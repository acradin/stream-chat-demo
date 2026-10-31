"""Experiment entry points; the provider implementation is shared with the backend."""

import os
from pathlib import Path
import re

from backend.env import read_env_file
from backend.realtime_provider import (
    API_URL, DEFAULT_MODEL, DECISION_TOOL, OUTPUT_RULES, PROMPT,
    Frame, MockProvider, RealtimeError, RealtimeProvider, decode_frame, parse_decision, parse_response,
)

DIRECTORY = Path(__file__).resolve().parent


def credentials():
    keys = frozenset({"OPENAI_API_KEY", "REALTIME_MODEL"})
    values = read_env_file(DIRECTORY.parents[1] / "backend/.env", keys)
    values.update(read_env_file(DIRECTORY / ".env", keys))
    key = os.environ.get("OPENAI_API_KEY", values.get("OPENAI_API_KEY", ""))
    model = os.environ.get("REALTIME_MODEL", values.get("REALTIME_MODEL", DEFAULT_MODEL))
    if not key or not key.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in key):
        raise RealtimeError("운영자 backend/.env의 OPENAI_API_KEY를 확인해주세요.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
        raise RealtimeError("실험용 REALTIME_MODEL 값을 확인해주세요.")
    return key, model
