# import kaggle.api
import copy
import glob
import shutil
from pathlib import Path
from typing import Optional

from kprize.bundling.docker.docker_conda_index import DockerCondaIndex
from kprize.bundling.python_install_dependency_parser import PythonInstallDependencyParser
from kprize.collection_utils import get_key_values, group_by_key
from kprize.constants import KEY_REPO, KEY_INSTANCE_ID
from kprize.dataset_utils import convert_task_instance_list_to_parquet, read_dataset_from_dir
from kprize.file_utils import zip_dir, get_immediate_subdirectories, copy_selective_dirs, create_dir_path, \
    copy_selective_files, read_jsonl
from kprize.json_utils import jsons
from kprize.subprocess_utils import run_commands
from swebench.harness.constants import FAIL_TO_FAIL, PASS_TO_FAIL


def create_dataset_metadata(
        dataset_title: str,
        dataset_id: str,
        resources: list[dict],
        license_name: str = "CC0-1.0",
) -> dict:
    return {
        "title": dataset_title,  # "Conda packages for K Prize",
        "id": dataset_id,  # "justinfiedler123/kprize-offline-assets",
        "licenses": [
            {
                "name": license_name
            }
        ],
        "resources": resources
    }


def get_resources_from_dirs(dirs: list[Path], root_dir: Optional[str] = None) -> list[dict]:
    """
    Get resources from directories
    :param dirs:
    :param root_dir:
    :return:
    """
    resources: list[dict] = []
    for directory in dirs:
        file_paths = directory.glob("**/*")
        for path in file_paths:
            # skip directory paths
            if path.is_dir():
                continue
            # skip metadata files
            if "dataset-metadata" in str(path):
                continue
            # skip DS_Store files
            if ".DS_Store" in str(path):
                continue
            # files paths
            rpath = str(path)
            if root_dir:
                rpath = rpath.split(root_dir)[1]
            resources.append({
                "path": rpath,
            })
    return resources

def read_landmine_instance_ids(file_path: Path|str) -> list[str]:
    """
    Read landmine instance ids
    :param file_path: Text file with instance ids separated by newlines
    :return:
    """
    file_path = Path(file_path)
    if file_path.exists():
        return file_path.read_text().splitlines()
    return []

def read_bifurcation_data(file_path: Path|str) -> list[dict]:
    """
    Read bifurcation data
    :param file_path: JSONL file with bifurcation data
    :return:
    """
    file_path = Path(file_path)
    if file_path.exists():
        return read_jsonl(file_path)
    return []

KEY_BIFURCATION_TEST_PATCH = "bifurcation_test_patch"
KEY_BIFURCATION_EXPECTATIONS = "bifurcation_expectations"
KEY_IS_LANDMINE = "is_landmine"

class KaggleDatasetManager:
    def __init__(
        self,
        output_dataset_dir: Path,
        kprize_bundling_assets_dir: Path,
        collected_pip_packages_dir: Path,
        collected_conda_packages_linux64_dir: Path,
        collected_instance_repos_dir: Path,
        python_install_dependency_parser: PythonInstallDependencyParser,
        docker_conda_index: DockerCondaIndex,
    ):
        self._output_dataset_dir = output_dataset_dir
        self._kprize_bundling_assets_dir = kprize_bundling_assets_dir
        self._collected_pip_packages_dir = collected_pip_packages_dir
        self._collected_conda_packages_linux64_dir = collected_conda_packages_linux64_dir
        self._collected_instance_repos_dir = collected_instance_repos_dir
        self._python_install_dependency_parser = python_install_dependency_parser
        self._docker_conda_index = docker_conda_index

    @staticmethod
    def process_task_instance_metadata(
        instances: list[dict],
        landmine_instance_ids:list[str] = [],
        bifurcation_dataset:list[dict] = [],
    ) -> list[dict]:
        """
        Process task instance metadata
        :param task_instance_list:
        :return:
        """
        processed_instances = []
        keyed_bifurcation_instances = group_by_key(bifurcation_dataset, KEY_INSTANCE_ID)
        for instance in instances:
            instance_id = instance[KEY_INSTANCE_ID]
            instance_copy = copy.deepcopy(instance)

            # remove tests with fail outcomes
            instance_copy[FAIL_TO_FAIL] = []
            instance_copy[PASS_TO_FAIL] = []

            # handle landmine issues
            instance_copy[KEY_IS_LANDMINE] = True if instance_id in landmine_instance_ids else False
            if instance_copy[KEY_IS_LANDMINE]:
                print(f"Landmine marked: {instance_id}")
            # add bifurcation
            if keyed_bifurcation_instances.get(instance_id):
                print(f"Bifurcation added: {instance_id}")
                bd = keyed_bifurcation_instances[instance_id][0]
                instance_copy[KEY_BIFURCATION_TEST_PATCH] = bd[KEY_BIFURCATION_TEST_PATCH]
                instance_copy[KEY_BIFURCATION_EXPECTATIONS] = bd[KEY_BIFURCATION_EXPECTATIONS]
            else:
                instance_copy[KEY_BIFURCATION_TEST_PATCH] = ""
                instance_copy[KEY_BIFURCATION_EXPECTATIONS] = ""

            processed_instances.append(instance_copy)

        return processed_instances

    def repackage_collected_datasets_for_kaggle(
        self,
        dataset_id: str,
        split_dirs: list[Path],
        compress: bool = True,
        landmine_instance_ids:list[str] = [],
        bifurcation_dataset:list[dict] = [],
    ):
        """
        Repackage collected datasets for kaggle
        Zips any assets that must stay compressed (tar.bz2, .zip, etc) and renames to .a_zip to avoid kaggle auto-unzipping
        """
        print("Copying collected dependencies to kaggle dataset directory...")

        split_names = list(map(lambda d: d.name, split_dirs))
        print(f" > splits: {split_names}")
        print(f" > bifurcation-instances: {get_key_values(bifurcation_dataset, KEY_INSTANCE_ID)}")
        print(f" > landmine-instances: {landmine_instance_ids}")

        # clear previous kaggle dataset directory
        print("Creating kaggle dataset directory...")
        if self._output_dataset_dir.exists():
            shutil.rmtree(self._output_dataset_dir)
        create_dir_path(self._output_dataset_dir)

        # Copy kprize_setup files
        print("Copying kprize setup files...")
        kprize_setup_dir = create_dir_path(self._output_dataset_dir / "kprize_setup")
        shutil.copy(self._kprize_bundling_assets_dir / "micromamba-linux-64", kprize_setup_dir)
        for file in glob.glob("dist/kprize-*.whl"):
            shutil.copy(file, kprize_setup_dir)
        # Copy swebench pip packages
        copy_selective_files(
            self._collected_pip_packages_dir,
            kprize_setup_dir / "pip_packages",
            specific_files=list(self._python_install_dependency_parser.get_pip_requirements_for_instance("swebench"))
        )

        # Copy split datasets
        for input_split_dir in split_dirs:
            split = input_split_dir.name
            split_instances = read_dataset_from_dir(input_split_dir)
            split_repos = list(group_by_key(split_instances, KEY_REPO).keys())
            split_instance_ids = get_key_values(split_instances, KEY_INSTANCE_ID)
            split_dir = create_dir_path(self._output_dataset_dir / split)

            print(f"Copying split '{split}' to kaggle dataset directory...")
            # Copy repo configs for this split
            copy_selective_files(
                "repo_configs",
                split_dir / "repo_configs",
                specific_files=list(map(lambda repo: f"{repo.split('/')[1]}.json", split_repos)),
                )

            # Copy task instances (as a single parquet file)
            processed_instances = self.process_task_instance_metadata(
                instances=split_instances,
                landmine_instance_ids=landmine_instance_ids,
                bifurcation_dataset=bifurcation_dataset
            )
            convert_task_instance_list_to_parquet(
                processed_instances,
                split_dir / "dataset.parquet"
            )

            dep_parser = self._python_install_dependency_parser
            # Copy pip packages
            copy_selective_files(
                self._collected_pip_packages_dir,
                split_dir / "pip_packages",
                specific_files=dep_parser.get_requirements_for_instances(
                    split_instance_ids,
                    dep_parser.get_pip_requirements_for_instance
                ),
            )

            # Copy conda packages
            copy_selective_files(
                self._collected_conda_packages_linux64_dir,
                split_dir / "conda_packages/linux-64",
                specific_files=dep_parser.get_requirements_for_instances(
                    split_instance_ids,
                    dep_parser.get_conda_requirements_for_instance
                ),
                )
            # Run conda index in docker
            self._docker_conda_index.run_conda_index(split_dir / "conda_packages")

            # Copy instance repos
            copy_selective_dirs(
                self._collected_instance_repos_dir,
                create_dir_path(split_dir / "repos"),
                specific_dirs=list(map(lambda i: f"repo__{i}", split_instance_ids)),
            )

        if compress:
            print("Compressing dataset assets...")
            data_dirs = get_immediate_subdirectories(self._output_dataset_dir)
            for data_dir in data_dirs:
                if data_dir.name in split_names:
                    zip_dir(data_dir, data_dir)
                    # Rename zip file to .a_zip
                    zip_file = data_dir.with_suffix(".zip")
                    zip_file.rename(data_dir.with_suffix(".a_zip"))
                    # Remove uncompressed directory
                    shutil.rmtree(data_dir)

        # Create Kaggle dataset metadata.json
        dataset_title = dataset_id.split("/")[-1].replace("-", " ").title()
        kaggle_metadata = create_dataset_metadata(
            dataset_title=dataset_title,
            dataset_id=dataset_id,
            resources=get_resources_from_dirs([self._output_dataset_dir], "kaggle_dataset/")
        )

        kaggle_metadata_file = self._output_dataset_dir / "dataset-metadata.json"
        kaggle_metadata_file.write_text(jsons(kaggle_metadata))
        print(f"Created kaggle dataset: {dataset_id}")

    def upload_dataset_to_kaggle(self):
        """ Upload kaggle dataset """
        print("Uploading to Kaggle. This may take a while...")
        run_commands([f"kaggle datasets version -p {self._output_dataset_dir} -r zip -m 'New version'"])
        print("Uploading to Kaggle complete.")