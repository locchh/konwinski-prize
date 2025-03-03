import json
import os
import re
import urllib.request
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Optional, Tuple

import requests

from kprize.constants import KEY_INSTANCE_ID

WHL_DOWNLOAD_REGEX = re.compile(r"\w*Downloading (.+\.whl)")
WHL_CACHED_REGEX = re.compile(r"\w*Using cached (.+\.whl)")
TAR_GZ_DOWNLOAD_REGEX = re.compile(r"\w*Downloading (.+\.tar\.gz)")

class DownloadStatus(Enum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILURE = "FAILURE"

def get_download_pip_dep_from_line(line: str) -> str:
    """
    Extracts the whl file from the download line

    Args:
        line (str): line from the log
    Returns:
        str: whl file name
    """
    match = WHL_DOWNLOAD_REGEX.search(line)
    if match:
        return match.group(1)
    match = TAR_GZ_DOWNLOAD_REGEX.search(line)
    if match:
        return match.group(1)
    match = WHL_CACHED_REGEX.search(line)
    if match:
        return match.group(1)
    return None


def parse_pip_dependencies(log: str) -> list[str]:
    """
    Parser for pip dependencies downloaded as part of the setup (whl files)

    Args:
        log (str): log content of environment and repo setup
    Returns:
        list: list of whls/tar.gz downloaded in the log
    """
    pip_dependency_set = set()
    escapes = "".join(chr(char) for char in range(1, 32))
    translator = str.maketrans("", "", escapes)

    for line in log.split("\n"):
        line = re.sub(r"\[(\d+)m", "", line)
        line = line.translate(translator)
        # print(line)
        dep = get_download_pip_dep_from_line(line)
        if dep:
            pip_dependency_set.add(dep)
    return sorted(pip_dependency_set)


def parse_conda_package_names_from_table(table_output: str) -> list[str]:
    """
    Parses the package names from the given table output.

    Args:
        table_output (str): The table output containing package information.
    Returns:
        list: List of package names.
    """
    package_names = []
    lines = table_output.split('\n')
    for line in lines:
        match = re.match(r"^\s*([^\s]+)\s*\|", line)
        if match:
            package_names.append(match.group(1))
    return package_names


def parse_conda_install_dependencies(output: str) -> dict:
    """
    Parses the given output and returns a dictionary with the first word as the key
    and the second word as the value.

    Args:
        output (str): The output containing package information.
    Returns:
        dict: Dictionary with the first word as the key and the second word as the value.
    """
    result = {}
    lines = output.strip().split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            key = parts[0]
            value = parts[1]
            result[key] = value
    return result


def parse_conda_dependencies(log: str) -> set[str]:
    """
    Parser for conda dependencies downloaded as part of the setup

    Args:
        log (str): log content of environment and repo setup
    Returns:
        list: list of conda packages downloaded in the log
    """
    start_conda_dependencies_installed = "The following NEW packages will be INSTALLED:"
    end_conda_dependencies = "Downloading and Extracting Packages:"

    index_start_installed = log.find(start_conda_dependencies_installed)
    if index_start_installed > 0:
        index_start_installed = index_start_installed + len(start_conda_dependencies_installed)
    index_end_installed = log.find(end_conda_dependencies)

    if index_start_installed > 0 and index_end_installed > 0:
        conda_install_output = log[index_start_installed:index_end_installed]
        installed_packages = parse_conda_install_dependencies(conda_install_output)
    else:
        print("Unable to find conda install dependencies in the log")
        installed_packages = {}

    # return set of package urls
    return set(installed_packages.values())


def get_pypi_package_from_whl(whl: str):
    return whl.split("-")[0]


def get_pypi_package_url(package_whl: str):
    return f"https://pypi.debian.net/{get_pypi_package_from_whl(package_whl)}/{package_whl}"


def is_url_valid(url: str) -> bool:
    """ Checks if the given URL is valid."""
    try:
        code = urllib.request.urlopen(url).getcode()
        return code == 200
    except:
        return False


# Url checks are slow, so cache the results
@cache
def get_conda_forge_package_url(package_id: str) -> Optional[str]:
    """ Constructs the download URL for a conda-forge package."""

    package_path = package_id.replace("::", "/")
    url_without_extension = f"https://conda.anaconda.org/{package_path}"
    _conda_url = f"{url_without_extension}.conda"
    if is_url_valid(_conda_url):
        return _conda_url
    _tar_url = f"{url_without_extension}.tar.bz2"
    if is_url_valid(_tar_url):
        return _tar_url
    return None


def get_channels_block_from_environment_yml(yml: str) -> str:
    """ Parses the environment.yml and returns the list of channels."""
    # example
    # channels:
    #   - conda-forge
    # dependencies:
    # get the channels block
    return "channels:" + yml.split("channels:")[1].split("dependencies:")[0]


def get_dependencies_from_setup_logs(setup_log_path: Path) -> Tuple[dict, dict]:
    """
    Parses PIP and Conda dependencies from setup log

    :param setup_log_path:
    :return: [pip_packages_map, conda_packages_map]
    """

    # check if setup log file exists
    if not os.path.exists(setup_log_path):
        print(f"Setup log file does not exist: {setup_log_path}")
        return {}, {}

    # Parse setup logs for dependencies
    with open(setup_log_path, "r") as f:
        log = f.read()
        pip_dependencies = parse_pip_dependencies(log)
        conda_dependencies = parse_conda_dependencies(log)

    # Create package maps { package_name: package_url }
    pip_package_map = {p: get_pypi_package_url(p) for p in pip_dependencies}
    conda_package_map = {}
    for p in conda_dependencies:
        purl = get_conda_forge_package_url(p)
        if purl:
            conda_package_map[purl.split('/')[-1]] = purl
        else:
            print(f"Failed to get conda-forge package url for: {p}")

    return pip_package_map, conda_package_map

class PythonInstallDependencyParser:
    def __init__(
            self,
            install_logs_dir: Path,
            collected_pip_packages_dir: Path,
            collected_conda_packages_dir: Path,
            collected_requirements_log_dir: Path,
            collected_failures_dir: Path,
    ):
        self._install_logs_dir = install_logs_dir
        self._collected_pip_packages_dir = collected_pip_packages_dir
        self._collected_conda_packages_dir= collected_conda_packages_dir
        self._collected_requirements_log_dir = collected_requirements_log_dir
        self._collected_failures_dir = collected_failures_dir

    @staticmethod
    def get_pip_requirements_file_name(instance_id: str) -> str:
        return f"{instance_id}-pip-requirements.txt"

    @staticmethod
    def get_conda_requirements_file_name(instance_id: str) -> str:
        return f"{instance_id}-conda-requirements.txt"

    def get_pip_requirements_path(self, instance_id: str) -> Path:
        return self._collected_requirements_log_dir / self.get_pip_requirements_file_name(instance_id)

    def get_conda_requirements_path(self, instance_id: str) -> Path:
        return self._collected_requirements_log_dir / self.get_conda_requirements_file_name(instance_id)

    def get_pip_requirements_for_instance(self, instance_id: str) -> set[str]:
        """Get PIP requirements for instance"""
        pip_requirements_path = self.get_pip_requirements_path(instance_id)
        pip_requirements = pip_requirements_path.read_text().split("\n") if pip_requirements_path.exists() else []
        for req in pip_requirements:
            if req.endswith(".tar.gz"):
                # locate the corresponding whl file
                matching_whls = list(self._collected_pip_packages_dir.glob(f"{req.replace('.tar.gz', '')}*.whl"))
                if len(matching_whls) > 0:
                    for whl_file in matching_whls:
                        print(f"Adding matching whl file: {whl_file.name} for {req}")
                        pip_requirements.append(whl_file.name)
        return set(pip_requirements)

    def get_conda_requirements_for_instance(self, instance_id: str) -> set[str]:
        """Get CONDA requirements for instance"""
        conda_requirements_path = self.get_conda_requirements_path(instance_id)
        conda_requirements = conda_requirements_path.read_text().split("\n") if conda_requirements_path.exists() else []
        return set(conda_requirements)

    @staticmethod
    def get_requirements_for_instances(instance_ids: list[str], get_requirements_func) -> list[str]:
        """Get PIP requirements for instances"""
        requirements = set()
        for instance_id in instance_ids:
            requirements |= get_requirements_func(instance_id)
        return requirements

    def download_packages(self, package_to_url_map: dict, output_dir: Path):
        """
        Download packages from package_to_url_map to output_dir
        :param package_to_url_map:
        :param output_dir:
        :return:
        """
        failed_downloads_path = self._collected_failures_dir / "failed_downloads.jsonl"
        skipped_packages = []
        for package in package_to_url_map.keys():
            output_file = output_dir / package
            if output_file.exists():
                skipped_packages.append(package)
                continue
            print(f"Downloading package: {package}")
            # download package
            url = package_to_url_map[package]
            response = requests.get(url)
            if response.status_code != 200:
                failed = {"package": package, "url": url}
                print(f"Failed to download package: {json.dumps(failed)}")
                with failed_downloads_path.open("a") as f:
                    f.write(f'{json.dumps(failed)}\n')
                continue
            # save package
            output_file.write_bytes(response.content)
        if len(skipped_packages) > 0:
            print(f"Skipped existing packages: {skipped_packages}")

    def download_packages_from_setup_log(self, instance_id: str, setup_log_path: Path) -> DownloadStatus:
        pip_requirements_file = self.get_pip_requirements_path(instance_id)
        conda_requirements_file = self.get_conda_requirements_path(instance_id)
        # Skip if packages have already been downloaded
        if pip_requirements_file.exists() and conda_requirements_file.exists():
            return DownloadStatus.SKIPPED
        if setup_log_path.exists():
            print(f"\nGetting dependencies for '{instance_id}'")
            # Parse dependencies from logs
            pip_packages, conda_packages = get_dependencies_from_setup_logs(setup_log_path)

            # download dependencies
            self.download_packages(pip_packages, self._collected_pip_packages_dir)
            self.download_packages(conda_packages, self._collected_conda_packages_dir)

            # create whl requirements file for task instance
            conda_requirements_file.write_text("\n".join(conda_packages))
            pip_requirements_file.write_text("\n".join(pip_packages))
            return DownloadStatus.SUCCESS
        else:
            print(f"\nERROR: Setup log not found {setup_log_path}")
            return DownloadStatus.FAILURE

    def download_packages_from_setup_logs(self, instances: list[dict]):
        """
        Download PIP and Conda dependencies from setup logs
        """
        skipped_instances = []
        error_instances = []
        for idx, instance in enumerate(instances):
            instance_id = instance[KEY_INSTANCE_ID]
            setup_log_path = self._install_logs_dir / f"{instance_id}/setup_output.txt"
            status = self.download_packages_from_setup_log(instance_id, setup_log_path)
            if status == DownloadStatus.SKIPPED:
                skipped_instances.append(instance_id)
            elif status == DownloadStatus.FAILURE:
                error_instances.append(instance_id)
        if len(skipped_instances) > 0:
            print(f"Skipped {len(skipped_instances)} instances with existing requirement logs:\n{skipped_instances}")
        if len(error_instances) > 0:
            print(f"Missing setup logs for {len(error_instances)} instances:\n{error_instances}")
