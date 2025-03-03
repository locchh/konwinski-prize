import argparse
from pathlib import Path
from kprize.git_utils import get_input_repo_path_from_git_url, parse_repos_from_gitmodules


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
