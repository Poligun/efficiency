#!/usr/bin/env python3
"""Assemble benchmark.json from per-run grading.json + timing.json.

Field names follow the eval-viewer schema exactly (`configuration`, nested
`result`, `expectations` with `text`/`passed`/`evidence`) — the viewer reads
these literally and renders zeros if they drift.
"""

from __future__ import annotations

import glob
import json
import os
import sys

ITER = sys.argv[1] if len(sys.argv) > 1 else "iteration-1"
SKILL = "deep-code-review"

runs = []
for eval_dir in sorted(glob.glob(os.path.join(ITER, "eval-*"))):
    meta_path = os.path.join(eval_dir, "eval_metadata.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    eval_name = meta.get("eval_name", os.path.basename(eval_dir))
    eval_id = meta.get("eval_id", 0)

    # with_skill first, then its baseline — the viewer pairs them in order.
    for config in ("with_skill", "without_skill"):
        d = os.path.join(eval_dir, config)
        g_path, t_path = os.path.join(d, "grading.json"), os.path.join(d, "timing.json")
        if not os.path.exists(g_path):
            print(f"  ! missing grading.json: {d}", file=sys.stderr)
            continue
        g = json.load(open(g_path))
        t = json.load(open(t_path)) if os.path.exists(t_path) else {}

        exps = g.get("expectations", [])
        passed = sum(1 for e in exps if e.get("passed"))
        total = len(exps) or g.get("total", 0)

        runs.append({
            "eval_id": eval_id,
            "eval_name": eval_name,
            "configuration": config,
            "run_number": 1,
            "result": {
                "pass_rate": round(passed / total, 4) if total else 0.0,
                "passed": passed,
                "failed": total - passed,
                "total": total,
                "time_seconds": round(t.get("duration_ms", 0) / 1000, 1),
                "tokens": t.get("total_tokens", 0),
                "tool_calls": t.get("tool_uses", 0),
                "errors": 0,
            },
            "expectations": exps,
        })

benchmark = {
    "metadata": {
        "skill_name": SKILL,
        "skill_path": f"/Users/yuhanzhao/GitHub/efficiency/skills/{SKILL}",
        "executor_model": "claude-opus-5[1m]",
        "analyzer_model": "claude-opus-5[1m]",
        "timestamp": "2026-07-29T00:00:00Z",
        "evals_run": sorted({r["eval_id"] for r in runs}),
        "runs_per_configuration": 1,
        "caveat": (
            "with_skill runs used a version of the skill that contained examples drawn "
            "from this eval target. Findings matching those examples are not independent "
            "evidence. Contamination was removed after the run; iteration 2 re-measures."
        ),
    },
    "runs": runs,
}

out = os.path.join(ITER, "benchmark.json")
json.dump(benchmark, open(out, "w"), indent=2)

# Human-readable summary
lines = ["# Benchmark — deep-code-review, iteration 1", ""]
lines.append("| Eval | Config | Pass | Rate | Time (s) | Tokens | Tools |")
lines.append("|---|---|---|---|---|---|---|")
for r in runs:
    res = r["result"]
    lines.append(f"| {r['eval_name']} | {r['configuration']} | "
                 f"{res['passed']}/{res['total']} | {res['pass_rate']:.0%} | "
                 f"{res['time_seconds']:.0f} | {res['tokens']:,} | {res['tool_calls']} |")

for cfg in ("with_skill", "without_skill"):
    sel = [r for r in runs if r["configuration"] == cfg]
    if not sel:
        continue
    tp = sum(r["result"]["passed"] for r in sel)
    tt = sum(r["result"]["total"] for r in sel)
    tok = sum(r["result"]["tokens"] for r in sel)
    sec = sum(r["result"]["time_seconds"] for r in sel)
    lines += ["", f"**{cfg}** — {tp}/{tt} assertions ({tp/tt:.0%}), "
                  f"{tok:,} tokens, {sec/60:.0f} min total"]

lines += ["", "> " + benchmark["metadata"]["caveat"]]
open(os.path.join(ITER, "benchmark.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
