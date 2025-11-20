"""
Orchestrates the 3-agent workflow using LangChain runnables.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from blog_to_podcast.agents.audio_generator import AudioGeneratorAgent
from blog_to_podcast.agents.blog_cleaner import BlogCleanerAgent
from blog_to_podcast.agents.script_generator import ScriptGeneratorAgent
from blog_to_podcast.core.groq_client import GroqClient

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class BlogToPodcastPipeline:
    """
    High-level pipeline that connects all agents.
    """

    groq_client: GroqClient = field(default_factory=GroqClient)
    blog_agent: BlogCleanerAgent = field(default_factory=BlogCleanerAgent)
    audio_agent: AudioGeneratorAgent = field(default_factory=AudioGeneratorAgent)
    script_agent: ScriptGeneratorAgent = field(init=False)

    def __post_init__(self) -> None:
        self.script_agent = ScriptGeneratorAgent(groq_client=self.groq_client)

    def _log_step(self, message: str) -> None:
        logger.info("[%s] %s", _timestamp(), message)

    def run(self, *, blog_source: str) -> Dict[str, str]:
        if not blog_source:
            raise ValueError("A blog URL or raw text source is required.")

        self._log_step("Pipeline start.")
        cleaned = self.blog_agent.runnable.invoke({"blog_source": blog_source})
        self._log_step("Blog cleaned.")

        script_result = self.script_agent.runnable.invoke(cleaned)
        script_text = script_result["podcast_script"]
        self._log_step("Podcast script ready.")
        print("\n===== PODCAST SCRIPT =====\n")
        print(script_text)
        print("\n===== END SCRIPT =====\n")

        try:
            audio_result = self.audio_agent.runnable.invoke(script_result)
        except Exception as exc:  # pragma: no cover - surfaced via CLI/HTTP
            logger.exception("Audio agent failed: %s", exc)
            raise
        self._log_step("Audio generation complete.")
        self._log_step(f"Final MP3: {audio_result['final_audio_path']}")
        return {
            **cleaned,
            **script_result,
            **audio_result,
        }


