from __future__ import annotations
from enum import Enum
from pathlib import Path


class PipEnvManagerType(Enum):
    CONDA = "CONDA"
    MAMBA = "MAMBA"
    MICROMAMBA = "MICROMAMBA"
    VENV = "VENV"


class PipEnvManager:
    def __init__(
            self,
            manager: PipEnvManagerType,
            env_name: str | None = None,
            python_version: str | None = None,
            local_conda_channel_dir: Path | None = None,
            local_pip_packages_dir: Path | None = None,
            force_x86: bool = False,
    ):
        self._manager = manager
        self._env_name = env_name or ("testbed" if not manager == PipEnvManagerType.VENV else "venv")
        self._python_version = python_version
        self._local_conda_channel_dir = Path(local_conda_channel_dir) if local_conda_channel_dir else None
        self._local_pip_packages_dir = Path(local_pip_packages_dir) if local_pip_packages_dir else None
        self._force_x86 = force_x86

    @property
    def manager(self):
        return self._manager

    @property
    def is_venv(self):
        return self._manager == PipEnvManagerType.VENV

    @property
    def python_version(self):
        return self._python_version

    @python_version.setter
    def python_version(self, value: str):
        self._python_version = value

    def get_env_create_cmds(self, pkgs: str = "") -> list[str]:
        local_channel_options = "" if not self._local_conda_channel_dir \
            else f"--channel file://{self._local_conda_channel_dir} --override-channels "
        if self._manager == PipEnvManagerType.CONDA:
            return [
                f"conda create {local_channel_options}-n {self._env_name} python={self._python_version} {pkgs} -y"
            ]
        if self._manager == PipEnvManagerType.MAMBA:
            return [
                f"mamba create {local_channel_options}-n {self._env_name} python={self._python_version} {pkgs} -y"
            ]
        if self._manager == PipEnvManagerType.MICROMAMBA:
            return [
                f"micromamba create {local_channel_options}-n {self._env_name} python={self._python_version} {pkgs} -y"
            ]
        if self._manager == PipEnvManagerType.VENV:
            return ["python -m venv venv"] + ([f"pip install {pkgs}"] if pkgs else [])
        return []

    @property
    def env_preactivate_cmds(self) -> list[str]:
        if self._manager == PipEnvManagerType.CONDA:
            return ["source /opt/conda/bin/activate"]
        return []

    @property
    def env_activate_cmds(self) -> list[str]:
        if self._manager == PipEnvManagerType.CONDA:
            return [
                f"conda activate {self._env_name}",
            ] + (["conda config --env --set subdir osx-64"] if self._force_x86 else [])
        if self._manager == PipEnvManagerType.MAMBA:
            return [
                f"mamba activate {self._env_name}",
            ]
        if self._manager == PipEnvManagerType.VENV:
            return [
                f"source ./{self._env_name}/bin/activate",
            ]
        return []

    @property
    def global_env_add_cmds(self) -> list[str]:
        if self._manager == PipEnvManagerType.CONDA and self._local_conda_channel_dir:
            return [f"conda config --add channels file://{self._local_conda_channel_dir}"]
        if self._manager == PipEnvManagerType.MAMBA and self._local_conda_channel_dir:
            return [f"mamba config --add channels file://{self._local_conda_channel_dir}"]
        if self._manager == PipEnvManagerType.MICROMAMBA and self._local_conda_channel_dir:
            return [f"micromamba config --add channels file://{self._local_conda_channel_dir}"]
        # if self == PipEnvManager.VENV:
        #     return [f"rm -rf {self._env_name}"]
        return []

    @property
    def global_env_remove_cmds(self) -> list[str]:
        if self._manager == PipEnvManagerType.CONDA:
            return [f"conda remove -n {self._env_name} --all --yes"]
        if self._manager == PipEnvManagerType.MAMBA:
            return [f"mamba remove -n {self._env_name} --all --yes"]
        if self._manager == PipEnvManagerType.MICROMAMBA:
            return [f"micromamba remove -n {self._env_name} --all --yes"]
        # if self == PipEnvManager.VENV:
        #     return [f"rm -rf {self._env_name}"]
        return []

    @property
    def run_in_env_prefix(self) -> str:
        if self._manager == PipEnvManagerType.MICROMAMBA:
            return f"micromamba run -n {self._env_name} "
        return ""

    def get_run_in_env_cmd(self, cmd: str) -> str:
        updated_cmd = cmd

        if self._local_pip_packages_dir:
            updated_cmd = updated_cmd.replace(
                "pip install",
                f"pip install --no-index --find-links={self._local_pip_packages_dir}",
            )

        if self.run_in_env_prefix == "":
            return updated_cmd

        if "&&" in updated_cmd:
            updated_cmd = f"&& {self.run_in_env_prefix}".join(updated_cmd.split("&&"))
        return self.run_in_env_prefix + updated_cmd

    def set_conda_channel_dir(self, local_conda_channel_dir: Path):
        self._local_conda_channel_dir = local_conda_channel_dir