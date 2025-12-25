"""Quick dirty CLI for testing and stuff."""

import argparse
from src.common.utils.logger import logger


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Extract blocks from a URL.")
    parser.add_argument("--url", required=True, type=str, help="The URL to extract blocks from")
    parser.add_argument(
        "--format",
        type=str,
        choices=["raw", "markdown"],
        default="markdown",
        help="Output format: 'raw' for pydantic repr, 'markdown' for clean markdown",
    )
    args = parser.parse_args()

    from src.processor import extract_blocks

    logger.info("Starting block extraction...")

    blocks = extract_blocks(args.url)

    match str(args.format).lower():
        case "raw":
            logger.info("Generating raw output...")
            for block in blocks:
                logger.info(block)

        case "markdown":
            logger.info("Generating markdown output...")
            logger.info("Markdown:\n%s", blocks.markdown)

        case _:
            logger.error(f"Unknown format: {args.format}")


if __name__ == "__main__":
    main()
