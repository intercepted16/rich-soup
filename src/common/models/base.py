"""Shared base models for blocks."""

from typing import TypeAlias, Collection, Literal

from pydantic import BaseModel

# Bounding box type: (x0, y0, x1, y1)
BBox: TypeAlias = tuple[float, float, float, float]


def bbox_size(bbox: BBox) -> tuple[float, float]:
    """Calculate width and height from bounding box."""
    x0, y0, x1, y1 = bbox
    w = x1 - x0
    h = y1 - y0
    if w < 0 or h < 0:
        raise ValueError(f"Invalid bbox: {bbox}")
    return w, h


class Span(BaseModel):
    """A span of text with consistent styling."""

    text: str
    formats: Collection[Literal["italic", "bold", "code", "none"] | str] = {"none"}
    font_size: float | None = None
    font_weight: float | None = None
    font_family: str | None = None

    model_config = {"arbitrary_types_allowed": True}
