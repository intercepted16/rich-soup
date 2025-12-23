"""Generic statistics utilities."""

from pydantic import BaseModel


class Statistics(BaseModel):
    mean: float
    median: float
    min: float
    max: float
    count: int


def _median(values: list[float]) -> float:
    """Compute the median of a list of values."""
    n = len(values)
    if n == 0:
        return 0.0
    sorted_vals = sorted(values)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    else:
        return sorted_vals[mid]


def _average(values: list[float]) -> float:
    """Compute the mean of a list of values."""
    n = len(values)
    if n == 0:
        return 0.0
    return sum(values) / n


def statistics(values: list[float]) -> Statistics:
    """Compute basic statistics from a list of values.

    Args:
        values (list[float]): The list of values to compute statistics from.

    Returns:
        Statistics: The computed statistics.
    """
    if not values:
        return Statistics(mean=0.0, median=0.0, min=0.0, max=0.0, count=0)

    return Statistics(
        mean=_average(values),
        median=_median(values),
        min=min(values),
        max=max(values),
        count=len(values),
    )
