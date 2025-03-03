from pathlib import Path
from typing import Any

from tqdm import tqdm

from swebench.harness.run_validation import main as base_run_validation
from kprize.collection.configs.repo_config import RepoConfig
from kprize.collection.configs.utils import get_latest_specs
from kprize.collection.constants import KPRIZE_CONSTANTS
from kprize.collection.kprize_global_state import KprizeGlobalState
from kprize.collection.validation.failure_mode import FailureMode
from kprize.collection.validation.instance_validation_stats import (
    InstanceValidationStats,
)


class Validator:
    def __init__(
        self,
        input_path: str,
        max_workers: int,
        force_rebuild: bool,
        cache_level: str,
        clean: bool,
        open_file_limit: int,
        run_id: str,
        state_output_path: str,
        validated_dir: str,
        pre_validated_dir: str,
        timeout: int = 1800,
        overwrite: bool = False,
    ):
        self.input_path = Path(input_path)
        self.max_workers = max_workers
        self.force_rebuild = force_rebuild
        self.cache_level = cache_level
        self.clean = clean
        self.open_file_limit = open_file_limit
        self.run_id = run_id
        self.state_output_path = Path(state_output_path)
        self.timeout = timeout
        self.state = KprizeGlobalState()
        self.overwrite = overwrite

        self.input_dir = self.input_path.parent if self.input_path.is_file() else self.input_path
        self.base_dir = self.input_dir.parent
        self.default_config = RepoConfig.from_json(Path(KPRIZE_CONSTANTS.default_config_path))

        self.validated_dir = Path(validated_dir)

        self.pre_validated_dir = Path(pre_validated_dir)

    def _init_repo_config(self, repo: str, repo_config_path: Path) -> RepoConfig:
        if repo_config_path.exists():
            return RepoConfig.from_json(repo_config_path)

        return RepoConfig(
            repo_name=repo.split("/")[-1],
            repo_path=repo,
            github_url=f"https://github.com/{repo}",
            log_parser=self.default_config.log_parser,
            specs={},
        )

    def _select_specs_or_default(self, repo_config: RepoConfig):
        if len(repo_config.specs) > 0:
            return get_latest_specs(repo_config)

        return get_latest_specs(self.default_config)

    def _update_repo_config(self, instances: list[dict[str, Any]]) -> None:
        if len(instances) == 0:
            return

        repo = instances[0]["repo"]
        repo_name = repo.split("/")[-1]
        repo_config_path = Path(KPRIZE_CONSTANTS.latest_config_path) / f"{repo_name}.json"

        repo_config = self._init_repo_config(repo, repo_config_path)

        default_version, default_specs = self._select_specs_or_default(repo_config)

        is_updated = False

        for instance in instances:
            any_fail_to_pass = len(instance.get("FAIL_TO_PASS", [])) > 0

            if any_fail_to_pass and "version" in instance and instance["version"] not in repo_config.specs:
                repo_config.specs[instance["version"]] = default_specs
                is_updated = True
            elif any_fail_to_pass and default_version not in repo_config.specs and len(repo_config.specs) == 0:
                repo_config.specs[default_version] = default_specs
                is_updated = True

        if is_updated:
            repo_config.to_json(repo_config_path)

    def _get_failure_mode(
        self,
        any_fail_to_pass: bool,
        any_pass_to_pass: bool,
        any_fail_to_fail: bool,
        any_pass_to_fail: bool,
    ) -> FailureMode:
        match (
            any_fail_to_pass,
            any_pass_to_pass,
            any_fail_to_fail,
            any_pass_to_fail,
        ):
            case (True, _, _, _):
                return FailureMode.SUCCESS
            case (False, True, _, _):
                return FailureMode.NO_FAIL_TO_PASS
            case (False, False, True, _):
                return FailureMode.NO_TO_PASS
            case (False, False, _, True):
                return FailureMode.NO_TO_PASS
            case (False, False, False, False):
                return FailureMode.NO_TESTS_RUN

    def _update_failure_modes(self, instances: list[dict[str, Any]]) -> None:
        for instance in instances:
            instance_id = instance["instance_id"]
            instance_state: InstanceValidationStats = self.state.get(instance_id)  # type: ignore

            if instance_state.failure_mode != FailureMode.UNKNOWN:
                continue

            any_fail_to_pass = len(instance.get("FAIL_TO_PASS", [])) > 0
            any_pass_to_pass = len(instance.get("PASS_TO_PASS", [])) > 0
            any_fail_to_fail = len(instance.get("FAIL_TO_FAIL", [])) > 0
            any_pass_to_fail = len(instance.get("PASS_TO_FAIL", [])) > 0

            failure_mode = self._get_failure_mode(
                any_fail_to_pass,
                any_pass_to_pass,
                any_fail_to_fail,
                any_pass_to_fail,
            )
            self.state.set(
                instance_id,
                InstanceValidationStats(failure_mode=failure_mode),
            )

    def _handle_finish_validation(self, instances: list[dict[str, Any]], repo_name: str):
        output_path = self.state_output_path / f"{repo_name}.json"

        if len(instances) == 0:
            if repo_name and self.state_output_path:
                self.state.save(output_path)
            return

        if KPRIZE_CONSTANTS.use_kprize_configs:
            self._update_repo_config(instances)

        self._update_failure_modes(instances)

        if repo_name and self.state_output_path:
            self.state.save(output_path)

    def _reorganize_output(self, repo_name: str):
        self.validated_dir.mkdir(exist_ok=True)
        self.pre_validated_dir.mkdir(exist_ok=True)

        validated_all_file = self.input_dir / f"{repo_name}-task-instances_validated.all.jsonl"

        if validated_all_file.exists():
            new_name = validated_all_file.name.replace("_validated.all.jsonl", ".jsonl")
            dest_path = self.pre_validated_dir / new_name
            validated_all_file.rename(dest_path)

        validated_file = self.input_dir / f"{repo_name}-task-instances_validated.jsonl"

        if validated_file.exists():
            new_name = validated_file.name.replace("_validated.jsonl", ".jsonl")
            dest_path = self.validated_dir / new_name
            validated_file.rename(dest_path)

    def _validate_repo(self, input_filepath: Path):
        try:
            instances = base_run_validation(
                dataset_name=input_filepath.as_posix(),
                split="",
                instance_ids=[],
                max_workers=self.max_workers,
                force_rebuild=self.force_rebuild,
                cache_level=self.cache_level,
                clean=self.clean,
                open_file_limit=self.open_file_limit,
                run_id=self.run_id,
                timeout=self.timeout,
            )
        except Exception as e:
            print(f"Error processing {input_filepath}: {e}")
            instances = []

        repo_name = input_filepath.stem.removesuffix("-task-instances")

        self._handle_finish_validation(instances=instances, repo_name=repo_name)
        self._reorganize_output(repo_name)

    def run(self):
        """Run the validation process."""
        if self.input_path.is_file():
            input_filepaths = [self.input_path]
        else:
            input_filepaths = list(self.input_path.glob("*.jsonl"))

        validated_filepaths = [
            self.validated_dir / f"{input_filepath.stem}.jsonl" for input_filepath in input_filepaths
        ]

        non_validated_filepaths = [
            input_filepath
            for input_filepath, validated_filepath in zip(input_filepaths, validated_filepaths)
            if not validated_filepath.exists() or validated_filepath.stat().st_size == 0
        ]

        filepaths_to_validate = non_validated_filepaths if not self.overwrite else input_filepaths

        if self.overwrite:
            print(f"Overwriting {len(validated_filepaths) - len(non_validated_filepaths)} existing validation file(s).")

        print(f"Processing {len(filepaths_to_validate)} files out of {len(input_filepaths)} total file(s).")

        for input_filepath in tqdm(filepaths_to_validate):
            print(
                "=" * 100,
                f"Processing: {input_filepath}",
                "=" * 100,
                sep="\n",
            )
            self.state.clear()
            self._validate_repo(input_filepath)
