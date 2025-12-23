"""Internally exposed API for extracting rich, raw blocks from Playwright."""

from src.blocks.core import extract_blocks
from src.blocks.models import BlockArray, Block, TextBlock, StrokeBlock

__all__ = ["extract_blocks", "BlockArray", "Block", "TextBlock", "StrokeBlock"]
