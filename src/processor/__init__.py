"""Process raw, rich blocks into a clean format using many heuristics. Main logic."""

from src.processor.core import parse_blocks
from src.processor.models import BlockArray

__all__ = ["parse_blocks", "BlockArray"]
