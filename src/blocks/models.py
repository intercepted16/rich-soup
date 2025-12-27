"""Raw block models for DOM extraction."""

from enum import Enum

from pydantic import BaseModel

from src.common.models import BBox, Span


# We want to keep block information raw.
# Since it doesn't do any processing, it can only output text or stroke; as that is what is necessary for
# later inference of links, tables, bold, headings, etc.
class BlockType(Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    LINK = "link"
    LIST = "list"


class Block(BaseModel):
    type: BlockType
    bbox: BBox


class TextBlock(Block):
    type: BlockType = BlockType.TEXT
    text: str
    spans: list[Span] | None = None  # Style information for text runs
    font_size: float
    font_weight: float
    font_family: str | None = None
    heading_level: int = 0  # 0 = not a heading, 1-6 = h1-h6
    is_code: bool = False
    is_blockquote: bool = False


class ImageBlock(Block):
    type: BlockType = BlockType.IMAGE
    src: str  # image source (e.g., base64 or URL)
    alt: str | None = None


class TableBlock(Block):
    type: BlockType = BlockType.TABLE
    rows: list[list[str]]  # 2D list representing table cells


class LinkBlock(Block):
    type: BlockType = BlockType.LINK
    href: str  # the URL
    spans: list[Span]  # the link text with style information


class ListBlock(Block):
    type: BlockType = BlockType.LIST
    items: list[list[Span]]  # List of items, each item is a list of spans
    ordered: bool  # True for numbered, False for bulleted
    level: int = 0  # Nesting level for hierarchical lists


class BlockArray(BaseModel):
    url: str  # what page this came from
    blocks: list[Block]  # the blocks
