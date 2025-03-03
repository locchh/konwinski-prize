import os
import subprocess
from pathlib import Path

from kprize.evaluation.utils import run_commands
from kprize.harness.micromamba_manager import MicromambaManager


class KprizeEnvHandler:
    def __init__(self, input_dir, temp_dir: str, verbose: bool = False):
        self.output_dir = Path(os.path.join(temp_dir, 'output'))
        self._kprize_setup_assets_input_dir = Path(os.path.join(input_dir, 'kprize_setup'))
        self._verbose = verbose

    def get_test_patch_path(self, instance_id: str) -> Path:
        return self.output_dir / f"test_patch_{instance_id}.diff"

    def get_model_patch_path(self, instance_id: str) -> Path:
        return self.output_dir / f"model_patch_{instance_id}.diff"

    def get_test_output_path(self, instance_id: str) -> Path:
        return self.output_dir / f"test_output_{instance_id}.txt"

    def get_test_bed_path(self) -> Path:
        """Get a full path for a test bed."""
        return Path("/testbed")

    def setup_micromamba(self):
        # Don't run check=True: `which` succeeds with exit code 1.
        micro_result = subprocess.run('which micromamba', shell=True, capture_output=True)
        mamba_result = subprocess.run('which mamba', shell=True, capture_output=True)
        conda_result = subprocess.run('which conda', shell=True, capture_output=True)
        running_on_kaggle = len([i for i in os.environ if i.lower().startswith('kaggle')]) > 4
        if running_on_kaggle:
            print('Forcing micromamba reinstallation to mitigate issues with older images.')
        elif (micro_result.stdout and micro_result.stdout.decode()) and not (micro_result.stderr and micro_result.stderr.decode()):
            print('Existing micromamba installation found. Skipping micromamba installation.')
            return None
        elif micro_result.returncode not in [0, 1]:
            raise ValueError("subprocess.run('which micromamba' returned unexpected exit code {result.returncode}")
        elif (mamba_result.stdout and mamba_result.stdout.decode()) and not (mamba_result.stderr and mamba_result.stderr.decode()):
            raise ValueError('Existing mamba installation found. Canceling run to avoid micromamba vs mamba conflict. Consider running in a Docker container or using an alias for micromamba, which is untested but is likely to work.')
        elif (conda_result.stdout and conda_result.stdout.decode()) and not (conda_result.stderr and conda_result.stderr.decode()):
            raise ValueError('Existing conda installation found. Canceling run to avoid micromamba vs conda conflict. Consider running in a Docker container or using an alias for micromamba, which is untested but is likely to work.')

        mamba_manager = MicromambaManager(Path("/root/.local/bin"))
        run_commands(
            mamba_manager.install_offline_cmds(
                self._kprize_setup_assets_input_dir,
                "micromamba-linux-64",
            )
        )

        if self._verbose:
            print("Micromamba setup finished.")
