import argparse
import json
from pathlib import Path

from unidiff import PatchSet

from kprize.collection.constants import KPRIZE_CONSTANTS
from kprize.collection.quality_evaluation.types import (
    InstanceQuality,
    IssueDescriptionQuality,
    TestStatus,
)


class QualityFilter:
    acceptable_test_statuses = {
        TestStatus.IRRELEVANT_PASSING,
        TestStatus.ISSUE_DRIVEN,
        TestStatus.UNKNOWN,
    }

    def __init__(
        self,
        input_path: Path | str,
        quality_eval_path: Path | str,
        output_path: Path | str | None = None,
        overwrite: bool = False,
    ):
        """Initialize the QualityFilter.

        Args:
            input_path: Path to jsonl file or directory containing instance files
            quality_eval_path: Directory containing quality evaluation json files
            output_path: Optional output directory (defaults to input_path parent / "qualified")
            overwrite: If True, overwrite existing qualified files. If False, skip them.
        """
        self.input_path = Path(input_path)
        self.quality_eval_path = Path(quality_eval_path)
        self.overwrite = overwrite

        if output_path is None and self.input_path.is_file():
            self.output_path = self.input_path.parent.parent / "qualified"
        elif output_path is None:
            self.output_path = self.input_path.parent / "qualified"
        else:
            self.output_path = Path(output_path)

        self.output_path.mkdir(exist_ok=True, parents=True)

        self.input_paths = [self.input_path] if self.input_path.is_file() else list(self.input_path.glob("*.jsonl"))

        self.instances_by_repo = self._load_instances()
        self.qualities = self._load_qualities()

    def _load_instances(self) -> dict[str, list[dict]]:
        instances_by_repo = {}

        for file in self.input_paths:
            repo_name = file.stem.replace("-task-instances", "")
            with file.open() as f:
                instances_by_repo[repo_name] = [json.loads(line) for line in f if line.strip()]

        return instances_by_repo

    def _load_qualities(self) -> dict[str, dict[str, InstanceQuality]]:
        return {
            quality_file.stem: self._load_quality_file(quality_file)
            for quality_file in self.quality_eval_path.glob("*.json")
        }

    def _load_quality_file(self, quality_file: Path) -> dict[str, InstanceQuality]:
        qualities = {}
        file_qualities = json.loads(quality_file.read_text())

        for quality in file_qualities:
            instance_quality = InstanceQuality.from_dict(quality)
            qualities[instance_quality.instance_id] = instance_quality

        return qualities

    def _should_keep_instance(self, quality: InstanceQuality) -> bool:
        """Filter instances based on quality criteria.

        An instance is kept if it meets all of the following criteria:

        - Does not have an underspecified issue description according to human evaluation
        - Has at least one test file marked as relevant by human evaluation

        Args:
            quality: The quality evaluation for an instance

        Returns:
            bool: True if the instance should be kept, False otherwise
        """
        if quality.issue_description_quality.human.value == IssueDescriptionQuality.UNDERSPECIFIED:
            return False

        return any(
            test_quality.status.human.value == TestStatus.ISSUE_DRIVEN for test_quality in quality.test_qualities
        )

    def _filter_test_patch(self, instance: dict, quality: InstanceQuality) -> dict:
        test_statuses = {
            test_quality.test_file_path: test_quality.status.human.value for test_quality in quality.test_qualities
        }

        patch = PatchSet(instance["test_patch"])

        relevant_files = [
            patched_file
            for patched_file in patch
            if patched_file.path not in test_statuses
            or test_statuses[patched_file.path] in self.acceptable_test_statuses
        ]

        filtered_patch = "\n".join(str(file) for file in relevant_files)

        filtered_instance = instance.copy()
        filtered_instance["test_patch"] = filtered_patch

        return filtered_instance

    def _filter_instances(self, instances: list[dict], repo_qualities: dict) -> list[dict]:
        filtered_instances = []
        for instance in instances:
            instance_id = instance["instance_id"]

            if instance_id not in repo_qualities:
                print(f"Skipping {instance_id} - no quality evaluations found")
                continue

            quality = repo_qualities[instance_id]

            if self._should_keep_instance(quality):
                filtered_instance = self._filter_test_patch(instance, quality)
                filtered_instances.append(filtered_instance)

        return filtered_instances

    def _format_output_filename(self, repo_name: str) -> str:
        return f"{repo_name}-task-instances.jsonl"

    def _write_filtered_instances(self, repo_name: str, filtered_instances: list[dict]):
        output_file = self.output_path / self._format_output_filename(repo_name)
        with open(output_file, "w") as f:
            for instance in filtered_instances:
                f.write(json.dumps(instance) + "\n")

    def run(self):
        total_instances = 0
        total_kept = 0

        for repo_name, instances in self.instances_by_repo.items():
            output_file = self.output_path / self._format_output_filename(repo_name)
            if output_file.exists() and not self.overwrite:
                print(f"Skipping {repo_name} - output file already exists")
                continue

            if repo_name not in self.qualities:
                print(f"Skipping {repo_name} - no quality evaluations found")
                continue

            repo_qualities = self.qualities[repo_name]

            filtered_instances = self._filter_instances(instances, repo_qualities)

            if len(filtered_instances) > 0:
                self._write_filtered_instances(repo_name, filtered_instances)

            total_instances += len(instances)
            total_kept += len(filtered_instances)

            print(f"Processed {repo_name}: {len(filtered_instances)}/{len(instances)} instances kept")

        print(f"Total instances processed: {total_kept}/{total_instances} instances kept")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter instances based on quality evaluations")
    parser.add_argument(
        "--input-path",
        "-i",
        required=True,
        type=str,
        help="Path to jsonl file or directory containing instance files",
    )
    parser.add_argument(
        "--quality-eval-path",
        "-q",
        default=KPRIZE_CONSTANTS.quality_evaluation_path,
        type=str,
        help=f"Directory containing quality evaluation json files (default: {KPRIZE_CONSTANTS.quality_evaluation_path})",
    )
    parser.add_argument(
        "--output-path",
        "-o",
        type=str,
        help="Optional output directory (defaults to input_path parent / 'qualified')",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="If set, overwrite existing qualified files",
    )

    args = parser.parse_args()

    quality_filter = QualityFilter(**vars(args))

    quality_filter.run()
