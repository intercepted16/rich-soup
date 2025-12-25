"""Core."""

from src.blocks.models import (
    BlockArray as RawBlockArray,
    TextBlock as RawTextBlock,
    Block as RawBlock,
    ImageBlock as RawImageBlock,
    TableBlock as RawTableBlock,
)
from src.common.utils.statistics import statistics
from src.processor.models import (
    BlockItem,
    PageMetrics,
    ParagraphBlock,
    ParsedBlocks,
    TableBlock,
    ImageBlock,
)
from src.common.utils.config import config
from typing import overload


def compute_page_metrics(raw_blocks: RawBlockArray) -> PageMetrics:
    """Compute page metrics from raw blocks."""
    font_sizes: list[float] = []
    font_weights: list[float] = []

    for block in raw_blocks.blocks:
        if isinstance(block, RawTextBlock):
            font_sizes.append(block.font_size)
            font_weights.append(block.font_weight)

    return PageMetrics(font_size=statistics(font_sizes), font_weight=statistics(font_weights))


def reading_order(raw_blocks: RawBlockArray) -> RawBlockArray:
    """Reorder blocks by reading order (top-to-bottom, left-to-right)."""
    blocks = sorted(raw_blocks.blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    result: list[RawBlock] = []
    current_line = []
    last_y = None

    for block in blocks:
        y = block.bbox[1]
        if last_y is None or abs(y - last_y) <= config.reading_order_y_tolerance:
            current_line.append(block)
        else:
            result.extend(sorted(current_line, key=lambda b: b.bbox[0]))
            current_line = [block]
        last_y = y

    if current_line:
        result.extend(sorted(current_line, key=lambda b: b.bbox[0]))

    return RawBlockArray(url=raw_blocks.url, blocks=result)


def _determine_heading_level(block: RawTextBlock, metrics: PageMetrics) -> int:
    """Determine heading level from semantic tags or font size."""
    if block.heading_level > 0:
        return block.heading_level

    for level, size_multiplier in sorted(
        config.header_thresholds.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        if block.font_size >= metrics.font_size.mean * size_multiplier:
            return level

    return 0


def _is_text_duplicate(normalized: str, seen_texts: set[str]) -> bool:
    """Check if text is a duplicate or substring of existing text."""
    if normalized in seen_texts:
        return True
    return any(normalized in seen or seen in normalized for seen in seen_texts)


def _hash_table(rows: list[list[str]]) -> str:
    """Create a hash of table content for deduplication."""
    # Normalize and join all table cells into a single string
    normalized_rows = []
    for row in rows:
        normalized_row = [" ".join(cell.lower().split()) for cell in row]
        normalized_rows.append("|".join(normalized_row))
    return "\n".join(normalized_rows)


def _handle_text_block(block: RawTextBlock, metrics: PageMetrics) -> list[ParagraphBlock]:
    """Convert a raw text block into ParagraphBlock(s) using page-level metrics."""
    text = (block.text or "").strip()
    if not text:
        return []

    if block.is_code:
        return [
            ParagraphBlock(
                text=text,
                bold=False,
                italic=False,
                heading=0,
                is_code=True,
                bbox=block.bbox,
            )
        ]

    # Split by double newlines for multiple logical paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    result: list[ParagraphBlock] = []
    for para_text in paragraphs:
        cleaned_text = " ".join(para_text.split())
        if not cleaned_text:
            continue

        # Skip small text
        if block.font_size <= metrics.font_size.mean * config.small_text_threshold:
            continue

        heading = _determine_heading_level(block, metrics)
        bold = block.font_weight >= metrics.font_weight.mean * (1 + config.bold_threshold)

        if block.is_blockquote:
            cleaned_text = f"> {cleaned_text}"

        result.append(
            ParagraphBlock(
                text=cleaned_text,
                bold=bold,
                italic=False,
                heading=heading,
                is_code=False,
                bbox=block.bbox,
            )
        )

    return result


class _DuplicateTracker:
    def __init__(self):
        self.seen_texts: set[str] = set()
        self.text_to_index: dict[str, int] = {}
        self.seen_images: set[str] = set()  # Track image srcs
        self.seen_tables: set[str] = set()  # Track table content hashes

    def is_duplicate(self, normalized: str) -> bool:
        return normalized in self.seen_texts

    def is_substring_duplicate(self, normalized: str) -> bool:
        return _is_text_duplicate(normalized, self.seen_texts)

    def add(self, normalized: str, index: int):
        self.seen_texts.add(normalized)
        self.text_to_index[normalized] = index

    def remove_at_index(self, idx: int):
        for key in self.text_to_index:
            if self.text_to_index[key] > idx:
                self.text_to_index[key] -= 1

    def is_image_duplicate(self, src: str) -> bool:
        """Check if image source has been seen."""
        return src in self.seen_images

    def add_image(self, src: str):
        """Track an image source."""
        self.seen_images.add(src)

    def is_table_duplicate(self, rows: list[list[str]]) -> bool:
        """Check if table content has been seen."""
        table_hash = _hash_table(rows)
        return table_hash in self.seen_tables

    def add_table(self, rows: list[list[str]]):
        """Track a table by hashing its content."""
        table_hash = _hash_table(rows)
        self.seen_tables.add(table_hash)


def _should_skip_paragraph(pb: ParagraphBlock, tracker: _DuplicateTracker) -> bool:
    """Determine if a paragraph should be skipped due to duplication."""
    if not pb.text.strip():
        return True

    if any(pattern in pb.text.lower() for pattern in config.skip_patterns):
        return True

    normalized = " ".join(pb.text.lower().split())

    # Skip exact duplicates for non-headings
    if tracker.is_duplicate(normalized) and pb.heading == 0:
        return True

    # Handle substring duplicates
    if tracker.is_substring_duplicate(normalized):
        if pb.heading == 0:
            return True
        # For headings, remove previous non-heading duplicate if exists
        if normalized in tracker.text_to_index:
            return False  # Will be handled by caller

    return False


def _process_blocks(
    raw_blocks: RawBlockArray,
    metrics: PageMetrics,
    header_threshold: float,
    footer_threshold: float,
) -> list[BlockItem]:
    """Process all raw blocks into parsed blocks."""
    blocks: list[BlockItem] = []
    tracker = _DuplicateTracker()

    for rb in raw_blocks.blocks:
        # Skip header/footer regions
        if rb.bbox[1] < header_threshold or rb.bbox[1] > footer_threshold:
            continue

        match rb:
            case RawTextBlock():
                # Skip narrow blocks (likely sidebar remnants)
                if rb.bbox[2] - rb.bbox[0] < 50:
                    continue

                for pb in _handle_text_block(rb, metrics):
                    if _should_skip_paragraph(pb, tracker):
                        continue

                    normalized = " ".join(pb.text.lower().split())

                    # Handle heading replacing non-heading duplicate
                    if pb.heading > 0 and normalized in tracker.text_to_index:
                        idx = tracker.text_to_index[normalized]
                        if idx < len(blocks) and getattr(blocks[idx], "heading", 0) == 0:
                            del blocks[idx]
                            tracker.remove_at_index(idx)

                    tracker.add(normalized, len(blocks))
                    blocks.append(pb)

            case RawImageBlock():
                if tracker.is_image_duplicate(rb.src):
                    continue
                tracker.add_image(rb.src)
                blocks.append(
                    ImageBlock(
                        src=rb.src,
                        alt="",
                        dimensions=(round(rb.bbox[2] - rb.bbox[0]), round(rb.bbox[3] - rb.bbox[1])),
                        bbox=rb.bbox,
                    )
                )

            case RawTableBlock():
                if tracker.is_table_duplicate(rb.rows):
                    continue
                tracker.add_table(rb.rows)
                blocks.append(
                    TableBlock(
                        rows=rb.rows,
                        bbox=rb.bbox,
                    )
                )

            case RawBlock():
                pass

    return blocks


@overload
def extract_blocks(url: str, /) -> ParsedBlocks: ...


@overload
def extract_blocks(raw_blocks: RawBlockArray, /) -> ParsedBlocks: ...


@overload
def extract_blocks(*, url: str | None = None, raw_blocks: RawBlockArray | None = None) -> ParsedBlocks: ...


def extract_blocks(
    url: str | RawBlockArray | None = None,
    *,
    raw_blocks: RawBlockArray | None = None,
) -> ParsedBlocks:
    """Parse raw blocks into clean blocks using heuristics.

    Can be called as:
    - extract_blocks('https://example.com')
    - extract_blocks(raw_blocks)
    - extract_blocks(url='https://example.com')
    - extract_blocks(raw_blocks=raw_blocks)
    """
    # Resolve input arguments
    if url is not None:
        if isinstance(url, str):
            if raw_blocks is not None:
                raise TypeError("Cannot provide both positional url and keyword raw_blocks")
            from src.blocks.core import extract_raw_blocks

            raw_blocks = extract_raw_blocks(url)
        else:
            if raw_blocks is not None:
                raise TypeError("Cannot provide both positional and keyword raw_blocks")
            raw_blocks = url
    elif raw_blocks is None:
        raise ValueError("Must provide either a URL or raw blocks to extract from.")

    # Reorder blocks by reading order
    raw_blocks = reading_order(raw_blocks)
    metrics = compute_page_metrics(raw_blocks)

    # Calculate header/footer thresholds
    if raw_blocks.blocks:
        max_y = max((b.bbox[3] for b in raw_blocks.blocks), default=0)
        header_threshold = max_y * config.header_threshold
        footer_threshold = max_y * config.footer_threshold
    else:
        header_threshold = footer_threshold = 0

    # Process all blocks
    blocks = _process_blocks(raw_blocks, metrics, header_threshold, footer_threshold)

    return ParsedBlocks(url=raw_blocks.url, blocks=blocks)
