"""Shared utility helpers used across bot modules."""


def safe_float(value, default=0.0) -> float:
    """Safely convert a value to float, handling None and strings."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    return default


def safe_int(value, default=0) -> int:
    """Safely convert a value to int, handling None and strings."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    return default
