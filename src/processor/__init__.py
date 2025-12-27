"""Process raw, rich blocks into a clean format using many heuristics. Main logic."""

from src.processor.core import extract_blocks
from src.processor.models import BlockArray
from src.common.models import BBox, Span

__all__ = ["extract_blocks", "BlockArray", "BBox", "Span"]
