import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple

from git import Repo

from kprize.docker_paths import get_input_repo_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_local_repo_dir_name(git_repo_name: str):
    return f"repo__{git_repo_name.replace('/', '__')}"


def get_input_repo_path_from_github_repo_name(repo: str) -> Path:
    return Path(get_input_repo_dir()) / get_local_repo_dir_name(repo)


def get_input_repo_path_from_git_url(git_url: str):
    owner, name = get_owner_and_repo_from_git_url(git_url)
    return get_input_repo_path_from_github_repo_name(f"{owner}/{name}")


# Copied from swebench.inference.make_datasets.bm25_retrieval
def clone_repo(repo, root_dir, token: Optional[str] = None):
    """
    Clones a GitHub repository to a specified directory.

    Args:
        repo (str): The GitHub repository to clone.
        root_dir (str): The root directory to clone the repository to.
        token (str): The GitHub personal access token to use for authentication.

    Returns:
        Path: The path to the cloned repository directory.
    """
    optional_token = f"{token}@" if token else ""
    repo_url = f"https://{optional_token}github.com/{repo}.git"

    return clone_repo_from_url(repo_url, repo, root_dir)


def clone_repo_from_url(repo_url: str, repo: str, root_dir):
    """
    Clones a Git repository to a specified directory.

    Args:
        repo_url (str): The url of the git repository to clone.
        repo (str): The name of the repository. e.g. owner/repo_name
        root_dir (str): The root directory to clone the repository to.

    Returns:
        Path: The path to the cloned repository directory.
    """
    repo_dir = Path(root_dir, get_local_repo_dir_name(repo))

    if not repo_dir.exists():
        logger.info(f"Cloning {repo} {os.getpid()}")
        Repo.clone_from(repo_url, repo_dir)
    return repo_dir


def get_tmp_repo_dir(git_repo_name: str) -> Path:
    return Path("/tmp/repos", git_repo_name.split('/')[-1])


def create_temp_local_repo(git_repo_name: str, commit: Optional[str] = None) -> Path:
    repo_dir = get_tmp_repo_dir(git_repo_name)
    if not repo_dir.exists():
        local_base_repo_path = get_input_repo_path_from_github_repo_name(git_repo_name)
        if not local_base_repo_path.exists():
            logger.error(f"Local repo path {local_base_repo_path} does not exist")
            return None
        # clone repo from base repo
        Repo.clone_from(local_base_repo_path, repo_dir)
    # checkout commit
    if commit is not None:
        repo = Repo(repo_dir)
        repo.git.checkout(commit)
    return repo_dir


def get_file_for_commit_from_local_repo(git_repo_name: str, commit: str, file_path: str) -> Optional[str]:
    repo_dir = create_temp_local_repo(git_repo_name, commit)
    # read file
    file_path = Path(repo_dir, file_path)
    if not file_path.exists():
        logger.error(f"File path {file_path} does not exist for commit {commit} in repo {git_repo_name}")
        return None
    # return file content
    return file_path.read_text()


def get_first_found_file_for_commit_from_local_repo(
        git_repo_name: str,
        commit: str,
        file_paths: list[str],
) -> Optional[str]:
    repo_dir = create_temp_local_repo(git_repo_name, commit)
    for file_path in file_paths:
        local_path = Path(repo_dir, file_path)
        if not file_path.exists():
            continue
        return local_path.read_text()
    return None


class MockResponse:
    def __init__(self, status_code: int, text: Optional[str] = None):
        self.status_code = status_code
        self.text = text


def request_file_from_local_repo(github_url: str) -> MockResponse:
    """
    Request a file from a local repo as if it was a HTTP request
    This is used to minimize changes to the existing swebench codebase (e.g. swebench.harness.utils)
    :param github_url:
    :return:
    """
    # extract repo and commit from github url
    # e.g. https://raw.githubusercontent.com/owner/repo_name/86fefd08f86e3492c8eba1066e41692a5751f161/swebench/harness/constants.py
    # e.g. https://github.com/owner/repo_name/blob/86fefd08f86e3492c8eba1066e41692a5751f161/swebench/harness/constants.py
    url = github_url.replace('blob/', '').replace('https://', '').replace('http://', '')
    path_parts = url.split('/')
    repo = '/'.join(path_parts[1:3])
    commit = path_parts[3]
    file_path = '/'.join(path_parts[4:])
    file_content = get_file_for_commit_from_local_repo(repo, commit, file_path)
    return MockResponse(200 if file_content else 404, file_content)


def parse_github_url(github_url: str):
    """
    Parses the given github_url to retrieve owner, repo, and sanitized url
    WARNING: This only supprts github.com urls
    """
    url = github_url
    owner, name = get_owner_and_repo_from_git_url(github_url)
    if owner and name:
        url = f"https://github.com/{owner}/{name}"
    return owner, name, url


def get_owner_and_repo_from_git_url(git_url: str) -> Tuple[str, str]:
    """
    Parses the given git_url to retrieve owner, repo, and sanitized url
    """
    result = re.search(".com/([\w-]*)/([\w-]*)", git_url)
    owner, name = None, None
    if result:
        owner = result.group(1)
        name = result.group(2)
    return owner, name


REGEX_SUBMODULE_URL = re.compile(r'\w*url = (.*)')


def parse_repos_from_gitmodules(gitmodules_content: str) -> list[str]:
    """
    Parse submodule urls from a .gitmodules file
    :param file_path:
    :return:
    """
    # Example .gitmodules file:
    # [submodule "sample-files"]
    # 	path = sample-files
    # 	url = https://github.com/py-pdf/sample-files
    sub_repos = []
    lines = gitmodules_content.split('\n')
    for line in lines:
        url_match = REGEX_SUBMODULE_URL.search(line)
        if url_match:
            sub_repos.append(url_match.group(1))
    return sub_repos


def get_total_count(api, api_method, *args, **kwargs):
    """
    Returns total count of items from given api_method for paginated results
    """
    PER_PAGE = 30
    items = api_method(*args, per_page=PER_PAGE, **kwargs)
    last_page = api.last_page()
    if last_page > 0:
        items = api_method(*args, per_page=PER_PAGE, page=last_page, **kwargs)
    return len(items) + (last_page * PER_PAGE)


def get_issue_and_pull_open_closed_counts(api, owner, name) -> dict:
    issues_count = -1
    issues_closed_count = -1
    pulls_closed_count = -1
    pulls_count = -1

    try:
        issues_count = get_total_count(api, api.issues.list_for_repo, owner, name)
        issues_closed_count = get_total_count(api, api.issues.list_for_repo, owner, name, state='closed')
        pulls_count = get_total_count(api, api.pulls.list, owner, name)
        pulls_closed_count = get_total_count(api, api.pulls.list, owner, name, state='closed')
    except Exception as e:
        print(f"Error getting github info {owner}/{name}\n{e}")
        pass

    return {
        "pull_stats": {
            "open": pulls_count,
            "closed": pulls_closed_count,
        },
        "issue_stats": {
            "open": issues_count,
            "closed": issues_closed_count,
        },
    }
