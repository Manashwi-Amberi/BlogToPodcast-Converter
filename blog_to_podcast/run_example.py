"""
Quick example runner for manual testing of the Blog -> Podcast pipeline.

Usage (PowerShell):
  $env:MURF_API_KEY = 'your-key'
  $env:GROQ_API_KEY = 'your-key'
  python -m blog_to_podcast.run_example

This script loads `.env` (if present) and runs the pipeline with a short sample.
"""
from __future__ import annotations

import logging
from dotenv import load_dotenv

from blog_to_podcast.core.pipeline import BlogToPodcastPipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    load_dotenv()
    sample_text = (
        "Today we're discussing how to convert blog posts into natural-sounding podcast episodes. "
        "This short sample will be narrated by the configured TTS provider (Murf)."
    )

    pipeline = BlogToPodcastPipeline()
    try:
        result = pipeline.run(blog_source=sample_text)
        print("Pipeline finished. Outputs:")
        for k, v in result.items():
            print(f"- {k}: {v}")
    except Exception as exc:
        logging.exception("Pipeline failed: %s", exc)


if __name__ == "__main__":
    main()
