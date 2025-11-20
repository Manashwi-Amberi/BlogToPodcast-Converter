"""
Agent responsible for fetching and cleaning blog content.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
import trafilatura
from langchain_core.runnables import RunnableLambda
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


def _is_url(source: str) -> bool:
    try:
        parsed = urlparse(source.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_text(raw_text: str, *, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", raw_text)
    text = text.strip()
    if len(text) > max_chars:
        logger.warning(
            "Cleaned text exceeds %s characters. Truncating for downstream safety.",
            max_chars,
        )
        return text[:max_chars]
    return text


@dataclass
class BlogCleanerAgent:
    """
    LangChain-compatible agent that outputs `clean_blog_text`.
    """

    # Increase max_chars to allow larger blog inputs to flow through the
    # pipeline without being truncated. Users reported a ~3k character
    # limit; raising default to 30000.
    max_chars: int = 30000
    timeout: int = 15

    def __post_init__(self) -> None:
        self.runnable = RunnableLambda(self._run)

    def _download_url(self, url: str) -> Optional[str]:
        downloaded = trafilatura.fetch_url(url, no_ssl=True)
        if downloaded:
            extracted = trafilatura.extract(downloaded, include_comments=False)
            if extracted:
                return extracted
        logger.info("Trafilatura failed, falling back to raw HTTP GET for %s", url)
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    @retry(wait=wait_fixed(1), stop=stop_after_attempt(3), reraise=True)
    def _run(self, inputs: Dict[str, str]) -> Dict[str, str]:
        source = inputs.get("blog_source")
        if not source:
            raise ValueError("blog_source is required.")
        logger.info("Agent 1: starting blog cleaning step.")
        if _is_url(source):
            logger.info("Detected URL input. Fetching remote content.")
            raw_text = self._download_url(source)
        else:
            raw_text = source
        if not raw_text:
            raise ValueError("No content could be extracted from the provided input.")
        clean_text = _clean_text(raw_text, max_chars=self.max_chars)
        logger.info("Agent 1: cleaning complete. %s characters retained.", len(clean_text))
        return {"clean_blog_text": clean_text}


