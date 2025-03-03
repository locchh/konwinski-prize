import os

from kprize.os_utils import get_boolean_env_var


# FIXME: This should probably be moved to another place like DataPathHandler
class KPrizeConstants:
    def __init__(
        self,
        use_kprize_configs: bool = False,
        latest_config_path: str = "repo_configs",
        current_quarter: str = "24_q3",
    ):
        self.use_kprize_configs = use_kprize_configs
        self.latest_config_path = latest_config_path
        self.current_quarter = current_quarter

    @property
    def default_config_path(self):
        return f"{self.latest_config_path}/_default.json"

    @property
    def quality_evaluation_path(self):
        return f"logs/quality/{self.current_quarter}"


KPRIZE_CONSTANTS = KPrizeConstants(
    use_kprize_configs=get_boolean_env_var("USE_KPRIZE_CONFIGS", False),
    latest_config_path=os.getenv("LATEST_CONFIG_PATH", "repo_configs"),
    current_quarter=os.getenv("CURRENT_QUARTER", "24_q3"),
)
