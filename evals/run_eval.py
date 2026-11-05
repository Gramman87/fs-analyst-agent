"""
Run the agent against every case in cases.py and score it on four dimensions:

  1. Routing     did the lead call (at least) the expected sub-agents?
  2. Coverage    does the memo mention the required terms as whole words?
  3. Judge       a separate model grades the memo against a rubric, 1-5. Anything below 3 fails.
  4. Grounding   figures in the memo that appear in no briefing. Reported for review, not a failure,
                 since a memo can legitimately derive a number.

This calls the live API and spends credits, so it isn't part of CI. Exits non-zero if any case fails.
Run it from the repo root:

    ANTHROPIC_API_KEY=... python evals/run_eval.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

# Make api/ importable from repo root
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, HERE)

from agents import client, run_lead  # noqa: E402
from cases import CASES  # noqa: E402
from scoring import (  # noqa: E402
    JUDGE_SCHEMA,
    case_passed,
    check_coverage,
    check_routing,
    parse_judge,
    unsupported_figures,
)

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-opus-4-7")

JUDGE_SYSTEM = """You are a senior sell-side research director grading an analyst memo. Score on three dimensions, 1-5 each:

- accuracy: does the memo correctly reflect the sub-agent briefings (no hallucinated numbers, no contradictions)?
- specificity: does it cite specific tickers, sectors, drivers — not vague platitudes?
- decisiveness: does it directly answer the client question and pick a side, or does it hedge?

Also give a one-sentence critique."""


def score_one(case: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    # A long eval shouldn't be cut off by the serverless function's deadline.
    result = run_lead(case["query"], case["holdings"], deadline_s=300)
    elapsed_s = time.time() - t0

    called_tools = {t["name"] for t in result["trace"] if t["kind"] == "tool_call"}
    routing_pass = check_routing(called_tools, case["expected_tools"])

    memo = result["memo"]
    missing_mentions = check_coverage(memo, case["must_mention"])
    briefings = [t["text"] for t in result["trace"] if t["kind"] == "tool_result"]

    # Claude-as-judge
    judge_resp = client().messages.create(
        model=JUDGE_MODEL,
        max_tokens=1500,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": JUDGE_SCHEMA},
        },
        system=JUDGE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Client question:\n{case['query']}\n\n"
                    f"Portfolio:\n{json.dumps(case['holdings'])}\n\n"
                    f"Sub-agent briefings the analyst received:\n"
                    + "\n---\n".join(
                        f"[{t['name']}]\n{t['text']}"
                        for t in result["trace"]
                        if t["kind"] == "tool_result"
                    )
                    + f"\n\nMemo to grade:\n{memo}"
                ),
            }
        ],
    )
    judge = parse_judge("".join(b.text for b in judge_resp.content if b.type == "text"))

    return {
        "id": case["id"],
        "routing_pass": routing_pass,
        "called_tools": sorted(called_tools),
        "coverage_pass": not missing_mentions,
        "missing_mentions": missing_mentions,
        "judge": judge,
        "unsupported_figures": unsupported_figures(memo, briefings, case["holdings"]),
        "elapsed_s": round(elapsed_s, 1),
        "usage": result.get("usage", {}),
    }


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. This eval calls the live API.")
        return 2

    print(f"Running {len(CASES)} eval cases against the agent…\n")
    results = []
    for case in CASES:
        print(f"  · {case['id']} …", end=" ", flush=True)
        try:
            r = score_one(case)
            results.append(r)
            print(f"done in {r['elapsed_s']}s")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"id": case["id"], "error": str(e)})

    print()
    print(f"{'case':32s} {'routing':>8s} {'coverage':>9s} {'acc':>4s} {'spec':>5s} {'dec':>4s}")
    print("-" * 70)
    routing_passes = coverage_passes = 0
    judge_totals = {"accuracy": 0, "specificity": 0, "decisiveness": 0}
    counted = 0
    for r in results:
        if "error" in r:
            print(f"{r['id']:32s} ERROR: {r['error']}")
            continue
        counted += 1
        routing_passes += int(r["routing_pass"])
        coverage_passes += int(r["coverage_pass"])
        j = r["judge"]
        for k in judge_totals:
            judge_totals[k] += int(j.get(k) or 0)
        print(
            f"{r['id']:32s} "
            f"{'PASS' if r['routing_pass'] else 'FAIL':>8s} "
            f"{'PASS' if r['coverage_pass'] else 'FAIL':>9s} "
            f"{j.get('accuracy',0):>4} "
            f"{j.get('specificity',0):>5} "
            f"{j.get('decisiveness',0):>4}"
        )
        if r["unsupported_figures"]:
            print(f"{'':32s} check these figures: {', '.join(r['unsupported_figures'])}")

    if counted:
        print()
        print(f"Routing pass rate:   {routing_passes}/{counted}")
        print(f"Coverage pass rate:  {coverage_passes}/{counted}")
        print(
            "Judge averages:      "
            f"acc={judge_totals['accuracy']/counted:.2f}  "
            f"spec={judge_totals['specificity']/counted:.2f}  "
            f"dec={judge_totals['decisiveness']/counted:.2f}"
        )

    # Save full results for review
    out_path = os.path.join(HERE, "last_run.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results: {out_path}")

    return 0 if all(case_passed(r) for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
