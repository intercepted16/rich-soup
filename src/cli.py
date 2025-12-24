"""Quick dirty CLI for testing and stuff."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Extract blocks from a URL.")
    parser.add_argument(
        "--url", required=True, type=str, help="The URL to extract blocks from"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["raw", "markdown"],
        default="markdown",
        help="Output format: 'raw' for pydantic repr, 'markdown' for clean markdown",
    )
    args = parser.parse_args()

    from src.blocks import extract_blocks
    from src.processor import parse_blocks
    from src.processor.models import ParagraphBlock
    from src.common.utils.logger import logger

    logger.info("Starting block extraction...")

    block_array = extract_blocks(args.url)
    parsed_block_array = parse_blocks(block_array)

    if args.format == "raw":
        logger.info("Generating raw output...")
        for block in parsed_block_array.blocks:
            print(block)
    else:  # markdown
        logger.info("Generating markdown output...")
        for block in parsed_block_array.blocks:
            if isinstance(block, ParagraphBlock):
                if block.is_code:
                    print(f"```\n{block.text}\n```\n")
                elif block.heading > 0:
                    prefix = "#" * block.heading
                    print(f"{prefix} {block.text}\n")
                elif block.bold:
                    print(f"**{block.text}**\n")
                else:
                    print(f"{block.text}\n")


if __name__ == "__main__":
    main()
