import os


def get_boolean_env_var(var_name: str, default: bool | None = None) -> bool | None:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes")
