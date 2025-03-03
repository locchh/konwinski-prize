from dataclasses import dataclass, field
from typing import Any

from kprize.collection.validation.failure_mode import FailureMode


@dataclass(frozen=True)
class InstanceValidationStats:
    failure_mode: FailureMode = field(default=FailureMode.UNKNOWN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_mode": self.failure_mode.value
        }
