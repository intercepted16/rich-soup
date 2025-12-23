# Rich Soup
Inspired by BeautifalSoup. Instead of parsing static HTML and using tags, it fully renders the page and the entire DOM (including JS/CSS & slop) using Playwright. Then, it uses semantics; i.e: avg font size versus larger font sizes, lines, gaps, spacing, hierachy/reading order; etc, to reconstruct the page into a CLEAN JSON/Markdown format.
Currently, the options are either:

- BeautifalSoup; static only, messy.
- PlayWright; lower level, manual.

- Rich Soup builds on Playwright to give the DX of BeautifalSoup but can render properly like Playwright.

Primarily intended for document-like pages; i.e: Microsft Learn, whitepapers (PDF life), Wiki-like sites. Best part is it uses the layout, not tags, and it's not static! It can extract from garbled DOMs with hundreds of divs and hydration from React and Astro islands and Tailwind, etc etc, perfectly fine.