"""Main entrypoint. Exposes the public API."""

from src.processor.core import extract_blocks
from src.processor.models import ParsedBlocks, BlockType

__all__ = ["extract_blocks", "ParsedBlocks", "BlockType"]
