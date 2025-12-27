"""Quick dirty CLI for testing and stuff."""

import argparse
from src.common.utils.logger import logger
from src.common.utils.config import config


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Rich Soup CLI")
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Extract action (default)
    extract_parser = subparsers.add_parser("extract", help="Extract blocks from a URL")
    extract_parser.add_argument("--url", required=True, type=str, help="The URL to extract blocks from")
    extract_parser.add_argument(
        "--format",
        type=str,
        choices=["raw", "markdown"],
        default="markdown",
        help="Output format: 'raw' for pydantic repr, 'markdown' for clean markdown",
    )

    subparsers.add_parser("config", help="Print configuration")

    args = parser.parse_args()

    action = args.action or "extract"

    if action == "extract":
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
                with open("output.md", "w", encoding="utf-8") as f:
                    f.write(blocks.markdown)
                logger.info("Markdown output written to output.md")

            case _:
                logger.error(f"Unknown format: {args.format}")

    elif action == "config":
        logger.info("Configuration:\n")
        for key, value in sorted(config.model_dump().items()):
            print(f"{key}={value}")


if __name__ == "__main__":
    main()
