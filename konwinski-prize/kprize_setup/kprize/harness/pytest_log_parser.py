from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from swebench import TestStatus

# ==== test session starts ====
TEST_SESSION_START_REGEX = re.compile(r"===+ test session starts ===+")
# ___ test_name ___
TEST_NAME_HEADER_REGEX = re.compile(r"___+ (.+) ___+")
# --- Captured stdout call ---
CAPTURED_STDOUT_REGEX = re.compile(r"---+ Captured stdout call ---+")
# --- Captured log call ---
CAPTURED_LOG_REGEX = re.compile(r"---+ Captured log call ---+")
# === short test summary info ===
SHORT_SUMMARY_HEADER_REGEX = re.compile(r"===+ short test summary info ===+")


@dataclass
class TestInfo:
    status: TestStatus | None = None
    stdout: str | None = None
    log: str | None = None
    failed_description: str | None = None

    @property
    def test_output(self) -> str | None:
        output_parts = []

        if self.stdout:
            output_parts.append(self.stdout)

        if self.log:
            output_parts.append(self.log)

        return "\n\n".join(output_parts) if output_parts else None


@dataclass
class PytestLogInfo:
    test_info_map: dict[str, TestInfo] = field(default_factory=dict)

    @staticmethod
    def _get_test_name_without_file_prefix(test_name: str) -> str | None:
        test_name_parts = test_name.split("::")

        if len(test_name_parts) > 1:
            return ".".join(test_name_parts[1:])

        return None

    def add_test_info(self, test_name: str, test_info: TestInfo):
        self.test_info_map[test_name] = test_info

    def remove_test_info(self, test_name: str):
        self.test_info_map.pop(test_name, None)

    def get_test_info(self, test_name: str | None) -> TestInfo | None:
        return self.test_info_map.get(test_name, None) if test_name is not None else None

    def update_test_info(self, test_name: str, test_info: TestInfo):
        cur_test_info = self.get_test_info(test_name)
        matching_test_name = None
        # Check if test info exists for test_name with file prefix
        if cur_test_info is None:
            matching_test_name = self._get_test_name_without_file_prefix(test_name)
            cur_test_info = self.get_test_info(matching_test_name)
        # Add new test info if it doesn't exist for test_name
        if cur_test_info is None:
            self.add_test_info(test_name, test_info)
            return
        # Update existing test info
        cur_test_info.status = test_info.status or cur_test_info.status
        cur_test_info.stdout = test_info.stdout or cur_test_info.stdout
        cur_test_info.log = test_info.log or cur_test_info.log
        cur_test_info.failed_description = test_info.failed_description or cur_test_info.failed_description

        # update test name to current test name if it was matched with a test name without file prefix
        if matching_test_name:
            self.add_test_info(test_name, cur_test_info)
            self.remove_test_info(matching_test_name)

    @property
    def test_status_map(self):
        return {test_name: test_info.status for test_name, test_info in self.test_info_map.items()}

    @property
    def stdout_call_map(self):
        return {test_name: test_info.stdout for test_name, test_info in self.test_info_map.items()}

    @property
    def log_call_map(self):
        return {test_name: test_info.log for test_name, test_info in self.test_info_map.items()}

    @property
    def failed_description_map(self):
        return {test_name: test_info.failed_description for test_name, test_info in self.test_info_map.items()}


@dataclass
class ParsingStatus:
    test_session_started: bool = False
    short_summary_started: bool = False
    is_reading_stdout: bool = False
    is_reading_log: bool = False
    test_name: str | None = None
    test_info: TestInfo | None = None

    def start_reading_stdout(self):
        self.is_reading_log = False

        if self.test_info is None:
            return

        self.is_reading_stdout = True
        self.test_info.stdout = self.test_info.stdout or ""

    def start_reading_log(self):
        self.is_reading_stdout = False

        if self.test_info is None:
            return

        self.is_reading_log = True
        self.test_info.log = self.test_info.log or ""

    def start_new_test(self, test_name: str):
        self.test_name = test_name
        self.test_info = TestInfo()
        self.is_reading_stdout = False
        self.is_reading_log = False

    def start_short_summary(self):
        self.short_summary_started = True
        self.is_reading_log = False
        self.is_reading_stdout = False


class PytestLogParser:
    """Parser for test logs generated with PyTest framework"""

    @staticmethod
    def _parse_test_session(line: str, status: ParsingStatus, log_info: PytestLogInfo) -> None:
        """Parse a line during the test session phase."""
        if TEST_NAME_HEADER_REGEX.match(line):
            if status.test_name and status.test_info:
                log_info.add_test_info(status.test_name, status.test_info)

            match = TEST_NAME_HEADER_REGEX.match(line)
            if match:
                status.start_new_test(match.group(1))

            return

        if CAPTURED_STDOUT_REGEX.match(line):
            status.start_reading_stdout()
            return

        if CAPTURED_LOG_REGEX.match(line):
            status.start_reading_log()
            return

        if SHORT_SUMMARY_HEADER_REGEX.match(line):
            if status.test_name and status.test_info:
                log_info.add_test_info(status.test_name, status.test_info)
            status.start_short_summary()
            return

        if status.is_reading_stdout and status.test_info and status.test_info.stdout is not None:
            status.test_info.stdout += line
            return

        if status.is_reading_log and status.test_info and status.test_info.log is not None:
            status.test_info.log += line
            return

    @staticmethod
    def _parse_short_summary(line: str, log_info: PytestLogInfo) -> None:
        """Parse a line during the short summary phase."""
        if not any(line.startswith(x.value) for x in TestStatus):
            return

        failed_description = None

        if line.startswith(TestStatus.FAILED.value):
            parts = line.split(" - ")
            if len(parts) > 1:
                failed_description = parts[-1]
                line = " - ".join(parts[:-1])

        test_case = line.split(maxsplit=1)

        if len(test_case) <= 1:
            return

        test_status = test_case[0].strip().strip(":")
        test_name = test_case[1].strip()

        log_info.update_test_info(
            test_name,
            TestInfo(
                status=TestStatus(test_status),
                failed_description=failed_description,
            ),
        )

    @staticmethod
    def parse(log_file: Path) -> PytestLogInfo:
        """
        Parse test logs

        Args:
            log_file (Path): path to log file
        Returns:
            PytestLogInfo: Object containing parsed test information
        """
        log_info = PytestLogInfo()
        status = ParsingStatus()

        with open(log_file) as file:
            for line in file:
                # Skip lines before test session starts
                if not status.test_session_started:
                    if TEST_SESSION_START_REGEX.match(line):
                        status.test_session_started = True
                    continue

                if not status.short_summary_started:
                    PytestLogParser._parse_test_session(line, status, log_info)
                else:
                    PytestLogParser._parse_short_summary(line, log_info)

        return log_info
