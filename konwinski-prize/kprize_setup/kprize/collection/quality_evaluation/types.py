from dataclasses import asdict, dataclass
from enum import Enum
from typing import Generic, TypeVar

from kprize.collection.utils import asdict_factory


class TestCoverage(Enum):
    UNSET = "unset"
    UNKNOWN = "unknown"
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class IssueDescriptionQuality(Enum):
    UNSET = "unset"
    UNKNOWN = "unknown"
    UNDERSPECIFIED = "underspecified"
    SUFFICIENT = "sufficient"


class IssueType(Enum):
    UNSET = "unset"
    UNKNOWN = "unknown"
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class TestStatus(Enum):
    # Default value when no evaluation has been performed
    UNSET = "unset"

    # Status could not be determined from available information
    UNKNOWN = "unknown"

    # Test is driven by the issue description and requirements
    ISSUE_DRIVEN = "issue_driven"

    # Test is overfit to implementation details rather than issue description
    OVERFIT_TO_IMPLEMENTATION = "overfit_to_implementation"

    # Test is unrelated to the issue but won't fail the instance
    IRRELEVANT_PASSING = "irrelevant_passing"

    # Test is unrelated to the issue and will fail the instance
    IRRELEVANT_FAILING = "irrelevant_failing"


T = TypeVar("T", bound=Enum)


@dataclass
class EnumWithNotes(Generic[T]):
    value: T
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=asdict_factory)

    @classmethod
    def from_dict(cls, data: dict, enum_type: type[T]) -> "EnumWithNotes[T]":
        return cls(value=enum_type(data["value"]), notes=data["notes"])


@dataclass
class DualEvaluation(Generic[T]):
    ai: EnumWithNotes[T]
    human: EnumWithNotes[T]

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=asdict_factory)

    @classmethod
    def from_dict(cls, data: dict, enum_type: type[T]) -> "DualEvaluation[T]":
        return cls(
            ai=EnumWithNotes.from_dict(data["ai"], enum_type),
            human=EnumWithNotes.from_dict(data["human"], enum_type),
        )


@dataclass
class TestQuality:
    test_file_path: str
    status: DualEvaluation[TestStatus]

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=asdict_factory)

    @classmethod
    def from_dict(cls, data: dict) -> "TestQuality":
        return cls(
            test_file_path=data["test_file_path"],
            status=DualEvaluation.from_dict(data["status"], TestStatus),
        )


@dataclass
class InstanceQuality:
    repo: str
    repo_name: str
    instance_id: str
    source_file_path: str
    pull_request_url: str
    resolved_issue_urls: list[str]
    issue_description: str
    issue_description_summary: str
    issue_description_quality: DualEvaluation[IssueDescriptionQuality]
    issue_type: DualEvaluation[IssueType]
    test_coverage: DualEvaluation[TestCoverage]
    test_qualities: list[TestQuality]

    def to_dict(self) -> dict:
        return asdict(self, dict_factory=asdict_factory)

    @classmethod
    def from_dict(cls, data: dict) -> "InstanceQuality":
        return cls(
            repo=data["repo"],
            repo_name=data["repo_name"],
            instance_id=data["instance_id"],
            source_file_path=data["source_file_path"],
            pull_request_url=data["pull_request_url"],
            resolved_issue_urls=data.get("resolved_issue_urls", []),
            issue_description=data["issue_description"],
            issue_description_summary=data["issue_description_summary"],
            issue_description_quality=DualEvaluation.from_dict(
                data["issue_description_quality"], IssueDescriptionQuality
            ),
            issue_type=DualEvaluation.from_dict(data["issue_type"], IssueType),
            test_coverage=DualEvaluation.from_dict(data["test_coverage"], TestCoverage),
            test_qualities=[TestQuality.from_dict(q) for q in data["test_qualities"]],
        )
