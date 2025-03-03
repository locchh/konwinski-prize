import json
from contextlib import contextmanager
from enum import Enum
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Callable


def with_state_lock(func):
    """Decorator that wraps a method with the state lock context manager."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._state_lock:
            return func(self, *args, **kwargs)

    return wrapper


class KprizeGlobalState:
    """
    Thread-safe singleton class for managing global state with support for
    atomic operations and transaction-like updates.

    The purpose of this class is to provide us the ability to track global state
    without having to make major modifications to the forked codebase.
    """

    _instance = None
    _lock = Lock()

    def __init__(self):
        if not hasattr(self, "_state"):
            self._state: dict[str, Any] = {}
            self._state_lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @contextmanager
    def atomic_update(self):
        """
        Context manager for atomic updates to multiple state values.
        Changes are applied only if no exceptions occur within the context.
        """
        temp_state = self._state.copy()
        try:
            yield temp_state
            with self._state_lock:
                self._state.update(temp_state)
        except Exception as e:
            # Rollback by not applying changes
            raise e

    @with_state_lock
    def transform(
        self, transform_fn: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        """
        Thread-safe update of state using a function that takes the current state and returns new state.

        Args:
            transform_fn: Function that takes current state dict and returns updated state dict
        """
        new_state = transform_fn(self._state.copy())
        self._state.clear()
        self._state.update(new_state)

    @with_state_lock
    def set(self, key: str | list[str], value: Any) -> None:
        """
        Thread-safe setter for state value(s).

        Args:
            key: Either a single key string or list of key strings to set
            value: Value to set for the key(s)
        """
        if isinstance(key, str):
            self._state[key] = value
        else:
            for k in key:
                self._state[k] = value

    @with_state_lock
    def get(self, key: str, default: Any = None) -> Any | None:
        """Thread-safe getter for a single state value."""
        return self._state.get(key, default)

    @with_state_lock
    def delete(self, key: str) -> None:
        """Thread-safe deletion of a state value."""
        self._state.pop(key, None)

    @with_state_lock
    def clear(self) -> None:
        """Thread-safe clearing of all state."""
        self._state.clear()

    @with_state_lock
    def get_all(self) -> dict[str, Any]:
        """Thread-safe getter for entire state dictionary."""
        return self._state.copy()

    def _convert_value(self, v: Any) -> Any:
        match v:
            case dict():
                return {k: self._convert_value(v) for k, v in v.items()}
            case list() | tuple():
                return [self._convert_value(x) for x in v]
            case _ if isinstance(v, Enum):
                return v.value
            case _ if hasattr(v, "to_dict"):
                return v.to_dict()
            case _ if hasattr(v, "__dict__"):
                return self._convert_value(v.__dict__)
            case _:
                return v

    def _to_dict(self) -> dict[str, Any]:
        return self._convert_value(self._state)

    @with_state_lock
    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._to_dict(), indent=4))
