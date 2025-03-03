"""
    NOTICE:
    This is a standalone script that effectively duplicates kprize.scripts.setup_local_gitmodules
    It is used during evaluation to setup the environment for the evaluation script
    without installing the entire swebench package
"""

import argparse
import re
from pathlib import Path
from typing import Tuple
# from kprize.git_utils import get_input_repo_path_from_git_url, parse_repos_from_gitmodules


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


def get_input_repo_dir() -> str:
    return f"/kaggle/working/kprize-assets/repos"


def get_local_repo_dir_name(git_repo_name: str):
    return f"repo__{git_repo_name.replace('/', '__')}"


def get_input_repo_path_from_github_repo_name(repo: str) -> Path:
    return Path(get_input_repo_dir()) / get_local_repo_dir_name(repo)


def get_input_repo_path_from_git_url(git_url: str):
    owner, name = get_owner_and_repo_from_git_url(git_url)
    return get_input_repo_path_from_github_repo_name(f"{owner}/{name}")


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


def update_gitmodules_to_local_paths(input_gitmodules_path: Path, output_gitmodules_path: Path):
    if not input_gitmodules_path.exists():
        print(f"Error: .gitmodules not found in {input_gitmodules_path}")
        exit(1)

    # Read .gitmodules
    gitmodules_content = input_gitmodules_path.read_text()
    # Parse submodule URLs
    submodule_urls = parse_repos_from_gitmodules(gitmodules_content)

    # Update submodule URLs to local paths
    modified_gitmodules_content = gitmodules_content
    for submodule_url in submodule_urls:
        modified_gitmodules_content = modified_gitmodules_content.replace(
            submodule_url,
            str(get_input_repo_path_from_git_url(submodule_url))
        )

    # Write modified .gitmodules
    output_gitmodules_path.write_text(modified_gitmodules_content)
    print(f"Updated .gitmodules to use local paths: {output_gitmodules_path}")


if __name__ == "__main__":
    """
    Update .gitmodules to use local paths for offline testing
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        help="Path to .gitmodules file",
        type=str,
        default="/testbed/.gitmodules"
    )
    parser.add_argument(
        "-o",
        help="Path to output file for modified .gitmodules",
        type=str,
        default=None
    )
    args = parser.parse_args()

    input_path = Path(args.i)
    output_path = Path(args.o) if args.o is not None else input_path
    update_gitmodules_to_local_paths(input_path, output_path)
