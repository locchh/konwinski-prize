import argparse
import json
import os
import string
from enum import Enum
from pathlib import Path
from typing import TypeVar

from anthropic import Anthropic
from tqdm import tqdm
from unidiff import PatchSet

from kprize.collection.constants import KPRIZE_CONSTANTS
from kprize.collection.quality_evaluation.types import (
    DualEvaluation,
    EnumWithNotes,
    InstanceQuality,
    IssueDescriptionQuality,
    IssueType,
    TestCoverage,
    TestQuality,
    TestStatus,
)

T = TypeVar("T", bound=Enum)


class QualityEvaluator:
    model_name = "claude-3-5-sonnet-20241022"

    def __init__(self, input_path: str | Path, overwrite: bool = False):
        input_path = Path(input_path)

        self.overwrite = overwrite
        self.input_paths = (
            [input_path] if input_path.is_file() else [p for p in input_path.glob("*.jsonl") if p.stat().st_size > 0]
        )
        self.instances = [self._load_task_instances(path) for path in self.input_paths]

        self.prompt_path = Path(__file__).parent / "prompts"

        self.client = Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        self._load_prompts()

    def _load_prompts(self) -> None:
        self.issue_description_quality_prompt = self._load_prompt(self.prompt_path / "issue-description-quality.txt")
        self.issue_type_prompt = self._load_prompt(self.prompt_path / "issue-type.txt")
        self.test_coverage_prompt = self._load_prompt(self.prompt_path / "test-coverage.txt")
        self.test_status_prompt = self._load_prompt(self.prompt_path / "test-status.txt")
        self.issue_description_summary_prompt = self._load_prompt(self.prompt_path / "issue-description-summary.txt")

    def _load_prompt(self, prompt_name: Path) -> str:
        return prompt_name.read_text()

    def _load_task_instances(self, input_path: Path) -> list[dict]:
        task_instances = []
        with input_path.open("r") as f:
            for line in f:
                task_instances.append(json.loads(line))

        return task_instances

    def _summarize_issue_description(self, instance: dict) -> str:
        prompt = self.issue_description_summary_prompt.format(issue_description=instance["problem_statement"])

        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        if len(response.content) == 0 or response.content[0].type != "text":
            print(f"Failed to generate issue description summary for instance {instance['instance_id']}")
            return ""

        return response.content[0].text

    def _get_enum_value_from_response(self, response: str, enum_class: type[T], default_value: T) -> T:
        response_words = {word.lower().strip(string.punctuation) for word in response.split()}
        assigned_values = [value for value in enum_class if value.value.lower() in response_words]

        if len(assigned_values) == 0:
            print(f"Model failed to provide a label, defaulting to '{default_value}'")
            return default_value

        if len(assigned_values) > 1:
            print(f"Model provided multiple labels, returning the last one: '{assigned_values[-1]}'")
            return assigned_values[-1]

        return assigned_values[0]

    def _classify_enum_with_reasoning(
        self,
        instance: dict,
        enum_class: type[T],
        prompt_template: str,
        prompt_args: dict,
        default_value: T,
    ) -> EnumWithNotes:
        """Classify using a formatted prompt template and return an enum value."""
        prompt = prompt_template.format(**prompt_args)

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        if len(response.content) == 0 or response.content[0].type != "text":
            print(f"No response from Anthropic for instance {instance['instance_id']}")
            return EnumWithNotes(value=default_value)

        reasoning = response.content[0].text
        value = self._get_enum_value_from_response(
            response=reasoning,
            enum_class=enum_class,
            default_value=default_value,
        )

        return EnumWithNotes(
            value=value,
            notes=reasoning,
        )

    def _get_pull_request_url(self, instance: dict) -> str:
        id = instance["instance_id"].split("-")[-1]
        return f"https://github.com/{instance['repo']}/pull/{id}/files"

    def _get_resolved_issue_urls(self, instance: dict) -> list[str]:
        return [f"https://github.com/{instance['repo']}/issues/{id}" for id in instance["issue_numbers"]]

    def _get_repo_name(self, repo: str) -> str:
        return repo.split("/")[-1]

    def _get_test_status_per_file(self, instance: dict) -> list[TestQuality]:
        patch_set = PatchSet(instance["test_patch"])

        return [
            TestQuality(
                test_file_path=file.path,
                status=DualEvaluation(
                    ai=self._classify_enum_with_reasoning(
                        instance=instance,
                        enum_class=TestStatus,
                        prompt_template=self.test_status_prompt,
                        prompt_args={
                            "issue_description": instance["problem_statement"],
                            "file_test_patch": str(file),
                        },
                        default_value=TestStatus.UNKNOWN,
                    ),
                    human=EnumWithNotes(value=TestStatus.UNSET),
                ),
            )
            for file in patch_set
        ]

    def _evaluate_instance(self, instance: dict, source_file_path: Path) -> InstanceQuality:
        pull_request_url = self._get_pull_request_url(instance)
        resolved_issue_urls = self._get_resolved_issue_urls(instance)

        ai_issue_description_quality = self._classify_enum_with_reasoning(
            instance=instance,
            enum_class=IssueDescriptionQuality,
            prompt_template=self.issue_description_quality_prompt,
            prompt_args={"issue_description": instance["problem_statement"]},
            default_value=IssueDescriptionQuality.UNKNOWN,
        )

        ai_issue_type = self._classify_enum_with_reasoning(
            instance=instance,
            enum_class=IssueType,
            prompt_template=self.issue_type_prompt,
            prompt_args={"issue_description": instance["problem_statement"]},
            default_value=IssueType.UNKNOWN,
        )

        ai_test_coverage = self._classify_enum_with_reasoning(
            instance=instance,
            enum_class=TestCoverage,
            prompt_template=self.test_coverage_prompt,
            prompt_args={
                "issue_description": instance["problem_statement"],
                "test_patch": instance["test_patch"],
            },
            default_value=TestCoverage.UNKNOWN,
        )

        test_status_per_file = self._get_test_status_per_file(instance)
        issue_description_summary = self._summarize_issue_description(instance)

        return InstanceQuality(
            instance_id=instance["instance_id"],
            repo=instance["repo"],
            repo_name=self._get_repo_name(instance["repo"]),
            source_file_path=source_file_path.as_posix(),
            issue_description=instance["problem_statement"],
            issue_description_summary=issue_description_summary,
            issue_description_quality=DualEvaluation(
                ai=ai_issue_description_quality,
                human=EnumWithNotes(value=IssueDescriptionQuality.UNSET),
            ),
            issue_type=DualEvaluation(
                ai=ai_issue_type,
                human=EnumWithNotes(value=IssueType.UNSET),
            ),
            test_qualities=test_status_per_file,
            test_coverage=DualEvaluation(
                ai=ai_test_coverage,
                human=EnumWithNotes(value=TestCoverage.UNSET),
            ),
            pull_request_url=pull_request_url,
            resolved_issue_urls=resolved_issue_urls,
        )

    def evaluate(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for repo_input_path, repo_instances in tqdm(list(zip(self.input_paths, self.instances))):
            repo_name = repo_input_path.stem.removesuffix("-task-instances")
            output_path = output_dir / f"{repo_name}.json"

            if output_path.exists() and not self.overwrite:
                print(f"Skipping {repo_name} because it already exists...")
                continue

            instance_quality_results = [
                self._evaluate_instance(instance, repo_input_path).to_dict() for instance in repo_instances
            ]

            output_path.write_text(json.dumps(instance_quality_results, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--input-path",
        type=str,
        required=True,
        help="Path to input JSONL file or directory with task instances",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=KPRIZE_CONSTANTS.quality_evaluation_path,
        type=str,
        help="Path to write evaluation results JSON file",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing evaluation files if they exist",
    )

    args = parser.parse_args()

    quality_evaluator = QualityEvaluator(
        input_path=args.input_path,
        overwrite=args.overwrite,
    )
    quality_evaluator.evaluate(args.output_dir)
