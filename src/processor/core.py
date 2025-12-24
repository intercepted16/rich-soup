"""Core."""

from src.blocks.models import (
    Block as RawBlock,
)
from src.blocks.models import (
    BlockArray as RawBlockArray,
)
from src.blocks.models import (
    TextBlock as RawTextBlock,
    TableBlock as RawTableBlock,
    ImageBlock as RawImageBlock,
)
from src.common.utils.statistics import statistics
from src.processor.models import (
    BlockArray,
    BlockItem,
    PageMetrics,
    ParagraphBlock,
    TableBlock,
)

from src.common.utils.logger import logger

BOLD_THRESHOLD = 0.350


def compute_page_metrics(raw_blocks: RawBlockArray) -> PageMetrics:
    """Compute page metrics from raw blocks.

    Args:
        raw_blocks (RawBlockArray): The raw blocks to compute metrics from.

    Returns:
        PageMetrics: The computed page metrics.
    """
    font_sizes: list[float] = []
    font_weights: list[float] = []
    for block in raw_blocks.blocks:
        if isinstance(block, RawTextBlock):
            font_sizes.append(block.font_size)
            font_weights.append(block.font_weight)

    return PageMetrics(
        font_size=statistics(font_sizes), font_weight=statistics(font_weights)
    )


def reading_order(raw_blocks: RawBlockArray, y_tol: float = 5.0) -> RawBlockArray:
    """Reorder raw blocks based on reading order (top-to-bottom, left-to-right).

    Args:
        raw_blocks (RawBlockArray): The blocks to reorder.
        y_tol (float): Vertical tolerance in pixels for considering blocks on the same line.

    Returns:
        RawBlockArray: The reordered blocks.
    """
    blocks = sorted(raw_blocks.blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    result: list[RawBlock] = []
    current_line: list[RawBlock] = []
    last_y: float | None = None

    for block in blocks:
        y = block.bbox[1]
        if last_y is None or abs(y - last_y) <= y_tol:
            current_line.append(block)
        else:
            current_line.sort(key=lambda b: b.bbox[0])
            result.extend(current_line)
            current_line = [block]
        last_y = y

    if current_line:
        current_line.sort(key=lambda b: b.bbox[0])
        result.extend(current_line)

    return RawBlockArray(url=raw_blocks.url, blocks=result)


def _handle_text_block(
    block: RawTextBlock, metrics: PageMetrics
) -> list[ParagraphBlock]:
    """Convert a raw text block into ParagraphBlock(s) using page-level metrics.

    Uses semantic heading levels from HTML tags when available, with font-size
    fallback. Splits text by double newlines to handle cases where a single DOM
    element contains multiple logical paragraphs.
    """
    text = block.text or ""
    text = text.strip()

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
            )
        ]

    # Split by double newlines (paragraph breaks) but preserve single newlines within paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        return []

    result: list[ParagraphBlock] = []

    for para_text in paragraphs:
        # Clean up the text: normalize whitespace
        cleaned_text = " ".join(para_text.split())

        if not cleaned_text:
            continue

        if block.font_size <= metrics.font_size.mean * 0.65:
            continue

        if block.heading_level > 0:
            heading = block.heading_level
        elif block.font_size >= metrics.font_size.median * 1.5:
            heading = 1  # Very large text → h1
        elif block.font_size >= metrics.font_size.median * 1.25:
            heading = 2  # Large text → h2
        elif (
            block.font_size >= metrics.font_size.median * 1.1
            and block.font_weight >= 600
        ):
            heading = 3  # Slightly larger + bold → h3
        else:
            heading = 0

        bold = block.font_weight >= metrics.font_weight.mean * (1 + BOLD_THRESHOLD)

        if block.is_blockquote:
            cleaned_text = f"> {cleaned_text}"

        result.append(
            ParagraphBlock(
                text=cleaned_text,
                bold=bold,
                italic=False,  # TODO: implement italic detection
                heading=heading,
                is_code=False,
            )
        )

    return result


def parse_blocks(raw_blocks: RawBlockArray) -> BlockArray:
    """Parse raw blocks into clean blocks using many heuristics.

    Args:
        raw_blocks (BlockArray): The raw blocks to parse.

    Returns:
        BlockArray: The parsed blocks.
    """
    raw_blocks = reading_order(raw_blocks)
    blocks: list[BlockItem] = []
    metrics: PageMetrics = compute_page_metrics(raw_blocks)

    if raw_blocks.blocks:
        # Find viewport bounds from all blocks
        max_y = max((b.bbox[3] for b in raw_blocks.blocks), default=0)

        header_threshold = max_y * 0.02  # Top 2% only
        footer_threshold = max_y * 0.98  # Bottom 2%
    else:
        header_threshold = footer_threshold = 0

    seen_texts: set[str] = set()
    text_to_block_index: dict[str, int] = {}  # Maps normalized text to its block index

    for rb in raw_blocks.blocks:
        # Skip blocks in extreme header/footer areas
        y = rb.bbox[1]
        if y < header_threshold or y > footer_threshold:
            continue

        match rb:
            case RawTextBlock():
                # Skip very narrow blocks (likely sidebar remnants)
                block_width = rb.bbox[2] - rb.bbox[0]
                if block_width < 50:
                    continue

                parsed_blocks = _handle_text_block(rb, metrics)
                for pb in parsed_blocks:
                    if not pb.text.strip():
                        continue

                    text_lower = pb.text.lower()
                    skip_patterns = [
                        "from wikipedia",
                        "not to be confused with",
                        "this article is about",
                        "for other uses",
                        "see also:",
                        "main article:",
                        "jump to navigation",
                        "jump to search",
                        "retrieved from",
                        "categories:",
                        "hidden categories:",
                        "view source",
                        "edit this",
                        "cookie policy",
                        "privacy policy",
                        "terms of use",
                    ]
                    if any(pattern in text_lower for pattern in skip_patterns):
                        continue

                    normalized = " ".join(pb.text.lower().split())

                    if normalized in seen_texts:
                        # Skip duplicates except for headings
                        if pb.heading == 0:
                            continue

                    is_duplicate = False
                    for seen in seen_texts:
                        if normalized in seen or seen in normalized:
                            is_duplicate = True
                            break

                    if is_duplicate:
                        # Don't skip headings even if they're substring duplicates
                        if pb.heading == 0:
                            continue
                        else:
                            # If this is a heading and there's a paragraph with same text, remove the paragraph
                            if normalized in text_to_block_index:
                                idx = text_to_block_index[normalized]
                                if idx < len(blocks) and blocks[idx].heading == 0:
                                    del blocks[idx]
                                    # Adjust indices in text_to_block_index
                                    for key in text_to_block_index:
                                        if text_to_block_index[key] > idx:
                                            text_to_block_index[key] -= 1

                    seen_texts.add(normalized)
                    text_to_block_index[normalized] = len(blocks)
                    blocks.append(pb)

            case RawTableBlock():
                blocks.append(
                    TableBlock(
                        rows=rb.rows,
                    )
                )

            case RawImageBlock():
                # TODO: handle images
                pass

            case _:
                logger.warning(f"Unknown block type encountered: {rb}")
                pass

    return BlockArray(url=raw_blocks.url, blocks=blocks)
