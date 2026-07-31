# Output contract

Load this in Step 6. Which shape you produce depends on the mode you detected in Step 1.

## Subagent mode

You were dispatched by `deep-code-review`. Your output is data, not a message — the
orchestrator parses it and merges it with other agents' findings.

Three rules, each protecting something specific:

- **One fenced JSON block, at most one line of prose.** No reasoning, no file listings, no
  narration of what you explored. The orchestrator's context is a shared resource and
  yours is the largest single contribution to it.
- **Never write memory.** Return `memory_proposals`. You can't obtain user approval, and
  several sibling agents writing the same file is a merge conflict by construction.
- **Findings must be self-contained.** The orchestrator should never have to re-open a file
  to understand one. Quote enough.

```json
{
  "skill": "business-logic-review",
  "base": "<sha>", "head": "<sha>", "files_reviewed": 0,
  "angles_run": ["A1","A2","A3","A4","A5","A6","A7","A8","A9"],
  "angles_skipped": {"A10": "no new concurrency primitives in the diff"},
  "findings": [
    {
      "id": "BLR-1",
      "title": "<the claim alone, no rationale>",
      "severity": "CRITICAL",
      "fix_clarity": "SCOPED",
      "angle": "A7 taint",
      "anchor": "<path>:<line>",
      "committed": true,
      "description": "<2-4 sentences: the mechanism, and the concrete consequence.>",
      "evidence": [
        {"file": "<path>", "line": 0, "quote": "<the line, verbatim from the current tree>"},
        {"file": "<path>", "line": 0, "quote": "<a second line if the claim needs two anchors>"}
      ],
      "trace": "<specific input or state> → <what the code does with it> → <the exact wrong output, crash, or corrupted state>",
      "suggested_fix": "<what to do; or the open question if this needs a decision>",
      "memory_refs": ["<entry ids this rests on, if any>"],
      "intent_dependency": "none"
    }
  ],
  "intent_questions": [
    {"id": "Q-1",
     "question": "<what you need a human to decide, phrased so one line answers it>",
     "blocks": ["BLR-3"],
     "default_assumption": "<what you assumed in the meantime>"}
  ],
  "memory_proposals": [
    {"file": "domains/<slug>.md", "op": "add", "entry_id": "MAP-<slug>-002",
     "body": "…the full markdown entry…"}
  ],
  "notes": "Knowledge base absent; proposals would seed it."
}
```

**`intent_dependency` is the field the orchestrator most needs.** Values: `none` (the
finding stands on code alone), `doc` (rests on a documented promise — capped at MEDIUM),
`user` (rests on confirmed human intent), `unresolved` (only a defect *if* an unconfirmed
intent holds). Marking `unresolved` honestly lets the orchestrator group those into one
question to the human instead of shipping several shaky findings — which is a much better
outcome than either dropping them or asserting them.

Severity and fix-clarity values come from
`../deep-code-review/references/severity-rubric.md` and must match exactly. The
orchestrator merges across agents; divergent vocabularies break the merge.

## Human mode

Markdown, and short at the top. The reader is deciding in about ninety seconds whether to
act on each finding.

```markdown
## Review: [what this branch does, one line]

[2-3 sentence verdict. Lead with whatever would most change their plan.]

**Coverage.** [Which angles fired, which were gated out and why, whether they ran inline
or as subagents, and anything you cut to stay under the cap. If you skipped something a
reader might expect, say so — an unstated gap reads as full coverage. This is the line the
severity rubric means when it says to disclose what was cut.]

### [SEVERITY] — [claim, ≤70 chars]
`path/to/file.rs:104` · fix: [mechanical | scoped | needs a decision]

[2-4 sentences: the mechanism, and the concrete consequence.]

```
[quoted line(s) from the current tree]
```

**Trace.** [Specific inputs or state → the exact wrong output. Concrete numbers where
they exist — "120 messages an hour" lands where "repeatedly" doesn't.]

**Fix.** [What to do. If it needs a decision, state the question instead of guessing.]

## Questions I couldn't answer from the code
[The intent questions. Say what each one would change if answered one way or the other —
that's what makes them worth the reader's time rather than a list of things you didn't
know.]

## Proposed memory update
[The diff. Then wait for approval before writing.]
```

The questions section is the highest-value part for a human reader, because answering one
permanently upgrades the memory from inference to confirmed intent. Frame each as a real
question with stakes attached, not as a disclaimer.

## Both modes

**Order findings** by severity descending, then fix clarity ascending within a band —
mechanical fixes first, so the reader builds momentum before hitting the one that needs a
meeting.

**Cap at roughly 12 findings.** Past that, readers stop distinguishing between them.
Correctness outranks hygiene when you cut, and say what you cut.

**An empty findings list is a real result.** Return it without editorializing. A reviewer
that always finds something is a reviewer whose findings mean nothing.
