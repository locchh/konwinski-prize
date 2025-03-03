from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from kprize.collection.configs.constants import LOG_PARSER_MAP
from kprize.collection.configs.repo_config import RepoConfig
from kprize.file_utils import strip_hidden_ascii
from kprize.harness.pytest_log_parser import (
    PytestLogInfo,
    PytestLogParser,
    TestInfo,
    TestStatus,
)


@dataclass
class EvalReport:
    instance_id: str
    is_resolved: bool
    report: dict[str, dict[str, list[str]]]


def run_commands(commands: list[str], filepath: Path | None = None):
    if commands is None or len(commands) < 1:
        return

    result = subprocess.run(
        "\n".join(commands),
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
    )

    if filepath:
        with filepath.open("a") as f:
            f.write(strip_hidden_ascii(result.stdout) + "\n")
            f.write(strip_hidden_ascii(result.stderr) + "\n")


def map_report_to_test_infos(report: dict[str, str]) -> PytestLogInfo:
    return PytestLogInfo(
        test_info_map={
            PytestLogInfo._get_test_name_without_file_prefix(test_name): TestInfo(status=TestStatus(status))
            for test_name, status in report.items()
        }
    )


def get_kprize_eval_report(
    test_output_path: Path,
    repo_config_path: Path,
) -> PytestLogInfo | None:
    repo_config = RepoConfig.from_json(repo_config_path)

    if repo_config.log_parser != "parse_log_pytest":
        log_parser = LOG_PARSER_MAP[repo_config.log_parser]
        output = test_output_path.read_text()
        report = log_parser(output)
        log_info = map_report_to_test_infos(report)
    else:
        log_info = PytestLogParser.parse(test_output_path)

    return log_info
