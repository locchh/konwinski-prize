from pathlib import Path


class MicromambaManager:
    def __init__(self, usr_bin_path: Path = Path("/root/.local/bin")):
        self._usr_bin_path = usr_bin_path

    @staticmethod
    def install_cmds():
        return ["curl -L micro.mamba.pm/install.sh | bash"]

    def install_offline_cmds(
            self,
            release_binary_path: Path,
            binary_name: str = "micromamba-linux-64",
    ):
        binary_name = Path(binary_name)
        return [
            f"cp {release_binary_path / binary_name} {self._usr_bin_path}"
            f"chmod +x {self._usr_bin_path / binary_name}",
            f"mv {self._usr_bin_path / binary_name} {self._usr_bin_path / 'micromamba'}"
        ]
