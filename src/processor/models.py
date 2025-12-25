"""Models."""

from enum import Enum

from pydantic import BaseModel

from src.common.utils.statistics import Statistics
from src.blocks.models import BBox

from functools import cached_property
from collections.abc import Iterator


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"


class BlockItem(BaseModel):
    type: BlockType
    bbox: BBox


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


class ImageBlock(BlockItem):
    type: BlockType = BlockType.IMAGE
    src: str  # image source (e.g., base64 or URL)
    alt: str | None = None
    dimensions: tuple[int, int]  # 0 if unknown, not None


class BlockArray(BaseModel):
    """Array of blocks extracted from a page. Exposes list-like interface alongside metadata."""

    url: str  # what page this came from
    blocks: list[BlockItem]  # the blocks

    def __getitem__(self, index: int) -> BlockItem:
        return self.blocks[index]

    def __iter__(self) -> Iterator[BlockItem]:  # pyright: ignore[reportIncompatibleMethodOverride]
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)


class ParsedBlocks(BlockArray):
    """Array of parsed blocks with additional export capabilities.

    A: Iterate directly over blocks

    B: access json representation via .json property

    C: access markdown representation via .markdown property
    """

    @cached_property
    def json(self) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.model_dump_json()

    @cached_property
    def markdown(self) -> str:
        lines: list[str] = []
        for block in self.blocks:
            if isinstance(block, ParagraphBlock):
                if block.is_code:
                    lines.append(f"```\n{block.text}\n```\n\n")
                elif block.heading > 0:
                    prefix = "#" * block.heading
                    lines.append(f"{prefix} {block.text}\n\n")
                elif block.bold:
                    lines.append(f"**{block.text}**\n\n")
                else:
                    lines.append(f"{block.text}\n\n")

            elif isinstance(block, ImageBlock):
                alt_text = block.alt if block.alt else "Image"
                lines.append(
                    f"![{alt_text}]({block.src}) {block.dimensions[0]}x{block.dimensions[1]}\n\n"
                )

            elif isinstance(block, TableBlock):
                if not block.rows:
                    continue
                header = block.rows[0]
                lines.append("| " + " | ".join(header) + " |")
                lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                for row in block.rows[1:]:
                    lines.append("| " + " | ".join(row) + " |")
                lines.append("\n\n")  # two newlines after table

        return "".join(lines)


class PageMetrics(BaseModel):
    font_size: Statistics
    font_weight: Statistics
