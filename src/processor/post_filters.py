"""Post processing filters for blocks."""

from src.processor.models import LinkBlock, BlockItem
from typing import Callable
import pycountry
from urllib.parse import urlparse
from src.common.utils.logger import logger
import unicodedata

# Build ISO language codes set
ISO_LANG_CODES: set[str] = set()
for lang in pycountry.languages:
    if hasattr(lang, "alpha_2"):
        alpha_2 = getattr(lang, "alpha_2", None)
        if isinstance(alpha_2, str):
            ISO_LANG_CODES.add(alpha_2.lower())

# Build language names set (English + native names)
LANG_NAMES: set[str] = set()
for lang in pycountry.languages:
    if hasattr(lang, "name"):
        name = getattr(lang, "name", None)
        if isinstance(name, str):
            LANG_NAMES.add(name.lower())
    if hasattr(lang, "native_name"):
        native_name = getattr(lang, "native_name", None)
        if isinstance(native_name, str):
            LANG_NAMES.add(native_name.lower())

LANG_NAMES.update({"Deutsch", "Espanol", "日本語"})  # last is JP

for name in list(LANG_NAMES):
    normalized_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").strip().lower()
    )
    LANG_NAMES.add(normalized_name)


def is_lang_path_segment(segment: str) -> bool:
    segment = segment.lower()
    if "-" in segment:
        lang, _ = segment.split("-", 1)
        return lang in ISO_LANG_CODES
    return segment in ISO_LANG_CODES


def remove_language_links(blocks: list[BlockItem]) -> None:
    """Remove blocks that are likely to be language selection links."""
    for idx, block in reversed(list(enumerate(blocks))):
        if not isinstance(block, LinkBlock):
            continue

        href = block.href.lower()
        # Check first path segment
        path_segment = urlparse(href).path.strip("/").split("/")[0]
        if not path_segment:
            continue

        path_segment = (
            unicodedata.normalize("NFKD", path_segment).encode("ascii", "ignore").decode("ascii").lower()
        )

        # Check if first segment is a language code
        if is_lang_path_segment(path_segment):
            del blocks[idx]
            continue

        for span in block.spans:
            filtered = (
                unicodedata.normalize("NFKD", span.text)
                .encode("ascii", "ignore")
                .decode("ascii")
                .strip()
                .lower()
            )
            logger.info("possibly filtering out (language text): %s", filtered)
            if (filtered or span.text) in LANG_NAMES:
                logger.info("removing language link with text: %s", span.text)
                del blocks[idx]
                break


def ignore_common_bs(blocks: list[BlockItem]) -> None:
    """Ignore blocks that are common boilerplate links."""
    bs = [
        "privacy policy",
        "terms of service",
        "terms and conditions",
        "contact us",
        "about us",
        "help",
        "faq",
        "cookie policy",
        "sitemap",
        "sign in",
        "get support",
        "pricing",
        "have any feedback or questions?",
        "guides",
        "privacy & terms",
        "licenses",
        "your privacy choices",
    ]
    for i, s in enumerate(bs):
        bs[i] = s.replace(" ", "").lower()

    for idx, block in reversed(list(enumerate(blocks))):
        if not isinstance(block, LinkBlock):
            continue

        link_text = " ".join(span.text.strip().lower() for span in block.spans).replace(" ", "")
        if link_text in bs:
            del blocks[idx]


def duped_links(blocks: list[BlockItem]) -> None:
    """Remove duplicate links based on href, keeping the first occurrence."""
    seen_hrefs: set[str] = set()
    new_blocks: list[BlockItem] = []

    for block in blocks:
        if isinstance(block, LinkBlock):
            logger.info(f"Processing link: {block.href}")
            if block.href in seen_hrefs:
                logger.info(f"Skipping duplicate link: {block.href}")
                continue  # skip duplicates
            seen_hrefs.add(block.href)
        new_blocks.append(block)

    # replace original list in-place
    blocks[:] = new_blocks


filters: list[Callable[[list[BlockItem]], None]] = [remove_language_links, ignore_common_bs, duped_links]


def filter_blocks(blocks: list[BlockItem]) -> None:
    """Apply post-processing filters to the extracted blocks."""
    for ffilter in filters:
        ffilter(blocks)
