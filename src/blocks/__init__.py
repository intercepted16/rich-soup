"""Internally exposed API for extracting rich, raw blocks from Playwright."""

from src.blocks.core import extract_raw_blocks
from src.blocks.models import BlockArray, Block, TextBlock

__all__ = [
    "extract_raw_blocks",
    "BlockArray",
    "Block",
    "TextBlock",
]
