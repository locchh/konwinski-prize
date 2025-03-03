import docker
from pathlib import Path

from kprize.docker_utils import container_stop_safe, build_image_if_not_exists


class DockerCondaIndex:
    def run_conda_index(self, conda_packages_dir: Path):
        """
        Run 'conda build' in docker container to generate a conda channel for the collected conda packages
        :param conda_packages_dir:
        :return:
        """
        print(f"Running 'conda index' container for {conda_packages_dir}...")
        client = docker.from_env()

        image_tag = "bundle-kaggle-conda-index:latest"
        build_image_if_not_exists(
            path="swebench/kprize/bundling/assets/",
            dockerfile = "Dockerfile_conda_index",
            tag=image_tag,
        )
        container = client.containers.run(
            image=image_tag,
            command='bin/bash -c "conda index conda_packages/"',
            volumes=[
                f"{conda_packages_dir.absolute()}:/conda_packages/",
            ],
            detach=True,
            auto_remove=True,
        )
        result = container.wait()
        exit_code = result['StatusCode']
        if exit_code != 0:
            print(f"'conda build' results\n > code: {exit_code}\n > output: {result}\n")

        container_stop_safe(container)

        # Remove dependency version restrictions from conda packages
        print("Removing dependency version restrictions from conda packages...")
        self.remove_conda_dependencies_version_restrictions(conda_packages_dir)


    @staticmethod
    def remove_conda_dependencies_version_restrictions(conda_packages_dir: Path):
        """
        Remove dependency version restrictions from conda packages

        This is necessary for offline conda installations, as the version restrictions will cause conda to fail
        Conda is able to auto-resolve version conflicts in online mode, but not offline

        :param conda_packages_dir: Path to (indexed) conda packages directory
        """
        for file in conda_packages_dir.glob("**/*.json"):
            with open(file, "r") as f:
                data = f.read()
                data = data.replace(',<1.3.0a0', '')

            with open(file, "w") as f:
                f.write(data)