"""Bounded paid comparison on original synthetic scenes, with per-call accounting."""

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import statistics
import time

from experiments.realtime_video.cost_cases import cases, model_frames, scheduling_probe, select, write_fixtures
from experiments.realtime_video.provider import DIRECTORY, RealtimeError, RealtimeProvider, credentials


ARMS = (
    ("large_6", "gpt-realtime-2.1", "six"),
    ("mini_6", "gpt-realtime-2.1-mini", "six"),
    ("mini_2", "gpt-realtime-2.1-mini", "endpoints"),
    ("mini_change_2", "gpt-realtime-2.1-mini", "change"),
)
# USD / million tokens; verified 2026-10-31 against official pricing.
RATES = {
    "gpt-realtime-2.1": {"text": "4", "image": "5", "cached_text": ".4", "cached_image": ".5", "output": "24"},
    "gpt-realtime-2.1-mini": {"text": ".6", "image": ".8", "cached_text": ".06", "cached_image": ".08", "output": "2.4"},
}
CONTEXT = "게임 방송 화면입니다. 소리는 제공되지 않습니다."


def dollars(usage, model):
    """Include failed outputs, cached modalities, and reasoning exactly once."""
    if not isinstance(usage, dict):
        raise ValueError("Missing token usage")
    details = usage["input_token_details"]
    cached = details.get("cached_tokens_details", {})
    counts = [usage["input_tokens"], usage["output_tokens"], details["text_tokens"], details["image_tokens"],
              details.get("cached_tokens", 0), cached.get("text_tokens", 0), cached.get("image_tokens", 0)]
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("Invalid token usage")
    if details.get("audio_tokens", 0) or usage.get("output_token_details", {}).get("audio_tokens", 0):
        raise ValueError("Unexpected audio usage")
    if (details["text_tokens"]+details["image_tokens"] != usage["input_tokens"]
            or cached.get("text_tokens", 0) > details["text_tokens"]
            or cached.get("image_tokens", 0) > details["image_tokens"]
            or cached.get("text_tokens", 0)+cached.get("image_tokens", 0) != details.get("cached_tokens", 0)):
        raise ValueError("Inconsistent token usage")
    rate = {key: Decimal(value) for key, value in RATES[model].items()}
    amount = Decimal(usage["output_tokens"]) * rate["output"]
    for modality in ("text", "image"):
        reused = cached.get(modality+"_tokens", 0)
        amount += (details[modality+"_tokens"]-reused)*rate[modality] + reused*rate["cached_"+modality]
    return float(amount / Decimal(1000000))


class MeasuredProvider(RealtimeProvider):
    """Capture diagnostic output only for these explicit synthetic comparisons."""
    def __init__(self, key, model):
        super().__init__(key, model)
        self.usage = self.response_status = self.raw_text = None
        self.output = None

    async def _receive(self):
        event = await super()._receive()
        if event.get("type") == "response.done":
            response = event.get("response", {})
            self.usage = response.get("usage")
            self.response_status = response.get("status")
            self.output = response.get("output", [])
            self.raw_text = "\n".join(item.get("arguments", "") if item.get("type") == "function_call" else
                "".join(part.get("text", "") for part in item.get("content", [])
                        if isinstance(part, dict) and part.get("type") in ("text", "output_text"))
                for item in self.output if isinstance(item, dict))
        return event


async def trial(case, arm, repeat, key, factory=MeasuredProvider):
    name, model, policy = arm
    indices, change = select(case, policy)
    row = {"arm": name, "model": model, "case": case.name, "repeat": repeat,
           "expected": case.expected, "selected_sequences": [i+1 for i in indices], "change_score": change,
           "input_sha256": [hashlib.sha256(case.images[i]).hexdigest() for i in indices],
           "called": False, "valid": False, "cost_usd": 0.0, "decision": None,
           "event_visible_in_selected_frames": bool(set(i+1 for i in indices) & set(case.evidence_sequences))}
    if not indices:
        row.update(status="skipped_unchanged", decision={"action": "WAIT", "comment": "", "evidence_frame_id": ""})
    else:
        provider = factory(key, model)
        started = None
        try:
            await provider.open()
            for frame in model_frames(case, indices, time.monotonic()):
                await provider.push_frame(frame)
            row["called"] = True
            started = time.monotonic()
            decision, _, _ = await provider.analyze("witty_friend", CONTEXT, [])
            row.update(status="completed", valid=True, decision=decision)
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__)
            if isinstance(exc, RealtimeError):
                row["error"] = str(exc)  # Provider errors are sanitized; never dump network exceptions.
        finally:
            if started is not None:
                row["analysis_ms"] = round((time.monotonic()-started)*1000)
            row.update(usage=provider.usage, response_status=provider.response_status, raw_text=provider.raw_text)
            row["output"] = getattr(provider, "output", None)
            await provider.close()
        if row["called"]:
            try:
                row["cost_usd"] = dollars(row["usage"], model)
            except (ValueError, KeyError, TypeError):
                row["cost_usd"] = None
                row["accounting_error"] = "Unknown usage; stop rather than count as free."
    decision = row["decision"]
    row["action_correct"] = bool(decision and decision["action"] == case.expected)
    row["false_reaction"] = bool(decision and decision["action"] == "REACT" and case.expected == "WAIT")
    row["missed_event"] = case.expected == "REACT" and not row["action_correct"]
    row["evidence_shows_event"] = bool(decision and decision["action"] == "REACT" and
        decision["evidence_frame_id"] in {f"frame_{sequence:08d}" for sequence in case.evidence_sequences})
    return row


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["arm"]].append(row)
    summaries = {}
    for name, items in groups.items():
        calls = [row for row in items if row["called"]]
        known = all(row["cost_usd"] is not None for row in items)
        amount = sum(row["cost_usd"] or 0 for row in items)
        latencies = [row["analysis_ms"] for row in calls if "analysis_ms" in row]
        summaries[name] = {
            "trials": len(items), "api_calls": len(calls), "skipped": sum(row["status"] == "skipped_unchanged" for row in items),
            "valid_responses": sum(row["valid"] for row in items),
            "correct_actions": sum(row["action_correct"] for row in items),
            "false_reactions": sum(row["false_reaction"] for row in items),
            "missed_events": sum(row["missed_event"] for row in items),
            "grounded_reactions": sum(row["evidence_shows_event"] for row in items),
            "total_usd": round(amount, 8) if known else None,
            "mean_call_usd": round(amount/len(calls), 8) if known and calls else None,
            "median_analysis_ms": statistics.median(latencies) if latencies else None,
        }
    return summaries


def write_report(path, report):
    report["summary"] = summarize(report["trials"])
    (path / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 화면 AI 비용 비교 결과", "", f"상태: {report['status']}", "",
             "직접 만든 합성 장면 6개. 실제 방송 품질·시간당 요금의 실측 결과가 아닙니다.", "",
             "| 조건 | API 호출 | 생략 | 유효 응답 | 행동 일치 | 오반응 | 사건 누락 | 총 USD | 판단 중앙값(ms) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, data in report["summary"].items():
        lines.append(f"| {name} | {data['api_calls']} | {data['skipped']} | {data['valid_responses']} | "
                     f"{data['correct_actions']}/{data['trials']} | {data['false_reactions']} | "
                     f"{data['missed_events']} | {data['total_usd']} | {data['median_analysis_ms']} |")
    lines += ["", "실패 응답 비용을 포함합니다. 생략은 API 유효 응답 수에 포함하지 않습니다.", "",
              "![동일 입력 장면](fixtures/contact_sheet.jpg)", "", "## 응답 원문", ""]
    for row in report["trials"]:
        text = row.get("raw_text") or ("[API 호출 생략]" if not row["called"] else "[응답 없음]")
        lines += [f"### {row['case']} / {row['arm']} / 반복 {row['repeat']}", "",
                  f"상태: {row['status']}, 선택 프레임: {row['selected_sequences']}, 정답: {row['expected']}", "",
                  "    " + text.replace("\n", "\n    "), ""]
    lines += ["## 별도 오프라인 스케줄 검사", "", "60초 동안 모든 응답이 REACT이고 추론 시간이 1.5초라는 가정입니다. "
              "실제 API 결과를 재생한 것은 아닙니다.", "", "```json", json.dumps(report["scheduler_probe"], indent=2), "```", "",
              "단가: https://developers.openai.com/api/docs/pricing (2026-10-31)"]
    (path / "results.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


async def run(args):
    values = cases()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = DIRECTORY / "runs" / ("cost_"+timestamp)
    path.mkdir(parents=True)
    write_fixtures(path / "fixtures", values)
    plan = (DIRECTORY / "EXPERIMENT_PLAN.md").read_bytes()
    report = {"status": "prepared", "created_utc": timestamp, "synthetic": True, "screen_captures": 0, "audio_inputs": 0,
              "plan_sha256": hashlib.sha256(plan).hexdigest(), "provider_sha256": hashlib.sha256((DIRECTORY/"provider.py").read_bytes()).hexdigest(),
              "pricing_date": "2026-10-31", "rates_usd_per_million": RATES, "budget_usd": args.budget_usd,
              "repeats": args.repeats, "max_calls": 48, "reserve_before_call_usd": .25,
              "scheduler_probe": {"baseline_5s": scheduling_probe(5, False), "precall_cooldown_5s": scheduling_probe(5, True),
                                  "precall_cooldown_10s": scheduling_probe(10, True)}, "trials": []}
    (path / "plan.md").write_bytes(plan)
    write_report(path, report)
    print(json.dumps({"report": str(path / "results.md"), "mode": "live" if args.live else "offline"}), flush=True)
    if not args.live:
        return 0
    key, _ = credentials()
    total, called = 0.0, 0
    report["status"] = "running"
    try:
        for repeat in range(1, args.repeats+1):
            for case_index, case in enumerate(values):
                offset = (case_index+repeat-1) % len(ARMS)
                for arm in ARMS[offset:]+ARMS[:offset]:
                    selected, _ = select(case, arm[2])
                    if selected and (called >= 48 or total+.25 > args.budget_usd):
                        report["status"] = "stopped_budget"
                        return 2
                    row = await trial(case, arm, repeat, key)
                    report["trials"].append(row)
                    called += int(row["called"])
                    total += row["cost_usd"] or 0
                    write_report(path, report)
                    print(json.dumps({"trial": len(report["trials"]), "arm": row["arm"], "case": case.name,
                                      "status": row["status"], "known_total_usd": round(total, 6)}, ensure_ascii=False), flush=True)
                    if row.get("accounting_error") or (row["status"] == "failed" and not row["called"]):
                        report["status"] = "stopped_connection_or_usage"
                        return 2
        report["status"] = "complete"
        return 0
    finally:
        write_report(path, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly send synthetic images to paid APIs")
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=2)
    parser.add_argument("--budget-usd", type=float, default=1.0)
    args = parser.parse_args()
    if not .25 <= args.budget_usd <= 1:
        parser.error("Budget must be between $0.25 and $1.00")
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
