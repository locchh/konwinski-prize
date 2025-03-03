from pathlib import Path

from swebench.harness.constants import (
    MAP_REPO_VERSION_TO_SPECS,
    SPECS_UNIVERSAL,
)
from swebench.harness.log_parsers import (
    MAP_REPO_TO_PARSER,
    parse_log_pytest,
)
from kprize.collection.configs.constants import LOG_PARSER_MAP
from kprize.collection.configs.repo_config import RepoConfig
from kprize.collection.constants import KPRIZE_CONSTANTS


def _get_repo_config_with_specs(repo: str):
    repo_name = repo.split("/")[-1]
    repo_config_path = Path(KPRIZE_CONSTANTS.latest_config_path) / f"{repo_name}.json"
    default_config_path = Path(KPRIZE_CONSTANTS.default_config_path)

    if not repo_config_path.exists() and default_config_path.exists():
        return RepoConfig.from_json(default_config_path)

    repo_config = RepoConfig.from_json(repo_config_path)

    if len(repo_config.specs) > 0:
        return repo_config

    if default_config_path.exists():
        return RepoConfig.from_json(default_config_path)

    raise ValueError(f"No config found for '{repo}' and no default config found.")


def get_latest_specs(repo_config: RepoConfig):
    return max(repo_config.specs.items(), key=lambda x: x[0])


def get_repo_test_spec_from_config(repo: str, version: str):
    """
    Reads a repo's config file and returns the TEST_SPEC for the given version.
    If the version is not found, it falls back to the latest version available.
    """
    repo_config = _get_repo_config_with_specs(repo)

    if version in repo_config.specs:
        return repo_config.specs[version].to_dict()

    _, latest_specs = get_latest_specs(repo_config)

    return latest_specs.to_dict()


def _get_repo_version_test_spec_with_fallback(repo: str, version: str):
    """
    Get TEST_SPEC for given instance
    Some new instances may not have TEST_SPECS, so fallback to "universal" specs or latest version available
    """
    repo_specs = MAP_REPO_VERSION_TO_SPECS.get(repo, None)
    # If repo isn't found use universal spec
    if not repo_specs:
        print(f"No TEST_SPEC found for '{repo}'. Defaulting to SPECS_UNIVERSAL.")
        return SPECS_UNIVERSAL

    # If version isn't found, use the latest version instead
    version_spec = None
    if version:
        version_spec = repo_specs.get(version, None)
    if not version_spec:
        versions = list(repo_specs.keys())
        versions.sort()
        last_version = versions[-1]
        print(f"No TEST_SPEC found for version '{version}'. Defaulting to '{last_version}'.")
        version_spec = repo_specs.get(last_version, None)

    return version_spec


def _get_log_parser_from_config(repo: str):
    repo_config = _get_repo_config_with_specs(repo)

    if repo_config.log_parser not in LOG_PARSER_MAP:
        raise ValueError(f"Unknown log parser: {repo_config.log_parser}")

    return LOG_PARSER_MAP[repo_config.log_parser]


def get_repo_log_parser(repo: str):
    if KPRIZE_CONSTANTS.use_kprize_configs:
        return _get_log_parser_from_config(repo)
    else:
        return MAP_REPO_TO_PARSER.get(repo, parse_log_pytest)


def get_repo_test_spec(repo: str, version: str):
    if KPRIZE_CONSTANTS.use_kprize_configs:
        return get_repo_test_spec_from_config(repo, version)
    else:
        return _get_repo_version_test_spec_with_fallback(repo, version)
