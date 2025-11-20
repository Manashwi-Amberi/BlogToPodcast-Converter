from __future__ import annotations

import argparse
import logging
from pathlib import Path

from blog_to_podcast.core.pipeline import BlogToPodcastPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert blog posts into a narrated podcast episode."
    )
    parser.add_argument("--url", help="URL of the blog post to convert.")
    parser.add_argument(
        "--text-file",
        dest="text_file",
        help="Path to a text/markdown file containing blog content.",
    )
    parser.add_argument(
        "--raw-text",
        dest="raw_text",
        help="Inline blog text. Useful for quick tests.",
    )
    return parser.parse_args()


def resolve_source(args: argparse.Namespace) -> str:
    if args.url:
        return args.url
    if args.text_file:
        path = Path(args.text_file).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")
        return path.read_text(encoding="utf-8")
    if args.raw_text:
        return args.raw_text
    raise ValueError("Provide at least one input via --url, --text-file, or --raw-text.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    args = parse_args()
    source = resolve_source(args)
    pipeline = BlogToPodcastPipeline()
    pipeline.run(blog_source=source)


if __name__ == "__main__":
    main()


