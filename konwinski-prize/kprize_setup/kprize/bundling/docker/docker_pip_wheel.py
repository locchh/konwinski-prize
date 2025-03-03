from pathlib import Path

import docker

from kprize.constants import KAGGLE_DOCKER_IMAGE_WORKING
from kprize.docker_utils import container_stop_safe


class DockerPipWheel:
    @staticmethod
    def run_pip_wheel(pip_packages_dir: Path):
        """
        Run 'pip wheel' in docker container to generate whl files for collected pip tar.gz packages
        :param pip_packages_dir:
        :return:
        """
        print("Running 'pip wheel' container...")
        client = docker.from_env()
        container = client.containers.run(
            image=KAGGLE_DOCKER_IMAGE_WORKING,
            command='bin/bash -c "pip wheel -w /pip_packages /pip_packages/*.tar.gz"',
            volumes=[
                f"{pip_packages_dir.absolute()}:/pip_packages/",
            ],
            detach=True,
            auto_remove=True,
        )
        result = container.wait()
        exit_code = result['StatusCode']
        if exit_code != 0:
            print(f"'pip wheel' results\n > code: {exit_code}\n > output: {result}\n")

        container_stop_safe(container)

        # delete tar.gz files
        for file in pip_packages_dir.glob("*.tar.gz"):
            file.unlink()