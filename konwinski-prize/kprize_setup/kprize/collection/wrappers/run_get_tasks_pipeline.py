import argparse
import json
import shutil
from pathlib import Path

from swebench.collect.get_tasks_pipeline import main as base_get_tasks_pipeline


def _reorganize_output(tasks_path: str | Path):
    tasks_path = Path(tasks_path)
    base_path = tasks_path.parent

    filtered_dir = base_path / "filtered"
    pre_filtered_dir = base_path / "pre_filtered"

    filtered_dir.mkdir(exist_ok=True)
    pre_filtered_dir.mkdir(exist_ok=True)

    for file_path in tasks_path.glob("*.jsonl.all"):
        new_name = file_path.name.removesuffix(".all")
        dest_path = pre_filtered_dir / new_name
        shutil.copy(file_path, dest_path)

    for file_path in tasks_path.glob("*.jsonl"):
        dest_path = filtered_dir / file_path.name
        shutil.copy(file_path, dest_path)


def _extract_repo_from_github_url(github_url: str) -> str:
    return github_url.split("https://github.com/")[-1].strip("/")


def _extract_repos_from_json(json_file: str) -> list[str]:
    repos = []
    with open(json_file, "r") as f:
        for line in f:
            item = json.loads(line.strip())

            if "github" not in item:
                continue

            repo = _extract_repo_from_github_url(item["github"])
            repos.append(repo)

    return repos


def run_get_tasks_pipeline(
    repos_file: str,
    prs_path: str,
    tasks_path: str,
    max_pulls: int,
    start_date: str,
    end_date: str,
):
    repos = _extract_repos_from_json(repos_file)

    base_get_tasks_pipeline(
        repos=repos,
        path_prs=prs_path,
        path_tasks=tasks_path,
        max_pulls=max_pulls,
        cutoff_date=start_date,
        end_date=end_date,
    )

    _reorganize_output(tasks_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script to collect pull requests and convert them to candidate task instances"
    )
    parser.add_argument(
        "--repos_file",
        type=str,
        help="Path to JSON file containing repository information",
    )
    parser.add_argument(
        "--prs_path", type=str, help="Path to folder to save PR data files to"
    )
    parser.add_argument(
        "--tasks_path",
        type=str,
        help="Path to folder to save task instance data files to",
    )
    parser.add_argument(
        "--max_pulls",
        type=int,
        help="Maximum number of pulls to log",
        default=None,
    )
    parser.add_argument(
        "--start_date",
        type=str,
        help="Start date for PRs to consider in format YYYYMMDD",
        default=None,
    )
    parser.add_argument(
        "--end_date",
        type=str,
        help="End date for PRs to consider in format YYYYMMDD",
        default=None,
    )

    args = parser.parse_args()

    run_get_tasks_pipeline(**vars(args))
