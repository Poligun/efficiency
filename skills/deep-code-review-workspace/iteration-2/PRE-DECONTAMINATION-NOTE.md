# Why `with_skill-pre-decontamination/` directories exist

The first iteration-2 with_skill runs (evals 2–4, completed 2026-07-30 22:06–22:25)
loaded the skill as of commit a722ba4 — before `f586e62 "Remove contamination"`
(22:31:38) landed. Proof: eval-2's run-notes report, as friction, the absence of the
exact SKILL.md paragraphs f586e62 added ("Don't wait idly", the A3-dispatch re-keying
of knowledge-base resolution, the Coverage user-skip/script-skip distinction), so the
SKILL.md those runs read predates f586e62 — and therefore still contained the
eval-target contamination that commit removed.

Those outputs are preserved here for reference (their run-notes drove real skill
fixes) but are excluded from the iteration-2 benchmark. The `with_skill/` dirs
contain the clean re-runs. Baselines (`without_skill/`) never load the skill and are
unaffected.

Eval-1 with_skill was never run before decontamination; it has no archived copy.
