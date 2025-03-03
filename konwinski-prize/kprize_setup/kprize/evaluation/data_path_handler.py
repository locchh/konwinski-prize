from __future__ import annotations

import os
import shutil
from pathlib import Path
if not os.getenv("DISABLE_POLARS_IMPORT", False):
    # Polars throws error running in local Kaggle docker notebooks
    import polars as pl


class DataPathHandler:
    """Handles path management for data directories and ensures they exist."""
    def __init__(self, data_path: Path | str, input_dir: Path | str, scratch_dir: Path | str, verbose: bool = False):
        self.data_path = Path(data_path)
        self.input_dir = Path(input_dir)
        self.scratch_dir = Path(scratch_dir)
        self._unpacked_data_path = None
        self._verbose = verbose

    def _ensure_directories_exist(self) -> None:
        """Verifies all required directories exist, else throws an error."""
        if not self.repo_dir.exists():
            raise FileNotFoundError(
                f"Input repo directory {self.repo_dir} does not exist."
            )

        if not self.repo_config_dir.exists():
            raise FileNotFoundError(
                f"Repository configuration directory {self.repo_config_dir} does not exist."
            )

        if not self.task_instances_file.exists():
            raise FileNotFoundError(
                f"Task instances directory {self.task_instances_file} does not exist."
            )

    def _assert_unpacked(self):
        if self._unpacked_data_path is None:
            if self.data_path.is_dir():
                self._unpacked_data_path = self.data_path
            else:
                raise ValueError("Data path not unpacked.")

    @property
    def conda_channel_dir(self) -> Path:
        """Directory for conda packages."""
        self._assert_unpacked()
        return self._unpacked_data_path / "conda_packages"

    @property
    def has_local_conda_channel(self) -> bool:
        """Check if the conda channel directory exists."""
        return self.conda_channel_dir.exists()

    @property
    def pip_packages_dir(self) -> Path:
        """Directory for pip packages."""
        self._assert_unpacked()
        return self._unpacked_data_path / "pip_packages"

    @property
    def repo_dir(self) -> Path:
        """Directory for input repositories."""
        self._assert_unpacked()
        return self._unpacked_data_path / "repos"

    @property
    def git_repo_dir(self) -> Path:
        """Directory for full git repositories."""
        self._assert_unpacked()
        return self._unpacked_data_path / "git_repos"

    @property
    def venv_repo_dir(self) -> Path:
        """Directory for input repositories with venv environments."""
        self._assert_unpacked()
        return self._unpacked_data_path / "venv_repos"

    @property
    def repo_config_dir(self) -> Path:
        """Directory for repository configurations."""
        self._assert_unpacked()
        return self._unpacked_data_path / "repo_configs"

    @property
    def task_instances_file(self) -> Path:
        """Task instances dataset file"""
        self._assert_unpacked()
        return self._unpacked_data_path / "dataset.parquet"

    def get_repo_path(self, instance_id: str) -> Path:
        """Get a full path for a repository."""
        return self.repo_dir / f"repo__{instance_id}"

    def get_repo_config_path(self, repo_name: str) -> Path:
        """Get a full path for a repository configuration."""
        return self.repo_config_dir / f"{repo_name}.json"

    def _format_unpacked_data_path(self) -> Path:
        """Format the unpacked data path from the input data path."""
        # Convert /kaggle/input/**/{name}.{ext} to /kaggle/working/**/{name}/
        return (
            self._map_to_working_path(self.data_path.parent)
            / self.data_path.stem
        )

    def _map_to_working_path(self, path: Path) -> Path:
        try:
            return self.scratch_dir / path.relative_to(self.input_dir)
        except ValueError:
            return path

    def read_instance_metadata(self) -> pl.DataFrame:
        """Read instances from the input directory."""
        return pl.read_parquet(self.task_instances_file)

    def read_instances_as_dict(self) -> list[dict]:
        """Read instances from the input directory."""
        df = pl.read_parquet(self.task_instances_file)
        # Convert to list of dictionaries
        return df.to_dicts()

    def unpack_data_path(self):
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data path not found at {self.data_path}.")

        if self.data_path.is_dir():
            if self._verbose:
                print("Data path already unpacked. Skipping...")
            self._unpacked_data_path = self.data_path
        else:
            unpacked_data_path = self._format_unpacked_data_path()
            if self._verbose:
                print(f"Unpacking data path to {unpacked_data_path}...")
            if not unpacked_data_path.exists():
                shutil.unpack_archive(self.data_path, unpacked_data_path, format="zip")
            else:
                if self._verbose:
                    print(f"Data path already unpacked to {unpacked_data_path}. Skipping...")
            self._unpacked_data_path = unpacked_data_path

        if self._verbose:
            print(f"Unpacked to {self._unpacked_data_path}.")
        self._ensure_directories_exist()
