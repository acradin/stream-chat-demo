"""Server-owned generation, service usage and private provider accounting."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import threading
import time
import uuid

from backend.manual_provider import validate_context
from backend.storage import atomic_json
from backend.providers import InvalidResponseError, ProviderError
from backend.screenshot_provider import (DEFAULT_MODEL, OpenAIScreenshotProvider,
                                 MockScreenshotProvider, validate_screenshot)


MAX_PARTICIPANTS = 5
SERVICE_FIELDS = ("generation_requests", "generated_chats")
TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
COUNTERS = ("attempts", "succeeded", "failed", "unmetered", *TOKEN_FIELDS)


def make_provider(name: str, model: str, api_key: str | None):
    if name == "mock":
        return MockScreenshotProvider()
    return OpenAIScreenshotProvider(model=model, api_key=api_key)


class DesktopService:
    def __init__(self, state_dir: str | Path, *, provider_factory=make_provider, cooldown_s: float = 1,
                 month_clock=None):
        self.usage_path = Path(state_dir) / "usage.json"
        self.provider_factory = provider_factory
        self.cooldown_s = cooldown_s
        self.month_clock = month_clock or (lambda: datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m"))
        self._batch_lock = threading.Lock()
        self._usage_lock = threading.RLock()
        self.stop_requested = threading.Event()
        self._last_started = -float("inf")
        self._recent = {"openai": [], "mock": []}
        self._usage = {"schema_version": 1, **{
            name: {key: 0 for key in COUNTERS} for name in ("openai", "mock")}}
        self._usage["service_months"] = {}
        if self.usage_path.exists():
            data = json.loads(self.usage_path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("schema_version") != 1
                    or any(not isinstance(data.get(name), dict)
                           or any(type(data[name].get(key)) is not int or data[name][key] < 0
                                  for key in COUNTERS) for name in ("openai", "mock"))):
                raise ValueError("usage.json 형식이 잘못됐습니다. 기존 파일을 보존하고 확인해주세요.")
            for name in ("openai", "mock"):
                self._usage[name] = {key: data[name][key] for key in COUNTERS}
                # A crash can leave an attempted call without a terminal result.
                pending = data[name]["attempts"] - data[name]["succeeded"] - data[name]["failed"]
                if pending < 0:
                    raise ValueError("usage.json 호출 수가 일치하지 않습니다.")
                self._usage[name]["failed"] += pending
                self._usage[name]["unmetered"] += pending if name == "openai" else 0
            months = data.get("service_months", {})
            if (not isinstance(months, dict) or any(
                    not isinstance(period, str) or not isinstance(values, dict)
                    or set(values) != {"openai", "mock"}
                    or any(not isinstance(values[name], dict) or any(
                        type(values[name].get(key)) is not int or values[name][key] < 0
                        for key in SERVICE_FIELDS) for name in ("openai", "mock"))
                    for period, values in months.items())):
                raise ValueError("서비스 사용량 기록 형식이 잘못됐습니다.")
            self._usage["service_months"] = months

    def usage(self) -> dict:
        with self._usage_lock:
            return copy.deepcopy(self._usage)

    def service_usage(self, provider_name: str = "openai") -> dict:
        """Public usage contains service units only, never provider costs/tokens."""
        with self._usage_lock:
            period = self.month_clock()
            monthly = self._usage["service_months"].get(period, {}).get(provider_name, {})
            return {"period": period, "timezone": "Asia/Seoul", "is_demo": provider_name == "mock",
                    "generation_requests": monthly.get("generation_requests", 0),
                    "generated_chats": monthly.get("generated_chats", 0),
                    "total_generated_chats": self._usage[provider_name]["succeeded"]}

    def _record(self, name: str, **increments) -> None:
        with self._usage_lock:
            candidate = copy.deepcopy(self._usage)
            period = self.month_clock()
            monthly = candidate["service_months"].setdefault(period, {
                provider: {key: 0 for key in SERVICE_FIELDS} for provider in ("openai", "mock")})
            monthly[name]["generation_requests"] += increments.pop("generation_requests", 0)
            monthly[name]["generated_chats"] += increments.get("succeeded", 0)
            for key, value in increments.items():
                candidate[name][key] += value
            atomic_json(self.usage_path, candidate)
            self._usage = candidate

    async def generate(self, personas: list[str], context: str, *, screenshot: bytes, provider_name: str,
                       model: str = DEFAULT_MODEL, api_key: str | None = None, on_line=None) -> dict:
        """One explicit batch, one call per participant; busy inputs are dropped.

        on_line is invoked on the caller's thread. GUI clients must queue events
        rather than touching their widgets from this callback.
        """
        if provider_name not in ("openai", "mock"):
            raise ValueError("지원하지 않는 생성 모드입니다.")
        if not isinstance(personas, list) or not 1 <= len(personas) <= MAX_PARTICIPANTS:
            raise ValueError("AI 인원은 1~5명이어야 합니다.")
        validate_screenshot(screenshot)
        snapshots = [validate_context({"request_id": uuid.uuid4().hex, "persona": persona,
                                      "channel_context": context, "recent_comments": []})
                     for persona in list(personas)]
        if not self._batch_lock.acquire(blocking=False):
            return {"status": "busy", "lines": []}
        provider = None
        lines = []
        try:
            if self.stop_requested.is_set():
                return {"status": "stopped", "lines": []}
            if time.monotonic() - self._last_started < self.cooldown_s:
                return {"status": "cooldown", "lines": []}
            # Credential/model errors happen before any attempted-call accounting.
            provider = self.provider_factory(provider_name, model, api_key)
            self._record(provider_name, generation_requests=1)
            self._last_started = time.monotonic()
            for index, snapshot in enumerate(snapshots, 1):
                if self.stop_requested.is_set():
                    break
                snapshot["recent_comments"] = self._recent[provider_name][-8:]
                self._record(provider_name, attempts=1)
                line = {"participant": index, "persona": snapshot["persona"],
                        "status": "error", "comment": "", "error": ""}
                try:
                    result = await asyncio.wait_for(provider.generate(snapshot, screenshot), timeout=31)
                    comment = result.get("comment") if isinstance(result, dict) else None
                    if (not isinstance(comment, str) or not 1 <= len(comment.strip()) <= 100
                            or any(ord(c) < 32 or c in "\u0085\u2028\u2029" for c in comment)):
                        raise InvalidResponseError("유효한 한 줄 채팅을 받지 못했습니다.")
                    raw_usage = result.get("usage", {})
                    tokens = {key: raw_usage[key] for key in TOKEN_FIELDS
                              if isinstance(raw_usage, dict) and type(raw_usage.get(key)) is int
                              and raw_usage[key] >= 0}
                    self._record(provider_name, succeeded=1,
                                 unmetered=int(provider_name == "openai" and "total_tokens" not in tokens),
                                 **(tokens if provider_name == "openai" else {}))
                    line.update(status="ready", comment=comment.strip(), generation_ms=result.get("generation_ms"))
                    self._recent[provider_name] = (self._recent[provider_name] + [comment.strip()])[-8:]
                except asyncio.CancelledError:
                    self._record(provider_name, failed=1, unmetered=int(provider_name == "openai"))
                    raise
                except (ProviderError, asyncio.TimeoutError) as exc:
                    self._record(provider_name, failed=1, unmetered=int(provider_name == "openai"))
                    line["error"] = str(exc) if isinstance(exc, ProviderError) else "생성 시간이 초과됐습니다."
                except OSError:
                    # Stop if the usage file cannot be saved; do not make more paid calls.
                    raise
                except Exception as exc:
                    self._record(provider_name, failed=1, unmetered=int(provider_name == "openai"))
                    line["error"] = f"생성 실패 ({type(exc).__name__})"
                lines.append(line)
                if on_line is not None:
                    on_line(copy.deepcopy(line))
            return {"status": "complete" if all(line["status"] == "ready" for line in lines) else "partial",
                    "lines": lines, "stopped": self.stop_requested.is_set()}
        finally:
            try:
                if provider is not None:
                    await provider.close()
            finally:
                self._batch_lock.release()
