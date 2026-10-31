"""Two post-comparison synthetic calls to inspect empty text output shapes."""

import argparse
import asyncio
from datetime import datetime, timezone
import json

from experiments.realtime_video.cost_benchmark import ARMS, MeasuredProvider, trial
from experiments.realtime_video.cost_cases import cases
from experiments.realtime_video.provider import DIRECTORY, credentials


async def run():
    key, _ = credentials()
    collected = []

    class Probe(MeasuredProvider):
        output = None

        async def _receive(self):
            event = await super()._receive()
            if event.get("type") == "response.done":
                self.output = event.get("response", {}).get("output", [])
            return event

    instances = []

    def factory(*args):
        provider = Probe(*args)
        instances.append(provider)
        return provider

    values = cases()
    for case in (values[0], values[2]):
        row = await trial(case, ARMS[1], 1, key, factory=factory)
        row["full_synthetic_output"] = instances[-1].output
        collected.append(row)
        if row.get("accounting_error") or not row["called"]:
            break
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = DIRECTORY / "runs" / ("output_probe_"+stamp+".json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"purpose": "Post-hoc diagnostic, excluded from comparison metrics",
        "synthetic": True, "screen_captures": 0, "audio_inputs": 0, "trials": collected}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(path), "calls": sum(row["called"] for row in collected),
                      "known_cost_usd": sum(row["cost_usd"] or 0 for row in collected)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    if not parser.parse_args().live:
        parser.error("Use --live to authorize two paid synthetic diagnostic requests")
    asyncio.run(run())
