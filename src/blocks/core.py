"""Core DOM-based block extraction with merged lists."""

from contextlib import ExitStack, contextmanager
from typing import Any, Generator, TypedDict
import json

from playwright.sync_api import Page, sync_playwright
import pathlib

from src.blocks.models import (
    Block,
    BlockArray,
    BlockType,
    TextBlock,
    ImageBlock,
    TableBlock,
)


class ListBBox(TypedDict):
    x: float
    y: float
    width: float
    height: float


PYTHON_FILE_DIR = pathlib.Path(__file__).parent.resolve()

INTERNAL_SCRIPT_CODE = (PYTHON_FILE_DIR / "core.js").read_text()

IIFE_WRAPPER = "(() => {{\n{}\n}})()"


@contextmanager
def _pw_page(url: str) -> Generator[Page, Any, Any]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")  # for faster load

        yield page
        browser.close()


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
    element_data: list[dict[str, Any]] = page.evaluate(
        IIFE_WRAPPER.format(
            INTERNAL_SCRIPT_CODE
            + f"\n\nreturn extractTextNodes({json.dumps(selectors)});"
        )
    )

    blocks: list[TextBlock] = []
    for data in element_data:
        bbox = data["bbox"]
        blocks.append(
            TextBlock(
                type=BlockType.TEXT,
                text=data["text"],
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


def _extract_images(page: Page):
    """Extract <img> blocks."""
    img_elements = page.evaluate(
        IIFE_WRAPPER.format(f"{INTERNAL_SCRIPT_CODE}\n\nreturn extractImages();")
    )
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


def extract_raw_blocks(url: str) -> BlockArray:
    """Extract text, images, and table blocks from a URL."""
    blocks: list[Block] = []
    s = ExitStack()
    page = s.enter_context(_pw_page(url))

    blocks.extend(_extract_text_blocks(page))
    blocks.extend(_extract_images(page))
    blocks.extend(_extract_tables(page))

    return BlockArray(url=url, blocks=blocks)
