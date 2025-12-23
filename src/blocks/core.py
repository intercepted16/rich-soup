"""Core."""

from contextlib import ExitStack, contextmanager
from typing import Any, Generator

from playwright.sync_api import ElementHandle, Page, sync_playwright

from src.blocks.models import Block, BlockArray, BlockType, StrokeBlock, TextBlock


@contextmanager
def _pw_page(url: str) -> Generator[Page, Any, Any]:
    """Setup Playwright for the given URL.

    Args:
        url (str): The URL to setup Playwright for.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        yield page  # extraction happens here
        browser.close()


def _extract_text_blocks(page: Page, elements: list[ElementHandle]):
    text_blocks: list[TextBlock] = []
    extracted_texts: list[str] = []

    element_data = page.evaluate(
        """(elements) => {
            const SKIP_TAGS = new Set([
                'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS',
                'VIDEO', 'AUDIO', 'OBJECT', 'EMBED', 'META', 'LINK',
                'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LABEL',
                'NAV', 'FOOTER', 'ASIDE', 'MENU', 'MENUITEM',
                'FORM', 'FIELDSET', 'OPTION', 'DATALIST',
                'DIALOG', 'SUMMARY', 'TEMPLATE', 'SLOT',
                'IMG', 'PICTURE', 'SOURCE', 'TRACK',
                'PROGRESS', 'METER', 'OUTPUT'
            ]);
            
            // Tags that often contain navigational or non-content elements
            const NAV_ROLES = new Set([
                'navigation', 'banner', 'contentinfo', 'complementary',
                'search', 'form', 'menu', 'menubar', 'toolbar',
                'tab', 'tablist', 'tabpanel', 'dialog', 'alertdialog',
                'status', 'log', 'marquee', 'timer', 'tooltip'
            ]);
            
            // Table-related tags (often contain metadata/infobox content)
            const TABLE_TAGS = new Set(['TABLE', 'THEAD', 'TBODY', 'TFOOT', 'TR', 'TD', 'TH', 'CAPTION', 'COL', 'COLGROUP']);
            
            // Heading tags for semantic detection
            const HEADING_TAGS = {'H1': 1, 'H2': 2, 'H3': 3, 'H4': 4, 'H5': 5, 'H6': 6};
            
            return elements.map(el => {
                const tagName = el.tagName?.toUpperCase() || '';
                const role = el.getAttribute('role')?.toLowerCase() || '';
                const ariaHidden = el.getAttribute('aria-hidden') === 'true';
                
                // Check if element or any ancestor has skip tag
                let ancestor = el;
                let hasSkipAncestor = false;
                let hasTableAncestor = false;
                while (ancestor && ancestor !== document.body) {
                    const ancestorTag = ancestor.tagName?.toUpperCase() || '';
                    const ancestorRole = ancestor.getAttribute?.('role')?.toLowerCase() || '';
                    if (SKIP_TAGS.has(ancestorTag) || NAV_ROLES.has(ancestorRole)) {
                        hasSkipAncestor = true;
                        break;
                    }
                    if (TABLE_TAGS.has(ancestorTag)) {
                        hasTableAncestor = true;
                    }
                    ancestor = ancestor.parentElement;
                }
                
                // Check if this is a table cell
                const isTableCell = TABLE_TAGS.has(tagName);
                
                return {
                    isHtmlElement: el instanceof HTMLElement,
                    tagName: tagName,
                    innerText: el.innerText?.trim() || '',
                    textContent: el.textContent?.trim() || '',
                    childrenTextLength: Array.from(el.children).reduce((total, child) => 
                        total + (child.innerText?.trim()?.length || 0), 0),
                    directTextLength: Array.from(el.childNodes)
                        .filter(n => n.nodeType === Node.TEXT_NODE)
                        .reduce((total, n) => total + (n.textContent?.trim()?.length || 0), 0),
                    bbox: el.getBoundingClientRect(),
                    visibility: window.getComputedStyle(el).visibility,
                    display: window.getComputedStyle(el).display,
                    opacity: window.getComputedStyle(el).opacity,
                    overflow: window.getComputedStyle(el).overflow,
                    role: role,
                    ariaHidden: ariaHidden,
                    hasSkipAncestor: hasSkipAncestor,
                    hasTableAncestor: hasTableAncestor,
                    isTableCell: isTableCell,
                    headingLevel: HEADING_TAGS[tagName] || 0,
                    isLink: tagName === 'A',
                    isCode: ['CODE', 'PRE', 'KBD', 'SAMP', 'VAR'].includes(tagName),
                    isList: ['UL', 'OL', 'LI', 'DL', 'DT', 'DD'].includes(tagName),
                    isBlockquote: tagName === 'BLOCKQUOTE',
                    isArticle: ['ARTICLE', 'SECTION', 'MAIN'].includes(tagName),
                    className: el.className || '',
                    id: el.id || '',
                    computedStyle: {
                        fontSize: window.getComputedStyle(el).fontSize,
                        fontWeight: window.getComputedStyle(el).fontWeight,
                        fontFamily: window.getComputedStyle(el).fontFamily
                    }
                };
            });
        }""",
        elements,
    )

    for data in element_data:
        if not data["isHtmlElement"]:
            continue

        if data["hasSkipAncestor"]:
            continue

        if data["ariaHidden"]:
            continue

        text = data["innerText"]
        if not text:
            continue

        word_count = len(text.split())

        # Skip table cells and elements inside tables unless they're substantial paragraphs
        # Table content is often metadata (infoboxes) or fragmented data
        if data["isTableCell"] or data["hasTableAncestor"]:
            # Only keep table content if it's a significant paragraph (20+ words)
            if word_count < 20:
                continue

        # Skip very short text (likely UI labels) unless it's a heading
        if word_count < 4 and data["headingLevel"] == 0:
            continue

        # Check visibility
        if data["visibility"] == "hidden" or data["display"] == "none":
            continue
        if data["opacity"] == "0":
            continue

        bbox = data["bbox"]
        if bbox["width"] <= 0 or bbox["height"] <= 0:
            continue

        parent_text_length = len(text)
        children_text_length = data["childrenTextLength"]
        if children_text_length > 0 and parent_text_length > 0:
            if children_text_length / parent_text_length > 0.85:
                continue

        direct_text_length = data["directTextLength"]
        if parent_text_length > 100 and direct_text_length < parent_text_length * 0.1:
            continue

        is_duplicate = False
        texts_to_remove: list[int] = []
        for idx, existing in enumerate(extracted_texts):
            if text in existing:
                is_duplicate = True
                break
            elif existing in text and len(text) > len(existing):
                texts_to_remove.append(idx)

        if is_duplicate:
            continue

        for idx in reversed(texts_to_remove):
            extracted_texts.pop(idx)
            text_blocks.pop(idx)

        style = data["computedStyle"]
        text_blocks.append(
            TextBlock(
                type=BlockType.TEXT,
                bbox=(
                    bbox["x"],
                    bbox["y"],
                    bbox["x"] + bbox["width"],
                    bbox["y"] + bbox["height"],
                ),
                text=text,
                font_size=float(style["fontSize"].replace("px", "")),
                font_weight=float(style["fontWeight"]),
                font_family=style["fontFamily"],
                heading_level=data["headingLevel"],
                is_code=data["isCode"],
                is_list=data["isList"],
                is_blockquote=data["isBlockquote"],
            )
        )
        extracted_texts.append(text)

    return text_blocks


def _extract_stroke_blocks(page: Page, elements: list[ElementHandle]):
    stroke_blocks: list[Block] = []

    element_data = page.evaluate(
        """(elements) => {
            return elements.map(el => ({
                bbox: el.getBoundingClientRect(),
                visibility: window.getComputedStyle(el).visibility,
                display: window.getComputedStyle(el).display,
                backgroundColor: window.getComputedStyle(el).backgroundColor
            }));
        }""",
        elements,
    )

    for data in element_data:
        if data["visibility"] == "hidden" or data["display"] == "none":
            continue

        bbox = data["bbox"]

        if bbox["width"] < 2 or bbox["height"] < 2:
            stroke_blocks.append(
                StrokeBlock(
                    type=BlockType.STROKE,
                    bbox=(
                        bbox["x"],
                        bbox["y"],
                        bbox["x"] + bbox["width"],
                        bbox["y"] + bbox["height"],
                    ),
                    color=data["backgroundColor"],
                )
            )

    return stroke_blocks


def extract_blocks(url: str) -> BlockArray:
    """Extract blocks from a given URL.

    Args:
        url (str): The URL to extract blocks from.

    Returns:
        BlockArray: The extracted blocks.
    """
    blocks: list[Block] = []

    s = ExitStack()

    page = s.enter_context(_pw_page(url))
    elements = page.query_selector_all("body *")

    text_blocks = _extract_text_blocks(page, elements)
    blocks.extend(text_blocks)

    stroke_blocks = _extract_stroke_blocks(page, elements)
    blocks.extend(stroke_blocks)

    return BlockArray(url=url, blocks=blocks)
