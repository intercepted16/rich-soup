"""Models."""

from enum import Enum

from pydantic import BaseModel

from src.common.utils.statistics import Statistics


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST = "list"


class BlockItem(BaseModel):
    type: BlockType

    def as_subclass(self):
        match self.type:
            case BlockType.PARAGRAPH:
                return ParagraphBlock.model_validate(self)
            case BlockType.TABLE:
                return TableBlock.model_validate(self)
            case BlockType.LIST:
                return ListBlock.model_validate(self)
            case _:
                raise ValueError(f"Unknown block type: {self.type}")


class ParagraphBlock(BlockItem):
    type: BlockType = BlockType.PARAGRAPH
    text: str
    bold: bool
    italic: bool
    heading: int  # 0 = normal text, 1 = h1, 2 = h2, etc.
    is_code: bool = False  # Whether this is a code block


class TableBlock(BlockItem):
    type: BlockType = BlockType.TABLE
    rows: list[list[str]]  # 2D list representing table cells


class ListBlock(BlockItem):
    type: BlockType = BlockType.LIST
    items: list[str]  # list of items in the list
    prefix: str  # e.g., "-", "*", "1.", etc.


class BlockArray(BaseModel):
    url: str  # what page this came from
    blocks: list[BlockItem]  # the blocks


class PageMetrics(BaseModel):
    font_size: Statistics
    font_weight: Statistics
