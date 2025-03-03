import glob
import json
import re
import shutil

import docker
from pathlib import Path

from kprize.bundling.docker.docker_conda_index import DockerCondaIndex
from kprize.bundling.docker.docker_pip_wheel import DockerPipWheel
from kprize.bundling.python_install_dependency_parser import PythonInstallDependencyParser
from kprize.bundling.repo_collector import RepoCollector
from kprize.constants import KEY_REPO, KEY_INSTANCE_ID, KAGGLE_DOCKER_IMAGE_WORKING
from kprize.collection_utils import group_by_key, get_key_values
from kprize.dataset_utils import read_dataset_from_dir, convert_task_instance_list_to_parquet
from kprize.bundling.kaggle_dataset import KaggleDatasetManager, read_landmine_instance_ids, read_bifurcation_data
from kprize.bundling.notebook_utils import get_instance_setup_notebook, get_instance_setup_notebook_venv
from kprize.docker_utils import container_stop_safe, container_remove_safe
from kprize.file_utils import copy_directory_skip_existing, create_dir_path, get_immediate_subdirectories
from kprize.json_utils import jsons
from kprize.subprocess_utils import run_commands


class KPrizeBundler:
    def __init__(
            self,
            instances_dir: str,
            output_dir: str,
            bundle_git_repos: bool = False,
            bundle_instance_repos: bool = True,
            bundle_compress: bool = True,
            create_venv_repos = False,
            split_filter: list[str] = None,
    ):
        self._instances_dir = Path(instances_dir)
        self._output_dir = Path(output_dir)
        # Create directories
        self._collected_deps_dir = create_dir_path(self._output_dir / "collected")
        self._collected_repos_dir = create_dir_path(self._collected_deps_dir / "repos")
        self._collected_instance_repos_dir = create_dir_path(self._collected_deps_dir / "instance_repos")
        self._collected_venv_repos_dir = create_dir_path(self._collected_deps_dir / "venv_repos")
        self._collected_pip_packages_dir = create_dir_path(self._collected_deps_dir / "pip_packages")
        self._collected_conda_packages_dir = create_dir_path(self._collected_deps_dir / "conda_packages")
        self._collected_conda_packages_linux64_dir = create_dir_path(self._collected_conda_packages_dir / "linux-64")
        self._collected_instance_requirements_dir = create_dir_path(self._collected_deps_dir / "instance_requirements")
        self._collected_failures_dir = create_dir_path(self._collected_deps_dir / "requirement_failures")

        # Docker directories
        self._docker_dir = create_dir_path(self._output_dir / "docker")
        self._docker_input_dir = create_dir_path(self._docker_dir / "input")
        self._docker_working_dir = create_dir_path(self._docker_dir / "working")
        self._docker_kprize_assets_dir = create_dir_path(self._docker_input_dir / "kprize-assets")
        self._docker_kprize_setup_dir = create_dir_path(self._docker_kprize_assets_dir / "kprize_setup")
        self._docker_setup_logs_dir = create_dir_path(self._docker_working_dir / "output/logs")

        # docker utils
        self._docker_conda_index = DockerCondaIndex()

        # Dependency parser
        self._python_install_dependency_parser = PythonInstallDependencyParser(
            install_logs_dir=self._docker_setup_logs_dir,
            collected_pip_packages_dir=self._collected_pip_packages_dir,
            collected_conda_packages_dir=self._collected_conda_packages_linux64_dir,
            collected_requirements_log_dir=self._collected_instance_requirements_dir,
            collected_failures_dir=self._collected_failures_dir,
        )

        # Kaggle dataset directories
        self._kaggle_dataset_dir = create_dir_path(self._output_dir / "kaggle_dataset")

        # Bundling assets directory
        self._kprize_bundling_assets_dir = Path("kprize/bundling/assets")

        # Kaggle bundle options
        self._bundle_git_repos = bundle_git_repos
        self._bundle_instance_repos = bundle_instance_repos
        self._bundle_compress = bundle_compress
        self._create_venv_repos = create_venv_repos
        self._split_filter = split_filter

        self._kaggle_dataset_manager = KaggleDatasetManager(
            output_dataset_dir=self._kaggle_dataset_dir,
            kprize_bundling_assets_dir=self._kprize_bundling_assets_dir,
            collected_pip_packages_dir=self._collected_pip_packages_dir,
            collected_conda_packages_linux64_dir=self._collected_conda_packages_linux64_dir,
            collected_instance_repos_dir=self._collected_instance_repos_dir,
            python_install_dependency_parser=self._python_install_dependency_parser,
            docker_conda_index=self._docker_conda_index,
        )

    def get_split_dirs(self) -> list[Path]:
        return get_immediate_subdirectories(self._instances_dir)

    def get_splits(self) -> list[str]:
        split_dirs = self.get_split_dirs()
        return [Path(d).name for d in split_dirs]

    def get_filtered_split_dirs(self) -> list[Path]:
        filtered = []
        for split_dir in self.get_split_dirs():
            if self._split_filter and split_dir.name in self._split_filter:
                filtered.append(split_dir)
        return filtered

    @staticmethod
    def remove_trailing_numbers(text) -> str:
        return re.sub(r'-\d+$', '', text)

    @staticmethod
    def get_repo_config_file_name(instance_id: str) -> str:
        repo_config_name = instance_id.split("__")[1]
        repo_config_name = KPrizeBundler.remove_trailing_numbers(repo_config_name)
        return f"{repo_config_name}.json"

    def remove_instance_run_data(self, instance_id: str):
        #repo config
        repo_config_path = self._docker_kprize_setup_dir / "repo_configs" / self.get_repo_config_file_name(instance_id)
        if repo_config_path.exists():
            print(f"Removing repo config: {repo_config_path}")
            repo_config_path.unlink()

        # setup logs
        setup_log_path = self._docker_setup_logs_dir.glob(f"{instance_id}*/setup_output.txt")
        for setup_log_file in setup_log_path:
            print(f"Removing setup log: {setup_log_file}")
            setup_log_file.unlink()

        #instance requirements
        pip_requirements_paths = list(self._collected_instance_requirements_dir.glob(
            self._python_install_dependency_parser.get_pip_requirements_file_name(f"{instance_id}*")
        ))
        conda_requirements_paths = list(self._collected_instance_requirements_dir.glob(
            self._python_install_dependency_parser.get_conda_requirements_file_name(f"{instance_id}*")
        ))
        for req_file in (pip_requirements_paths + conda_requirements_paths):
            print(f"Removing requirements logs: {req_file}")
            req_file.unlink()

        # reset conda index (delete noarch dir)
        conda_index_dir = self._collected_conda_packages_dir / "noarch"
        if conda_index_dir.exists():
            print(f"Removing conda index dir: {conda_index_dir}")
            shutil.rmtree(conda_index_dir)

    def copy_collected_dependencies_to_docker(self, instances: list[dict]):
        shutil.rmtree(self._docker_kprize_assets_dir / "repo_configs", ignore_errors=True)
        docker_kprize_working_dir = create_dir_path(self._docker_working_dir / "kprize-assets")
        shutil.rmtree(docker_kprize_working_dir, ignore_errors=True)

        # K Prize swebench
        for whl_file in glob.glob("dist/kprize-*.whl"):
            shutil.copy(whl_file, self._docker_kprize_setup_dir)
        # shutil.copy("dist/swebench-2.1.0-py3-none-any.whl", self._docker_kprize_setup_dir)

        # copy task instances to docker input
        task_instances_dir = create_dir_path(self._docker_kprize_assets_dir / "task_instances")
        input_task_instances_path = task_instances_dir / "input-task-instances.jsonl"
        input_task_instances_path.write_text("\n".join(list(map(json.dumps, instances))))

        # create dataset.parquet
        convert_task_instance_list_to_parquet(instances, self._docker_kprize_assets_dir / "dataset.parquet")

        # copy repo config
        shutil.copytree("repo_configs", self._docker_kprize_assets_dir / "repo_configs")

        # copy PIP packages
        print("Copying pip packages to docker...")
        copy_directory_skip_existing(self._collected_pip_packages_dir, self._docker_kprize_assets_dir / "pip_packages")
        print("Copying pip packages complete.")

        # copy repos to docker input
        print("Copying git repos to docker...")
        copy_directory_skip_existing(self._collected_repos_dir, self._docker_kprize_assets_dir / "git_repos")
        print("Copying repos complete.")

        # copy instances repos to docker input
        print("Copying instance_repos to docker...")
        copy_directory_skip_existing(self._collected_instance_repos_dir, self._docker_kprize_assets_dir / "repos")
        print("Copying repos complete.")

        # print("Copying venv repos to docker...")
        # copy_directory_skip_existing(self._docker_working_dir / "output/venv_repos", self._docker_kprize_assets_dir / "venv_repos")
        # print("Copying repos complete.")

        # copy CONDA packages to docker input
        print("Copying conda packages to docker input...")
        copy_directory_skip_existing(self._collected_conda_packages_dir, self._docker_kprize_assets_dir / "conda_packages")
        print("Copying conda packages complete.")

    def run_env_setup_in_docker(self, instances: list[dict], force_online: bool = True):
        print(f"Running setup in docker")
        print(f"  instances={len(instances)}")
        print(f"  instances={group_by_key(instances, KEY_INSTANCE_ID).keys()}")

        if len(instances) < 1:
            return

        # Create setup notebook
        if self._create_venv_repos:
            notebook = get_instance_setup_notebook_venv(instances)
        else:
            notebook = get_instance_setup_notebook(instances, force_online)

        # Save to notebook to docker inputs
        notebook_dir = create_dir_path(self._docker_input_dir / "notebooks")
        notebook_file_path = notebook_dir / "env_setup.ipynb"
        notebook_file_path.write_text(jsons(notebook))

        print("Running setup container...")
        client = docker.from_env()

        # Run notebook in Kaggle container
        container = client.containers.run(
            image=KAGGLE_DOCKER_IMAGE_WORKING,
            command='bin/bash -c "pip install --quiet jupyter nbconvert && ' +
                    'jupyter nbconvert --execute --inplace /kaggle/input/notebooks/env_setup.ipynb"'
            ,
            volumes=[
                f"{self._docker_dir.absolute()}/working:/kaggle/working/",
                f"{self._docker_dir.absolute()}/input:/kaggle/input/",
            ],
            detach=True,
            auto_remove=False,  # Auto remove causes issues reading logs
        )

        result = container.wait()
        exit_code = result['StatusCode']
        print(f"code: {exit_code} output: {result}")

        # Get container logs
        print(f"Logs:\n{container.logs().decode('utf-8')}")

        # Remove container
        container_stop_safe(container)
        container_remove_safe(container)

    @staticmethod
    def build_kprize_whl():
        run_commands(["pip wheel --no-deps -w ./dist ."])

    def run_dependency_collection(
            self,
            force_online: bool = True,
            conda_index: bool = False,
            upload_to_kaggle: bool = False,
            skip_run_in_docker: bool = False,
            skip_dataset_creation: bool = False,
            skip_docker_log_parsing: bool = False,
            clear_instance_id: str = None,
            dataset_id: str = "justinfiedler123/kprize-assets",
            force_copy_assets_to_docker: bool = False,
    ):
        print("Running dependency collection")
        print(f" > venv_repos={self._instances_dir}")
        print(f" > instances-dir={self._instances_dir}")
        print(f" > output-dir={self._output_dir}")
        print(f" > splits: {self.get_splits()}")

        # Load task instances
        instances = []
        for split_dir in self.get_split_dirs():
            split_instances = read_dataset_from_dir(split_dir)
            instances.extend(split_instances)
        instances_count = len(instances)
        grouped_instances = group_by_key(instances, KEY_REPO)
        repos = list(grouped_instances.keys())

        print("\nLoaded task instances")
        print(f" > instances={instances_count}")
        print(f" > repos({len(repos)})={repos}")

        print("\nBuilding kprize wheel...")
        self.build_kprize_whl()

        if clear_instance_id:
            print(f"Clearing instance run data for '{clear_instance_id}'")
            self.remove_instance_run_data(clear_instance_id)

        repo_collector = RepoCollector(
            collected_repos_dir=self._collected_repos_dir,
            collected_instance_repos_dir=self._collected_instance_repos_dir,
        )
        # Run repo collection
        repo_collector.run_repo_collection(repos)

        # Run instance repo collection
        repo_collector.run_instance_repo_collection(instances)

        # only run instances that don't already have logs
        instances_without_setup_logs = []
        instances_with_setup_logs = []
        for instance in instances:
            if Path(f"{self._docker_setup_logs_dir}/{instance[KEY_INSTANCE_ID]}/setup_output.txt").exists():
                instances_with_setup_logs.append(instance)
            else:
                instances_without_setup_logs.append(instance)

        run_setup_in_docker = not skip_run_in_docker and len(instances_without_setup_logs) > 0

        if run_setup_in_docker or force_copy_assets_to_docker:
            print("\nCopying collected dependencies to docker...")
            self.copy_collected_dependencies_to_docker(instances)

        # Run env setup in docker
        if run_setup_in_docker:
            print("\nRunning env setup docker...")
            print("Setup info already exists for the following instances. Skipping.")
            print(get_key_values(instances_with_setup_logs, KEY_INSTANCE_ID))
            self.run_env_setup_in_docker(instances_without_setup_logs, force_online=force_online)

        # Download packages from setup logs
        if not skip_docker_log_parsing:
            # get swebench pip dependencies
            print("Downloading swebench dependencies...")
            self._python_install_dependency_parser.download_packages_from_setup_log(
                "swebench",
                self._kprize_bundling_assets_dir / "swebench_pip_install_setup_output.txt",
            )
            # Download packages from setup logs
            self._python_install_dependency_parser.download_packages_from_setup_logs(instances)

        # Run pip wheel in docker
        if len(list(self._collected_pip_packages_dir.glob("*.tar.gz"))) > 0:
            DockerPipWheel.run_pip_wheel(self._collected_pip_packages_dir)

        # Run conda index in docker
        if not (self._collected_conda_packages_dir / "noarch").exists() or conda_index:
            self._docker_conda_index.run_conda_index(self._collected_conda_packages_dir)

        # Repackage collected datasets for kaggle
        if not skip_dataset_creation:
            split_dirs = self.get_filtered_split_dirs()
            self._kaggle_dataset_manager.repackage_collected_datasets_for_kaggle(
                dataset_id=dataset_id,
                split_dirs=split_dirs,
                compress=self._bundle_compress,
                landmine_instance_ids=read_landmine_instance_ids("task_instance_metadata/landmine_ids.txt"),
                bifurcation_dataset=read_bifurcation_data("task_instance_metadata/bifurcation.jsonl")
            )

        if upload_to_kaggle:
            # Upload kaggle dataset
            self._kaggle_dataset_manager.upload_dataset_to_kaggle()
