import shutil
from pathlib import Path

from git import Repo
from kprize.constants import KEY_INSTANCE_ID, KEY_REPO
from kprize.git_utils import clone_repo, get_local_repo_dir_name, parse_repos_from_gitmodules, \
    get_owner_and_repo_from_git_url, clone_repo_from_url

class RepoCollector:
    def __init__(self, collected_repos_dir: Path, collected_instance_repos_dir: Path):
        self._collected_repos_dir = collected_repos_dir
        self._collected_instance_repos_dir = collected_instance_repos_dir

    def run_repo_collection(self, repos: list[str]):
        print("Running repo collection")
        print(f"Cloning repos")
        print(f"  repos_dir={self._collected_repos_dir}")

        skipped_repos = []
        for repo in repos:
            repo_dir_name = get_local_repo_dir_name(repo)
            repo_path = self._collected_repos_dir / repo_dir_name
            if repo_path.exists():
                skipped_repos.append(repo_dir_name)
                continue
            # clone repo
            clone_repo(repo, str(self._collected_repos_dir))
            # clone git submodules
            # check for .gitmodules file
            gitmodules_path = repo_path / ".gitmodules"
            if gitmodules_path.exists():
                print(f"Found .gitmodules file.")
                print(gitmodules_path.read_text())
                # get list of submodules
                sub_repo_urls = parse_repos_from_gitmodules(gitmodules_path.read_text())
                print(f"Cloning {len(sub_repo_urls)} submodules.\n{sub_repo_urls}")
                for sub_repo_url in sub_repo_urls:
                    owner, name = get_owner_and_repo_from_git_url(sub_repo_url)
                    sub_repo = f"{owner}/{name}"
                    sub_repo_dir = self._collected_repos_dir / get_local_repo_dir_name(sub_repo)
                    if sub_repo_dir.exists():
                        skipped_repos.append(sub_repo_dir)
                        continue
                    clone_repo_from_url(sub_repo_url, sub_repo, str(self._collected_repos_dir))
        if len(skipped_repos) > 0:
            print(f"Skipped for existing repos in {self._collected_repos_dir}:\n{skipped_repos}")

    def run_instance_repo_collection(self, instances: list):
        """
        Clone repo at base_commit for each instance, and remove git history
        """
        print("Running instance repo collection")
        skipped_instances = []
        for instance in instances:
            # check if instance repo already exists
            instance_repo_dir = self._collected_instance_repos_dir / f"repo__{instance[KEY_INSTANCE_ID]}"
            if instance_repo_dir.exists():
                skipped_instances.append(instance[KEY_INSTANCE_ID])
                continue
            # checkout the repo locally
            repo = instance[KEY_REPO]
            repo_dir = self._collected_repos_dir / get_local_repo_dir_name(repo)
            if not repo_dir.exists():
                # clone repo
                clone_repo(repo, str(self._collected_repos_dir))
            repo = Repo(repo_dir)
            # checkout commit
            base_commit = instance["base_commit"]
            repo.git.checkout(base_commit)
            # update submodules
            for submodule in repo.submodules:
                submodule.update(init=True)
            # copy repo to instance directory, not including .git
            shutil.copytree(repo_dir, instance_repo_dir, ignore=shutil.ignore_patterns('.git'))
        if len(skipped_instances) > 0:
            print(f"Skipped for existing instance repos in {self._collected_instance_repos_dir}:\n{skipped_instances}")
