import argparse
from pathlib import Path

from tqdm import tqdm

from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
from kprize.collection.configs.repo_config import RepoConfig
from kprize.collection.constants import KPRIZE_CONSTANTS


def create_repo_config(repo_path: str, specs_dict: dict) -> RepoConfig:
    repo_name = repo_path.split("/")[-1]

    return RepoConfig.from_dict(
        {
            "repo_name": repo_name,
            "repo_path": repo_path,
            "github_url": f"https://github.com/{repo_path}",
            "log_parser": MAP_REPO_TO_PARSER[repo_path].__name__,
            "specs": specs_dict,
        }
    )


def make_configs(verbose: bool, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    repos = MAP_REPO_VERSION_TO_SPECS.items()
    if verbose:
        repos = tqdm(repos, desc="Writing configs")

    for repo_path, specs_dict in repos:
        if repo_path not in MAP_REPO_TO_PARSER:
            if verbose:
                print(f"No log parser found for {repo_path}, skipping...")
            continue

        repo_name = repo_path.split("/")[-1]
        output_file = output_dir / f"{repo_name}.json"

        config = create_repo_config(repo_path, specs_dict)
        config.to_json(output_file)

        if verbose:
            print(f"Exported specs for {repo_path} to {output_file}...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=KPRIZE_CONSTANTS.latest_config_path,
        help=f"Output directory for config files (default: {KPRIZE_CONSTANTS.latest_config_path})",
    )

    args = parser.parse_args()

    make_configs(**vars(args))
