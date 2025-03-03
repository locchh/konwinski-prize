"""
This file is based on the swebench/kprize/harness/test_spec.py file from the swebench repository.

It makes the following changes:
1. Allows use of different pip env managers e.g. virtualenv, mamba, conda
2. Some environment functionality may not work for venv at this time (environment.yml, requirements.txt)
"""

from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Any, Union, cast

from swebench.harness.constants import (
    APPLY_PATCH_PASS,
    FAIL_TO_PASS,
    KEY_INSTANCE_ID,
    MAP_REPO_TO_INSTALL,
    PASS_TO_PASS,
    USE_X86,
    SWEbenchInstance,
)
from kprize.harness.test_spec import (
    DIFF_MODIFIED_FILE_REGEX,
    replace_uninstallable_packages_requirements_txt,
)
from kprize.harness.test_spec import TestSpec
from kprize.harness.utils import (
    get_environment_yml,
    get_requirements,
    get_test_directives,
)
from kprize.collection.configs.repo_config import RepoConfig
from kprize.constants import (
    HEREDOC_DELIMITER_GIT_APPLY,
    HEREDOC_DELIMITER_REQUIREMENTS,
)
from kprize.harness.pip_env_manager import (
    PipEnvManager,
)


class TestSpecCreator:
    def __init__(
        self,
        pip_env_manager: PipEnvManager,
        repo_config_dir: Path | str,
        instance_repos_dir: Path | None = None,
        local_repos_dir: Path | None = None,
        disable_apt_install: bool = False,
        include_install_in_repo_setup: bool = False,
        reset_tests_after_eval: bool = False,
        # swebench originally used "$HOME" for the requirements_dir,
        # but this is not available in the kaggle environment
        requirements_dir: str = "/root",
        testbed_dir: str = "/testbed",
        activate_only_in_eval: bool = False,
    ):
        self._pip_env_manager = pip_env_manager
        self._instance_repos_dir = Path(instance_repos_dir) if instance_repos_dir else None
        self._local_repos_dir = Path(local_repos_dir) if local_repos_dir else None
        self._disable_apt_install = disable_apt_install
        self._include_install_in_repo_setup = include_install_in_repo_setup
        self._reset_tests_after_eval = reset_tests_after_eval
        self._requirements_dir = Path(requirements_dir)
        self._repo_config_dir = Path(repo_config_dir)
        self._testbed_dir = Path(testbed_dir)
        self._activate_only_in_eval = activate_only_in_eval

    def _get_instance_repo_dir(self, instance_id: str) -> Path:
        if self._instance_repos_dir is None:
            raise ValueError("instance_repo_dir is not set")

        return self._instance_repos_dir / f"repo__{instance_id}"

    def _get_local_repo_dir(self, instance_id: str) -> Path:
        if self._local_repos_dir is None:
            raise ValueError("local_repos_dir is not set")
        instance_parts = instance_id.split('-')
        repo = '-'.join(instance_parts[:-1])
        return self._local_repos_dir / f"repo__{repo}"

    def _get_repo_config_path(self, repo_name: str) -> Path:
        return self._repo_config_dir / f"{repo_name}.json"

    def get_apply_model_patch_commands(self, model_patch_path: Path) -> list[str]:
        return [f'echo "{APPLY_PATCH_PASS} (pred)"'] + (
            [f"git apply {model_patch_path} -v"]
            if not self._instance_repos_dir
            else [f"patch -p1 < {model_patch_path}"]
        )

    def get_test_specs_from_dataset(self, dataset: Union[list[SWEbenchInstance], list[TestSpec]]) -> list[TestSpec]:
        """
        Idempotent function that converts a list of SWEbenchInstance objects to a list of TestSpec objects.
        """
        if isinstance(dataset[0], TestSpec):
            return cast(list[TestSpec], dataset)
        return list(map(self.make_test_spec, cast(list[SWEbenchInstance], dataset)))

    def make_repo_script_list(self, specs, repo, repo_directory, base_commit, instance_id: str) -> list[str]:
        """
        Create a list of bash commands to set up the repository for testing.
        This is the setup script for the instance image.
        """
        manager = self._pip_env_manager
        current_env = "$CONDA_DEFAULT_ENV" if not manager.is_venv else "venv"
        repo_env_create_cmds = [] if self._activate_only_in_eval else (
                manager.env_preactivate_cmds +
                [] if not manager.is_venv else manager.get_env_create_cmds() +
                manager.env_activate_cmds
        )
        if self._instance_repos_dir:
            instance_repo_dir = self._get_instance_repo_dir(instance_id)
            setup_commands = (
                [
                    f"cp -r {instance_repo_dir} {repo_directory}",
                    f"chmod -R 777 {repo_directory}",  # So nonroot user can run tests
                    f"cd {repo_directory}",
                    # Make sure conda is available for later use
                ]
                + repo_env_create_cmds
                + [
                    f'echo "Current environment: {current_env}"',
                ]
            )
        else:
            repo_env_create_cmds = (manager.env_preactivate_cmds + manager.env_activate_cmds) \
                if not manager.is_venv else manager.get_env_create_cmds()
            # This is copied from the original swebench implementation
            setup_commands = (
                [
                    f"git clone -o origin https://github.com/{repo} {repo_directory}"
                    if not self._local_repos_dir
                    else f"git clone {self._get_local_repo_dir(instance_id)} {repo_directory}",
                    f"chmod -R 777 {repo_directory}",  # So nonroot user can run tests
                    f"cd {repo_directory}",
                    f"git reset --hard {base_commit}",
                    # Remove the remote so the agent won't see newer commits.
                    "git remote remove origin",
                ]
                + repo_env_create_cmds
            )
        if repo in MAP_REPO_TO_INSTALL:
            setup_commands.append(MAP_REPO_TO_INSTALL[repo])

        # Run pre-install set up if provided
        if "pre_install" in specs:
            for pre_install in specs["pre_install"]:
                if self._instance_repos_dir:
                    if "git " in pre_install:
                        # skip git commands if using instance repo, instance repo is already in the proper base state
                        continue
                # elif self._local_repos_dir:
                    # Use local gitmodules if available
                    # if "git submodule update" in pre_install:
                    #     # e.g. "git submodule update --init"
                    #     # replace .com urls in .gitmodules with local paths
                    #     input_repo_path = Path(self._get_local_repo_dir(instance_id))
                    #     if input_repo_path.exists():
                    #         print("Using local gitmodules.")
                    #         pre_install = (
                    #             f"python /kaggle/input/kprize-assets/setup_local_gitmodules.py && {pre_install}"
                    #         )
                if self._disable_apt_install and "apt-get " in pre_install:
                    continue
                setup_commands.append(pre_install)
        if "pip_packages" in specs and manager.is_venv and not self._activate_only_in_eval:
            pip_packages = " ".join(specs["pip_packages"])
            cmd = manager.get_run_in_env_cmd(f"python -m pip install {pip_packages}")
            setup_commands.append(cmd)

        if "install" in specs and self._include_install_in_repo_setup and not self._activate_only_in_eval:
            setup_commands.append(manager.get_run_in_env_cmd(specs["install"]))
        return setup_commands

    def make_env_script_list(self, instance: SWEbenchInstance, specs: dict, env_name: str) -> list[str]:
        """
        Creates the list of commands to set up the conda environment for testing.
        This is the setup script for the environment image.

        Returns:
            list[str]: List of commands to set up the conda environment
        """
        manager = self._pip_env_manager
        python_version = manager.python_version
        env_name = env_name if not manager.is_venv else "venv"
        reqs_commands = manager.global_env_add_cmds + manager.env_preactivate_cmds
        # Create conda environment according to install instructinos
        pkgs = specs.get("packages", "")
        if pkgs == "requirements.txt":
            # Create environment
            cmd = manager.get_env_create_cmds()
            reqs_commands += cmd

            # Install dependencies
            reqs = replace_uninstallable_packages_requirements_txt(get_requirements(instance))
            path_to_reqs = f"{self._requirements_dir}/requirements.txt"
            reqs_commands.append(
                f"cat <<'{HEREDOC_DELIMITER_REQUIREMENTS}' > {path_to_reqs}\n{reqs}\n{HEREDOC_DELIMITER_REQUIREMENTS}"
            )
            cmd = manager.env_activate_cmds
            # cmd = f"conda activate {env_name} && python -m pip install -r {path_to_reqs}"
            reqs_commands += cmd
            reqs_commands.append(manager.get_run_in_env_cmd(f"python -m pip install -r {path_to_reqs}"))
            reqs_commands.append(f"rm {path_to_reqs}")
        elif pkgs == "environment.yml":
            # Create environment from yml
            reqs = get_environment_yml(instance, env_name)
            path_to_reqs = "environment.yml"
            reqs_commands.append(
                f"cat <<'{HEREDOC_DELIMITER_REQUIREMENTS}' > {path_to_reqs}\n{reqs}\n{HEREDOC_DELIMITER_REQUIREMENTS}"
            )
            if "no_use_env" in specs and specs["no_use_env"]:
                # `conda create` based installation
                cmd = f"conda create -c conda-forge -n {env_name} python={python_version} -y"
                reqs_commands.append(cmd)

                # Install dependencies
                cmd = f"conda env update -f {path_to_reqs}"
                reqs_commands.append(cmd)
            else:
                # `conda env create` based installation
                cmd = f"conda env create --file {path_to_reqs}"
                reqs_commands.append(cmd)

                cmd = f"conda activate {env_name} && conda install python={python_version} -y"
                reqs_commands.append(cmd)

            # Remove environment.yml
            reqs_commands.append(f"rm {path_to_reqs}")
        else:
            # Create environment + install dependencies
            cmd = manager.get_env_create_cmds(pkgs) if not manager.is_venv else []
            reqs_commands += cmd

        # reqs_commands.append(f"conda activate {env_name}")
        reqs_commands += manager.env_activate_cmds if not manager.is_venv else []

        # Install additional packages if specified
        if "pip_packages" in specs and not manager.is_venv:
            pip_packages = " ".join(specs["pip_packages"])
            cmd = manager.get_run_in_env_cmd(f"python -m pip install {pip_packages}")
            reqs_commands.append(cmd)
        return reqs_commands

    def make_eval_script_list(
        self,
        instance,
        specs,
        repo_directory,
        base_commit: str,
        test_patch: str | None = None,  # deprecated: use test_patch_path, kept for backwards compat with old swebench
        test_patch_path: Path | None = None,
        model_patch_path: Path | None = None,
    ) -> list[str]:
        """
        Applies the test patch and runs the tests.
        """
        instance_id = instance[KEY_INSTANCE_ID]
        repo_config = RepoConfig.from_json(self._get_repo_config_path(instance["repo"].split("/")[-1]))
        manager = self._pip_env_manager
        env_activate_commands = manager.env_preactivate_cmds + manager.env_activate_cmds

        if test_patch_path and test_patch_path.exists():
            test_patch = test_patch_path.read_text()

        if test_patch is None:
            raise ValueError("test_patch or test_patch_path must be provided")

        test_files = re.findall(DIFF_MODIFIED_FILE_REGEX, test_patch)

        # Reset test files to the state they should be in before the patch.
        if self._instance_repos_dir:
            instance_repo_dir = self._get_instance_repo_dir(instance_id)
            reset_tests_command = f"cp -f {' '.join(map(lambda tf: str(instance_repo_dir / tf), test_files))}"
        else:
            reset_tests_command = f"git checkout {base_commit} {' '.join(test_files)}"

        model_patch_commands = [] if not model_patch_path else self.get_apply_model_patch_commands(model_patch_path)

        if test_patch_path is not None:
            if self._instance_repos_dir:
                apply_test_patch_command = f"patch -p1 < {test_patch_path}"
            else:
                apply_test_patch_command = f"git apply {test_patch_path}"
        else:
            apply_test_patch_command = (
                f"git apply -v - <<'{HEREDOC_DELIMITER_GIT_APPLY}'\n{test_patch}\n{HEREDOC_DELIMITER_GIT_APPLY}"
            )
        test_command = " ".join(
            [
                manager.get_run_in_env_cmd(repo_config.get_specs_with_fallback(instance.get("version")).test_cmd),
                *get_test_directives(instance),
            ]
        )
        eval_commands = [f"cd {repo_directory}"] + env_activate_commands

        if "eval_commands" in specs:
            eval_commands += specs["eval_commands"]

        if not self._instance_repos_dir:
            eval_commands += [
                f"git config --global --add safe.directory {repo_directory}",  # for nonroot user
                # This is just informational, so we have a record
                "git status",
                "git show",
                f"git diff {base_commit}",
            ]  # + self._pip_env_manager.env_activate_cmds
        if "install" in specs and not self._include_install_in_repo_setup and not self._activate_only_in_eval:
            env_vars = (" ".join(specs["env_vars"]) + " ") if "env_vars" in specs else ""
            eval_commands.append(env_vars + manager.get_run_in_env_cmd(specs["install"]))
        if not self._instance_repos_dir:
            eval_commands.append(reset_tests_command)
        eval_commands += model_patch_commands + [
            apply_test_patch_command,
            test_command,
        ]
        if self._reset_tests_after_eval:
            # Revert tests after done, leave the repo in the same state as before
            eval_commands.append(reset_tests_command)
        return eval_commands

    def make_test_spec(
        self,
        instance: SWEbenchInstance,
        use_spec_python: bool = False,
        test_patch_path: Path | None = None,
        model_patch_path: Path | None = None,
    ) -> TestSpec:
        if isinstance(instance, TestSpec):
            return instance
        repo_config = RepoConfig.from_json(self._get_repo_config_path(instance["repo"].split("/")[-1]))
        instance_id = instance[KEY_INSTANCE_ID]
        repo = instance["repo"]
        version = instance.get("version", "none")
        instance["version"] = version
        base_commit = instance["base_commit"]
        problem_statement = instance["problem_statement"]
        hints_text = instance.get("hints_text", "")  # Unused
        test_patch = instance["test_patch"]


        def _from_json_or_obj(key: str) -> Any:
            """If key points to string, load with json"""
            if isinstance(instance[key], str):
                return json.loads(instance[key])
            return instance[key]

        pass_to_pass = _from_json_or_obj(PASS_TO_PASS)
        fail_to_pass = _from_json_or_obj(FAIL_TO_PASS)
        env_name = "testbed"
        repo_directory = self._testbed_dir or f"/{env_name}"
        specs = repo_config.get_specs_with_fallback(version).to_dict()

        # Override the default python version
        if use_spec_python:
            self._pip_env_manager.python_version = specs["python"]

        repo_script_list = self.make_repo_script_list(specs, repo, repo_directory, base_commit, instance_id)
        env_script_list = self.make_env_script_list(instance, specs, env_name)
        eval_script_list = self.make_eval_script_list(
            instance,
            specs,
            repo_directory,
            base_commit,
            test_patch=test_patch,
            test_patch_path=test_patch_path,
            model_patch_path=model_patch_path,
        )
        if platform.machine() in {"aarch64", "arm64"}:
            # use arm64 unless explicitly specified
            arch = "arm64" if instance_id not in USE_X86 else "x86_64"
        else:
            arch = "x86_64"

        return TestSpec(
            instance_id=instance_id,
            repo=repo,
            env_script_list=env_script_list,
            repo_script_list=repo_script_list,
            eval_script_list=eval_script_list,
            version=version,
            arch=arch,
            FAIL_TO_PASS=fail_to_pass,
            PASS_TO_PASS=pass_to_pass,
        )
