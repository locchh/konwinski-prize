"""
run_filter_task_instances.py

Filter task instances based on a split directory of task instances

Usage:
    python -m kprize.bundling.scripts.run_filter_task_instances -i <input-file> -o <output-file> -s <split-dir>
"""

import argparse
from pathlib import Path

from kprize.collection_utils import get_key_values
from kprize.constants import KEY_INSTANCE_ID
from kprize.dataset_utils import read_dataset_from_dir
from kprize.file_utils import read_jsonl, to_jsonl_str

if __name__ == "__main__":
    default_input_file = "task_instance_metadata/q3-task-instances-all-new-log-parser.jsonl"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input-file",
        help="File containing task instances to filter",
        type=str,
        default=Path(default_input_file),
    )
    parser.add_argument(
        "-o",
        "--output-file",
        help="File to output filtered task instances",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-s",
        "--split-dir",
        help="Directory to containing existing split task instances",
        type=str,
        default=Path("task_instances/test"),
    )
    args = parser.parse_args()

    input_file = Path(args.input_file)
    split_dir = Path(args.split_dir)
    output_file = Path(args.output_file) if args.output_file \
        else input_file.parent / f"{input_file.stem}-{split_dir.name}-filtered.jsonl"

    print(f" > input-file={input_file}")
    print(f" > output-file={output_file}")
    print(f" > split-dir={split_dir}")

    # Load task instances
    task_instances = read_jsonl(input_file)
    print(f"Filtering {len(task_instances)} task instances")

    # Read split
    split_instance_ids = get_key_values(read_dataset_from_dir(split_dir), KEY_INSTANCE_ID)
    print(f"Split has {len(split_instance_ids)} task instances")

    # Filter task instances
    filtered_instances = [inst for inst in task_instances if inst[KEY_INSTANCE_ID] in split_instance_ids]
    print(f"Filtered to {len(filtered_instances)} task instances")

    # Write to output file
    with open(output_file, "w") as f:
        jsonl_str = to_jsonl_str(filtered_instances)
        f.write(jsonl_str)

    print(f"New split writen to {output_file}")
