"""Models."""

from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel


# We want to keep block information raw.
# Since it doesn't do any processing, it can only output text or stroke; as that is what is necessary for later inference of links, tables, bold, headings, etc.
class BlockType(Enum):
    TEXT = "text"
    IMAGE = "image"


BBox: TypeAlias = tuple[float, float, float, float]  # (x0, y0, x1, y1)


class Block(BaseModel):
    type: BlockType
    bbox: BBox


class TextBlock(Block):
    type: BlockType = BlockType.TEXT
    text: str
    font_size: float
    font_weight: float
    font_family: str | None = None
    heading_level: int = 0  # 0 = not a heading, 1-6 = h1-h6
    is_code: bool = False
    is_list: bool = False
    is_blockquote: bool = False


class ImageBlock(Block):
    type: BlockType = BlockType.IMAGE
    src: str  # image source (e.g., base64 or URL)


class TableBlock(Block):
    type: BlockType = BlockType.TEXT
    rows: list[list[str]]  # 2D list representing table cells


class BlockArray(BaseModel):
    url: str  # what page this came from
    blocks: list[Block]  # the blocks
