import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from kprize.dataclass_utils import asdict_factory


@dataclass
class Spec:
    """
    Configuration specification for repository setup and testing.

    The docstring params are in the order they are executed when building the
    image and then running the container.

    Parameters:
        python (str): Python version to use (e.g. "3.8", "3.9")
        packages (str, optional): Space-separated list of conda packages to
            install, or "requirements.txt" or "environment.yml"
        pip_packages (tuple[str, ...], optional): Python packages to install via pip
        pre_install (tuple[str, ...], optional): Commands to run before installation
        install (str, optional): Command to install the repository (e.g. "pip install -e .")
        eval_commands (tuple[str, ...], optional): Commands to run before the test test_cmd.
        test_cmd (str): Command to run tests (e.g. "pytest tests")
        execute_test_as_nonroot (bool, optional): Whether to run tests as non-root user
        no_use_env (bool, optional): Whether to skip using a virtual environment
        nano_cpus (int, optional): CPU quota in units of 1e-9 CPUs
    """

    python: str
    test_cmd: str
    install: str | None = None
    packages: str | None = None
    pip_packages: tuple[str, ...] | None = None
    eval_commands: tuple[str, ...] | None = None
    pre_install: tuple[str, ...] | None = None
    execute_test_as_nonroot: bool | None = None
    no_use_env: bool | None = None
    nano_cpus: int | None = None
    env_vars: tuple[str, ...] | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "Spec":
        return cls(**data)


@dataclass
class RepoConfig:
    repo_name: str
    repo_path: str
    github_url: str
    log_parser: str
    # version -> spec
    specs: dict[str, Spec] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=asdict_factory)

    @classmethod
    def from_dict(cls, data: dict) -> "RepoConfig":
        data = data.copy()
        data["specs"] = {version: Spec.from_dict(spec_data) for version, spec_data in data["specs"].items()}
        return cls(**data)

    @classmethod
    def from_json(cls, json_path: Path) -> "RepoConfig":
        return cls.from_dict(json.loads(Path(json_path).read_text()))

    def to_json(self, json_path: Path) -> None:
        Path(json_path).write_text(json.dumps(self.to_dict(), indent=4))

    def get_specs_with_fallback(self, version: str | None = None) -> Spec:
        if len(self.specs) == 0:
            raise ValueError("No specs found in repo config")

        if version in self.specs:
            return self.specs[version]
        elif "default" in self.specs:
            return self.specs["default"]
        else:
            return self.specs[max(self.specs.keys())]
