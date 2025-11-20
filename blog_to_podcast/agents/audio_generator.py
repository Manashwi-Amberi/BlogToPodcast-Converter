"""
Agent that handles TTS synthesis and audio mixing.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import imageio_ffmpeg
import numpy as np
import pyloudnorm as pyln
import requests
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from murf import Murf
from pydub import AudioSegment
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

# Configure ffmpeg/ffprobe for PyDub so that users do not need a global installation.
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
AudioSegment.ffmpeg = AudioSegment.converter
AudioSegment.ffprobe = shutil.which("ffprobe") or AudioSegment.converter


def _segment_to_float_array(segment: AudioSegment) -> np.ndarray:
    array = np.array(segment.get_array_of_samples()).astype(np.float32)
    if segment.channels > 1:
        array = array.reshape((-1, segment.channels)).mean(axis=1)
    max_int16 = float(np.iinfo(np.int16).max)
    if max_int16 == 0:
        return array
    return array / max_int16


def _normalize_lufs(segment: AudioSegment, target_lufs: float) -> AudioSegment:
    array = _segment_to_float_array(segment)
    if not np.any(array):
        return segment
    meter = pyln.Meter(segment.frame_rate)
    loudness = meter.integrated_loudness(array)
    gain = target_lufs - loudness
    return segment.apply_gain(gain)


def _standardize_segment(segment: AudioSegment) -> AudioSegment:
    return (
        segment.set_frame_rate(44100)
        .set_sample_width(2)
        .set_channels(2)
    )


@dataclass
class AudioGeneratorAgent:
    """
    Converts the generated script into a mixed MP3 file.
    """

    output_path: Path = Path("blog_to_podcast/output/final_podcast.mp3")
    intro_path: Path = Path("blog_to_podcast/assets/intro.mp3")
    outro_path: Path = Path("blog_to_podcast/assets/outro.mp3")
    target_lufs: float = -14.0
    speech_delta_db: float = 1.0
    music_delta_db: float = -1.0
    voice_id: str = "en-US-julia"
    murf_model: str = "GEN2"
    http_timeout: int = 30

    def __post_init__(self) -> None:
        load_dotenv()
        self._ensure_audio_toolchain()
        api_key = os.getenv("MURF_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MURF_API_KEY not found. Please add it to your .env file."
            )
        self.tts_client = Murf(api_key=api_key)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.runnable = RunnableLambda(self._run)

    def _synthesize(self, script: str) -> AudioSegment:
        logger.info("Agent 3: synthesizing speech via Murf.")
        response = self.tts_client.text_to_speech.generate(
            text=script,
            voice_id=self.voice_id,
            format="MP3",
            sample_rate=44100,
            model_version=self.murf_model,
            encode_as_base_64=True,
        )
        # The Murf SDK may return different attribute or key names depending
        # on version and serialization (camelCase vs snake_case). Be defensive
        # and try multiple options for locating the audio payload.
        audio_bytes: Optional[bytes] = None

        def _resp_to_mapping(obj: Any) -> Dict[str, Any]:
            if obj is None:
                return {}
            if isinstance(obj, dict):
                return obj
            # try dataclass / SDK object conversions
            if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
                try:
                    return obj.to_dict()
                except Exception:
                    pass
            if hasattr(obj, "__dict__"):
                return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
            return {}

        resp_map = _resp_to_mapping(response)

        # Try common names for base64-encoded audio
        for encoded_key in ("encoded_audio", "encodedAudio", "encodedAudioBase64", "encodedAudio64"):
            encoded_val = resp_map.get(encoded_key) or getattr(response, encoded_key, None)
            if encoded_val:
                logger.debug("Found encoded audio via key %s", encoded_key)
                try:
                    audio_bytes = base64.b64decode(encoded_val)
                except Exception as err:
                    raise ValueError("Failed to decode base64 audio from Murf response: %s" % err)
                break

        # Try signed URL / file URL fields
        if audio_bytes is None:
            for url_key in ("audio_file", "audioFile", "url", "audio_url", "signedUrl"):
                url_val = resp_map.get(url_key) or getattr(response, url_key, None)
                if url_val:
                    logger.info("Downloading Murf audio from URL field '%s'.", url_key)
                    try:
                        resp = requests.get(url_val, timeout=self.http_timeout)
                        resp.raise_for_status()
                        audio_bytes = resp.content
                    except Exception as err:
                        raise ValueError(f"Failed to download Murf audio from URL ({url_key}): {err}")
                    break

        # Some SDKs may return raw bytes directly
        if audio_bytes is None:
            if isinstance(response, (bytes, bytearray)):
                audio_bytes = bytes(response)

        if not audio_bytes:
            raise ValueError("Murf returned no audio payload (checked several fields).")

        try:
            speech_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        except Exception as err:
            raise RuntimeError(f"Failed to parse audio bytes into AudioSegment: {err}")

        return _standardize_segment(speech_segment)

    def _load_music(self, path: Path, *, fade_in: int = 0, fade_out: int = 0) -> AudioSegment:
        if not path.exists():
            raise FileNotFoundError(f"Required audio asset missing: {path}")
        segment = AudioSegment.from_file(path)
        # Only apply fades when a positive duration is provided. Some
        # pydub versions raise if fade duration is None or start/end
        # calculations produce None.
        if fade_in and fade_in > 0:
            segment = segment.fade_in(int(fade_in))
        if fade_out and fade_out > 0:
            segment = segment.fade_out(int(fade_out))
        return _standardize_segment(segment)

    def _post_mix(self, segment: AudioSegment) -> AudioSegment:
        if segment.max_dBFS > 0:
            segment = segment.apply_gain(-segment.max_dBFS)
        return _normalize_lufs(segment, self.target_lufs)

    @retry(wait=wait_fixed(2), stop=stop_after_attempt(2), reraise=True)
    def _run(self, inputs: Dict[str, str]) -> Dict[str, str]:
        script = inputs.get("podcast_script")
        if not script:
            raise ValueError("podcast_script is required to create audio.")

        speech = _normalize_lufs(self._synthesize(script), self.target_lufs + self.speech_delta_db)
        intro_music = _normalize_lufs(
            self._load_music(self.intro_path, fade_in=2000),
            self.target_lufs + self.music_delta_db,
        )
        outro_music = _normalize_lufs(
            self._load_music(self.outro_path, fade_out=1500),
            self.target_lufs + self.music_delta_db,
        )

        logger.info("Agent 3: mixing intro, speech, and outro.")
        composite = intro_music + speech + outro_music
        final_audio = self._post_mix(composite)
        final_audio.export(
            self.output_path,
            format="mp3",
            bitrate="320k",
            parameters=["-ar", "44100"],
        )
        logger.info("Agent 3: final audio exported to %s", self.output_path)
        return {"final_audio_path": str(self.output_path)}

    def _ensure_audio_toolchain(self) -> None:
        ffmpeg_path = AudioSegment.converter
        ffprobe_path = getattr(AudioSegment, "ffprobe", None)
        missing = []
        if not ffmpeg_path or not Path(ffmpeg_path).exists():
            missing.append("ffmpeg")
        if not ffprobe_path:
            missing.append("ffprobe")
        if missing:
            raise RuntimeError(
                "ffmpeg/ffprobe binaries are required. Install FFmpeg and ensure it is on PATH."
            )


