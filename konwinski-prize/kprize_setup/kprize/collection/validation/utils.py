from kprize.collection.kprize_global_state import KprizeGlobalState
from kprize.collection.validation.failure_mode import FailureMode
from kprize.collection.validation.instance_validation_stats import (
    InstanceValidationStats,
)


def update_unknown_instance_state(
    instance_id: str, failure_mode: FailureMode, state: KprizeGlobalState
) -> None:
    instance_state: InstanceValidationStats | None = state.get(instance_id)  # type: ignore
    new_stats = InstanceValidationStats(failure_mode=failure_mode)

    if instance_state is None:
        print(f"Instance {instance_id} not found in state.")
        state.set(instance_id, new_stats)
        return

    if instance_state.failure_mode == FailureMode.UNKNOWN:
        state.set(instance_id, new_stats)
