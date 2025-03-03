from argparse import ArgumentParser

from kprize.collection.validation.validator import Validator

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--input_path",
        type=str,
        help="Path to a JSONL file or directory containing JSONL files with task specifications.",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Maximum number of workers (should be <= 75%% of CPU cores)",
    )
    parser.add_argument("--open_file_limit", type=int, default=4096, help="Open file limit")
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Timeout (in seconds) for running tests for each instance",
    )
    parser.add_argument(
        "--force_rebuild",
        action="store_true",
        help="Force rebuild of all images",
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        help="Cache level - remove images above this level",
        default="env",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean images above cache level",
    )
    parser.add_argument("--run_id", type=str, required=True, help="Run ID - identifies the run")
    parser.add_argument(
        "--state_output_path",
        type=str,
        help="Directory to save the state json file.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing validation files.",
    )
    parser.add_argument(
        "--validated_dir",
        type=str,
        help="Directory to store validated files",
        required=True,
    )
    parser.add_argument(
        "--pre_validated_dir",
        type=str,
        help="Directory to store pre-validated files",
        required=True,
    )

    args = parser.parse_args()
    validator = Validator(**vars(args))
    validator.run()
