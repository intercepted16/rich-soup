"""Core DOM-based block extraction with merged lists."""

from contextlib import ExitStack, contextmanager
from typing import Any, Generator, TypedDict
import json

from playwright.sync_api import Page, sync_playwright, Browser
import pathlib

from src.blocks.models import (
    Block,
    BlockArray,
    BlockType,
    TextBlock,
    ImageBlock,
    TableBlock,
    LinkBlock,
    ListBlock,
)
from src.common.models import Span


class ListBBox(TypedDict):
    x: float
    y: float
    width: float
    height: float
    text: str


class ElementData(TypedDict):
    bbox: dict[str, float]
    text: str
    spans: list[dict[str, Any]] | None
    fontSize: float
    fontWeight: float
    fontFamily: str | None
    headingLevel: int
    isCode: bool
    isList: bool
    isBlockquote: bool


PYTHON_FILE_DIR = pathlib.Path(__file__).parent.resolve()

INTERNAL_SCRIPT_CODE = (PYTHON_FILE_DIR / "core.js").read_text()

IIFE_WRAPPER = "(() => {{\n{}\n}})()"


@contextmanager
def browser() -> Generator[Browser, Any, Any]:
    """Context manager for browser lifecycle."""
    playwright = sync_playwright().start()
    try:
        browser_instance = playwright.chromium.launch(headless=True)
        try:
            yield browser_instance
        finally:
            browser_instance.close()
    finally:
        playwright.stop()


@contextmanager
def _pw_page(url: str) -> Generator[Page, Any, Any]:
    """Context manager for creating a page and navigating to URL."""
    with ExitStack() as stack:
        browser_instance = stack.enter_context(browser())
        page = browser_instance.new_page()
        stack.callback(page.close)
        page.goto(url, wait_until="domcontentloaded", timeout=10000)
        try:
            # Scroll to bottom to trigger lazy-loaded content
            # page.evaluate("""
            #     async () => {
            #         await new Promise((resolve) => {
            #             let totalHeight = 0;
            #             const distance = 100;
            #             const timer = setInterval(() => {
            #                 window.scrollBy(0, distance);
            #                 totalHeight += distance;
            #                 if (totalHeight >= document.body.scrollHeight) {
            #                     clearInterval(timer);
            #                     resolve();
            #                 }
            #             }, 100);
            #         });
            #     }
            # """)
            page.wait_for_timeout(500)  # stability wait
        except Exception:
            pass

        yield page


def _extract_text_blocks(page: Page) -> list[TextBlock]:
    """Use extractTextNodes.js for fast text block extraction."""
    selectors = [
        "p",
        "div",
        "li",
        "dt",
        "dd",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "code",
        "section",
        "article",
        "main",
        "a",
        "blockquote",
    ]
    element_data: list[ElementData] = page.evaluate(
        IIFE_WRAPPER.format(INTERNAL_SCRIPT_CODE + f"\n\nreturn extractTextNodes({json.dumps(selectors)});")
    )

    blocks: list[TextBlock] = []
    for data in element_data:
        bbox = data["bbox"]

        # Convert span dicts to Span objects if available
        spans: list[Span] | None = None
        if data.get("spans"):
            span_list = data["spans"]
            if span_list is not None:
                spans = [
                    Span(
                        text=span["text"],
                        formats=span["formats"],
                        font_size=span.get("font_size"),
                        font_weight=span.get("font_weight"),
                        font_family=span.get("font_family"),
                    )
                    for span in span_list
                ]

        blocks.append(
            TextBlock(
                type=BlockType.TEXT,
                text=data["text"],
                spans=spans,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                font_size=data.get("fontSize", 0),
                font_weight=data.get("fontWeight", 0),
                font_family=data.get("fontFamily"),
                heading_level=data.get("headingLevel", 0),
            )
        )
    return blocks


def _extract_lists(page: Page) -> list[ListBlock]:
    """Extract lists by calling extractLists() JS function in the page."""
    element_data: list[dict[str, Any]] = page.evaluate(
        IIFE_WRAPPER.format(f"{INTERNAL_SCRIPT_CODE}\n\nreturn extractLists();")
    )

    blocks: list[ListBlock] = []
    for data in element_data:
        bbox = data["bbox"]

        # Convert items - each item is a list of span dicts
        items: list[list[Span]] = []
        for item_spans in data.get("items", []):
            spans = [
                Span(
                    text=span["text"],
                    formats=span["formats"],
                    font_size=span.get("font_size"),
                    font_weight=span.get("font_weight"),
                    font_family=span.get("font_family"),
                )
                for span in item_spans
            ]
            items.append(spans)

        blocks.append(
            ListBlock(
                type=BlockType.LIST,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                items=items,
                ordered=data.get("ordered", False),
                level=data.get("level", 0),
            )
        )

    return blocks


def _extract_images(page: Page):
    """Extract <img> blocks."""
    img_elements = page.evaluate(IIFE_WRAPPER.format(f"{INTERNAL_SCRIPT_CODE}\n\nreturn extractImages();"))
    blocks: list[ImageBlock] = []

    for img in img_elements:
        bbox = img["bbox"]
        src = img["src"]

        blocks.append(
            ImageBlock(
                type=BlockType.IMAGE,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                src=src,
                alt=img.get("alt", None),
            )
        )

    return blocks


def _extract_tables(page: Page) -> list[TableBlock]:
    """Extract tables by calling extractTables() JS function in the page."""
    element_data: list[dict[str, Any]] = page.evaluate(
        IIFE_WRAPPER.format(f"{INTERNAL_SCRIPT_CODE}\n\nreturn extractTables();")
    )  # JS returns list of table objects

    blocks: list[TableBlock] = []
    for data in element_data:
        bbox = data["bbox"]
        blocks.append(
            TableBlock(
                type=BlockType.TABLE,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                rows=data["rows"],
            )
        )

    return blocks


def _extract_links(page: Page) -> list[LinkBlock]:
    """Extract links by calling extractLinks() JS function in the page."""
    element_data: list[dict[str, Any]] = page.evaluate(
        IIFE_WRAPPER.format(f"{INTERNAL_SCRIPT_CODE}\n\nreturn extractLinks();")
    )  # JS returns list of link objects

    blocks: list[LinkBlock] = []
    for data in element_data:
        bbox = data["bbox"]

        # Convert span dicts to Span objects
        spans: list[Span] = []
        if data.get("spans"):
            span_list = data["spans"]
            if span_list is not None:
                spans = [
                    Span(
                        text=span["text"],
                        formats=span["formats"],
                        font_size=span.get("font_size"),
                        font_weight=span.get("font_weight"),
                        font_family=span.get("font_family"),
                    )
                    for span in span_list
                ]

        blocks.append(
            LinkBlock(
                type=BlockType.LINK,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                href=data["href"],
                spans=spans,
            )
        )

    return blocks


def extract_raw_blocks(url: str) -> BlockArray:
    """Extract text, images, table, and link blocks from a URL."""
    blocks: list[Block] = []

    with _pw_page(url) as page:
        blocks.extend(_extract_text_blocks(page))
        blocks.extend(_extract_images(page))
        blocks.extend(_extract_tables(page))
        blocks.extend(_extract_links(page))
        blocks.extend(_extract_lists(page))

    return BlockArray(url=url, blocks=blocks)
