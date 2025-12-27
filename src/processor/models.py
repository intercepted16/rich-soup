"""Processed block models."""

from enum import Enum

from pydantic import BaseModel

from src.common.utils.statistics import Statistics
from src.common.models import BBox, Span

from functools import cached_property
from collections.abc import Iterator
from src.common.utils.logger import logger


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    LINK = "link"
    LIST = "list"


class BlockItem(BaseModel):
    type: BlockType
    bbox: BBox


class ParagraphBlock(BlockItem):
    type: BlockType = BlockType.PARAGRAPH
    spans: list[Span]  # Array of spans with individual styling
    heading: int  # 0 = normal text, 1 = h1, 2 = h2, etc.
    is_code: bool = False  # Whether this is a code block

    @property
    def text(self) -> str:
        """Get concatenated text from all spans."""
        return "".join(span.text for span in self.spans)


class TableBlock(BlockItem):
    type: BlockType = BlockType.TABLE
    rows: list[list[str]]  # 2D list representing table cells


class ImageBlock(BlockItem):
    type: BlockType = BlockType.IMAGE
    src: str  # image source (e.g., base64 or URL)
    alt: str | None = None
    dimensions: tuple[int, int]  # 0 if unknown, not None


class LinkBlock(BlockItem):
    type: BlockType = BlockType.LINK
    href: str  # the URL
    spans: list[Span]  # the link text with style information


class ListBlock(BlockItem):
    type: BlockType = BlockType.LIST
    items: list[list[Span]]  # List items with style information
    ordered: bool  # True for numbered, False for bulleted
    level: int = 0  # Nesting level for hierarchical lists


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

    def _format_spans(self, spans: list[Span]) -> str:
        """Format a list of spans into markdown text with proper spacing."""
        if not spans:
            return ""

        result = ""
        for i, span in enumerate(spans):
            text = span.text

            # Apply formatting
            for fmt in span.formats:
                match fmt:
                    case "bold":
                        text = f"**{text}**"
                    case "italic":
                        text = f"*{text}*"
                    case "code":
                        text = f"`{text}`"
                    case "none":
                        pass
                    case _:
                        logger.warning(f"Unknown format: {fmt}")

            # Add space before this span if needed
            if i > 0 and result and not result[-1].isspace():
                # Don't add space if current text starts with punctuation
                if text and text[0] not in ".,!?;:)]}":
                    result += " "

            result += text

        return result

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
                else:
                    span_md = self._format_spans(block.spans)
                    lines.append(f"{span_md}\n\n")

            elif isinstance(block, ImageBlock):
                alt_text = block.alt if block.alt else "Image"
                lines.append(f"![{alt_text}]({block.src}) {block.dimensions[0]}x{block.dimensions[1]}\n\n")

            elif isinstance(block, TableBlock):
                if not block.rows or len(block.rows) == 0:
                    continue

                # Find the maximum number of columns across all rows
                max_cols = max(len(row) for row in block.rows)
                if max_cols == 0:
                    continue

                # Normalize rows to have the same number of columns
                normalized_rows: list[list[str]] = []
                for row in block.rows:
                    # Pad with empty strings if row is shorter
                    normalized_row = row + [""] * (max_cols - len(row))
                    normalized_rows.append(normalized_row)

                # First row is header
                header: list[str] = normalized_rows[0]
                lines.append("| " + " | ".join(header) + " |\n")
                lines.append("| " + " | ".join(["---"] * len(header)) + " |\n")

                # Remaining rows are data
                for row in normalized_rows[1:]:
                    lines.append("| " + " | ".join(row) + " |\n")
                lines.append("\n")  # blank line after table

            elif isinstance(block, LinkBlock):
                span_md = self._format_spans(block.spans)
                lines.append(f"[{span_md}]({block.href})\n\n")

            elif isinstance(block, ListBlock):
                for i, item_spans in enumerate(block.items):
                    item_text = self._format_spans(item_spans)
                    prefix = "  " * block.level  # Indentation for nested lists
                    if block.ordered:
                        lines.append(f"{prefix}{i + 1}. {item_text}\n")
                    else:
                        lines.append(f"{prefix}- {item_text}\n")
                lines.append("\n")  # blank line after list

        return "".join(lines)


class PageMetrics(BaseModel):
    font_size: Statistics
    font_weight: Statistics
