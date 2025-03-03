from __future__ import annotations

from pathlib import Path

from kprize.constants import KAGGLE_OUTPUT_DIR, KAGGLE_WORKING_DIR, KAGGLE_INPUT_DIR

dataset_name = "kprize-assets-new" # kprize-assets

def get_input_kprize_assets_dir() -> str:
    return f"{KAGGLE_INPUT_DIR}/{dataset_name}"


def get_working_kprize_assets_dir() -> str:
    return f"{KAGGLE_WORKING_DIR}/{dataset_name}"


def get_input_repo_dir() -> str:
    return f"{get_working_kprize_assets_dir()}/repos"


def get_input_repo_path(repo: str) -> str:
    return f"{get_input_repo_dir()}/repo__{repo}"


def get_input_repo_path_from_instance_id(instance_id: str) -> str:
    instance_parts = instance_id.split('-')
    # remove the issue id
    repo = '-'.join(instance_parts[:-1])
    return get_input_repo_path(repo)


def get_input_pip_packages_dir() -> str:
    return f"{get_working_kprize_assets_dir()}/pip_packages"


def get_input_conda_channel_dir() -> str:
    return f"{get_working_kprize_assets_dir()}/conda_packages"


def get_patch_file_dir() -> str:
    return f"{KAGGLE_OUTPUT_DIR}/patch"


def get_test_patch_file_name(instance_id: str) -> str:
    return f"test_patch_{instance_id}.diff"


def get_model_patch_file_name(instance_id: str) -> str:
    return f"model_patch_{instance_id}.diff"


def get_test_patch_file_path(instance_id: str, output_dir: Path | None = None) -> Path:
    if output_dir is None:
        output_dir = Path(get_patch_file_dir())
    return output_dir / get_test_patch_file_name(instance_id)


def get_model_patch_file_path(instance_id: str, output_dir: Path | None = None) -> Path:
    if output_dir is None:
        output_dir = Path(get_patch_file_dir())
    return output_dir / get_model_patch_file_name(instance_id)
