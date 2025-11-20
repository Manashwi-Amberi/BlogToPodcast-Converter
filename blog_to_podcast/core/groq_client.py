"""
Groq API client wrapper used by LangChain agents.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from groq import Groq, GroqError

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Lightweight wrapper around the Groq chat completions API.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
        # Allow larger outputs; increase default from 1500 to 3000 tokens
        # to permit longer generated scripts.
        max_output_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Groq API key missing. Please set GROQ_API_KEY in your .env file."
            )
        self.client = Groq(api_key=self.api_key)
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    def run_groq(self, system_prompt: str, user_prompt: str) -> str:
        """
        Execute a completion with the stored configuration.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except GroqError as api_error:
            logger.error("Groq API error: %s", api_error)
            raise

        if not response.choices:
            raise ValueError("Groq response did not contain any choices.")
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Groq response choice did not include content.")
        return content.strip()


