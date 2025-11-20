"""
Agent that converts cleaned blog text into a podcast script.
"""

from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass
from typing import Dict, List

from langchain_core.runnables import RunnableLambda
from tenacity import retry, stop_after_attempt, wait_fixed

from blog_to_podcast.core.groq_client import GroqClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an expert podcast scriptwriter. Convert structured or unstructured "
    "blog content into a casual, friendly, engaging podcast script.\n\n"
    "RULES:\n"
    "- Use simple spoken English.\n"
    "- No long sentences.\n"
    "- Add conversational transitions.\n"
    "- Avoid robotic tone.\n"
    "- Add a quick hook in the first 10 seconds.\n"
    "- End with a warm closing note."
)


@dataclass
class ScriptGeneratorAgent:
    """
    LangChain agent that wraps the Groq client.
    """

    groq_client: GroqClient

    def __post_init__(self) -> None:
        self.runnable = RunnableLambda(self._run)

    def _build_prompt(self, clean_blog_text: str) -> str:
        return (
            "Transform the following blog content into a fully produced podcast script. "
            "Focus on clarity, narrative flow, and conversational transitions.\n\n"
            "BLOG CONTENT:\n"
            f"{clean_blog_text}"
        )

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(3), reraise=True)
    def _run(self, inputs: Dict[str, str]) -> Dict[str, str]:
        blog_text = inputs.get("clean_blog_text")
        if not blog_text:
            raise ValueError("clean_blog_text is required for script generation.")
        logger.info("Agent 2: generating podcast script with Groq.")
        prompt = self._build_prompt(blog_text)
        try:
            script = self.groq_client.run_groq(SYSTEM_PROMPT, prompt)
            if not script:
                raise ValueError("Groq returned an empty script.")
            self._ensure_valid_script(script)
            logger.info("Agent 2: script generation complete via Groq.")
            return {"podcast_script": script.strip()}
        except Exception as error:  # pragma: no cover - fallback path
            logger.warning("Groq unavailable (%s). Using fallback writer.", error)
            fallback_script = self._build_fallback_script(blog_text)
            return {"podcast_script": fallback_script}

    def _ensure_valid_script(self, script: str) -> None:
        snippet = script.lstrip()[:80].lower()
        if any(snippet.startswith(prefix) for prefix in ("<!doctype", "<html", "<!doctype html")):
            raise RuntimeError(
                "Groq returned an HTML error page instead of a script. Please try again shortly."
            )

    def _build_fallback_script(self, clean_blog_text: str) -> str:
        trimmed = clean_blog_text.strip()
        if not trimmed:
            return (
                "Hey there, welcome back! It looks like the blog content was empty, "
                "so there's nothing to narrate right now."
            )

        paragraphs = [p.strip() for p in trimmed.split("\n") if p.strip()]
        opener = paragraphs[0] if paragraphs else ""
        # Allow a longer opener to avoid truncation for longer titles
        opener = textwrap.shorten(opener, width=600, placeholder="...")

        body_text = " ".join(paragraphs[1:]) if len(paragraphs) > 1 else trimmed
        # Increase fallback body width so longer articles produce fuller fallback scripts
        body_text = textwrap.shorten(body_text, width=5000, placeholder="...")

        key_points = self._extract_key_points(paragraphs)
        formatted_points = "\n".join(f"- {point}" for point in key_points)

        fallback_script = f"""
[Intro]
Hey friends, welcome to the Blog -> Podcast Studio. Today we're unpacking a post titled:
"{opener}"

[Main Takeaways]
{formatted_points or "This article focuses on a single narrative, so let's walk through it together."}

[Deep Dive]
{body_text}

[Outro]
That's a wrap for this quick conversion. Once Groq is reachable again, run the same post for a fully polished script.
"""
        return textwrap.dedent(fallback_script).strip()

    def _extract_key_points(self, paragraphs: List[str]) -> List[str]:
        points: List[str] = []
        for paragraph in paragraphs[:6]:
            sentence = paragraph.split(".")[0].strip()
            if not sentence:
                continue
            sentence = textwrap.shorten(sentence, width=160, placeholder="...")
            if sentence not in points:
                points.append(sentence)
            if len(points) == 4:
                break
        return points


