# Implementation-loop retrospective: six autonomous sessions on phaethon

Status: findings and proposals, awaiting the owner's answers to the open questions at the end.
Date: 2026-10-25.
Audience: the owner of the efficiency and phaethon repositories, deciding what to change in the loop, the review skills, and the writing rules.
Prerequisites: familiarity with `agents/implementation-loop.md` in phaethon, the `deep-code-review` and `tech-writing` skills here, and the Claude Code harness (subagents, hooks, worktrees).
Evidence: [implementation-loop-retrospective/](implementation-loop-retrospective/) holds the per-session analyses, the per-PR tables, the harness feature survey, the six PR 49 review reports, and the transcript condenser that produced the numbers.

## Verdict

The loop produced sixteen merged PRs in about nineteen hours of agent activity for roughly $200, and the implementation itself was fast and largely correct: a 2,000 to 3,000 line PR took 4 to 18 minutes of session time to write. The cost and the delay sit elsewhere, in four places. The sessions never reset their context, so cache reads of a 350K to 625K token prefix were the largest token cost. The sessions blocked on the owner for decisions that the owner then accepted as recommended in 19 of 21 cases, and the two longest stalls (11 hours and 3 hours) held independent work hostage behind one question. The review rounds found real bugs in every PR, including about ten regressions introduced by the previous round's fixes, but each round re-read the whole branch from zero, the review skill's verifier and knowledge-base steps never ran, and one PR took six rounds because fix rounds kept adding mechanism. Finally, the prose that reached the owner, in questions, status reports and GUI labels, used product, code and tracker vocabulary interchangeably, which produced one reversed decision, two clarification turns per in-game check, and a tab the owner could not place.

The sections below give the evidence, then the proposals split into what belongs in this repository's skills and what belongs in phaethon, then the open questions. Each proposal names the evidence it rests on.

## 1. What happened, by the numbers

| Session | Span | Active time | PRs | Peak context (tokens) | Questions asked | Reviewer agents | Estimated cost |
|---|---|---|---|---|---|---|---|
| 64117bac | 1.2 h | 1.2 h | 23, 24, 25, 26, 27 | 359K | 1 | 13 | $19 |
| c01a72e3 | 3.2 h | 2.0 h | 29, 30 | 536K | 4 | 20 | $40 |
| 101ca9b8 | 10.9 h | 2.1 h | 31, 32, 33, 34, 36 | 609K | 3 | 23 | $48 |
| 69c7d0fb | 8.5 h | 2.2 h | 37, 40, 44 | 625K | 6 | 17 | $56 |
| aadd6222 | 1.0 h | 0.7 h | 46, 48 | 344K | 8 | 8 | $15 |
| 0e5c87c2 | 12.9 h | 0.9 h | 49 | 393K | 5 | 9 | $23 |

The cost column is computed from the transcripts' usage fields at Opus 5.5 list prices (cache reads at $0.20 per million tokens); the one session that recorded its own cost ($20) agrees with the estimate. Across the six sessions the main threads replayed 358 million cached tokens over 1,178 API calls, which at list price is about $72 of the $125 main-thread total. No session compacted; the 1M-window default compacts at about 967K tokens, and every session paused by its own judgment first.

Per PR, the split between writing and the rest is lopsided. Implementation time (previous merge to PR open, excluding idle gaps over ten hours) summed to about 18 hours across all PRs, but that figure includes every wait on the owner; the sessions' own writing time per PR was 4 to 18 minutes for the large PRs. Review plus fixes (PR open to merge) summed to about 25 hours, of which two PRs that waited on the owner contributed 16 hours. Review rounds ran 1.5 to 12.5 minutes each, with a median near 5 minutes, and the loop ran 38 rounds over 17 PRs for roughly 290 findings. Tables per PR are in [evidence.md](implementation-loop-retrospective/evidence.md).

## 2. Findings

### 2.1 Prose that reaches a human

The owner's two observations hold up on the transcripts. The house-voice scanner, run over 160K characters of the sessions' assistant prose, reports about 100 anthropomorphic-verb candidates (S2), with "refuses", "wants", "expects", "ignores" and "honours" applied to clippy, bazelisk, the loader and the library. The negation habit is measurable: "does not" appears twice in the same corpus, against 30 uses of "never" and a dozen "verb no thing" constructions ("writes no value", "needs no action", "changes no files", "holds no logic"). Neither pattern is in the corpus as a rule: the digest bans anthropomorphism but the sessions produce it anyway, and nothing bans object-negation, which the sessions seem to reach for because the digest also asks for compression.

Two further patterns matter more than those two for comprehension:

- **Terms without a layer.** "Gate" names the Bazel test gate in the loop document, the INI recipe in the PRD, a recorded change entry, an `if` block and a verb in the same session. "Key" names a keyboard binding in a `[Key]` section, the variable `$swapkey0`, and the lookup key for a user label; the owner reversed a decision 49 minutes after taking it because the question had used two of these without saying which (c01a72e3, 04:23). "Package", "slot", "profile", "family", "slug", "entry", "promote" and "working tree" are PRD or ADR terms that the questions, status reports and PR comments use as if settled, and "the name route" is an enum variant presented as a product term. The PRD's Concepts table defines most of them, but nothing a question or a GUI label shows says "this is a PRD term" or links to the table, and "gate", "promote" and "slug" were added to the vocabulary after the table was written.
- **Reports written for nobody.** Each session wrote five to eight status reports of 300 to 500 words to a user who was absent (user turns per session: one to four, except the session with in-game checks), each restating the PR body and the PR comments. Those reports are where most of the anthropomorphism and the bold-label bullets live, and they cost output tokens and context on every later turn.

### 2.2 Questions to the owner

The sessions put 21 questions to the owner in 12 calls. The owner took the recommended option 19 times; the two exceptions were "I just installed it" and one product note on add-on mods. Three questions could have been settled from the PRD (the pairwise-check API, F10 reload after a rebind, the test-input source), and one asked the owner to choose the session's starting task because the continuation prompt said to. The questions that worked best stated a contradiction between two documents, or used a named example ("two Belle mods both on her Basic outfit"); the ones that did not stacked three to five undefined nouns per sentence ("promoting a gated package to the shared slot", "head IB 8b067f99 ... Skin-only (sharing unknown)").

The timing hurt more than the wording. In session 0e5c87c2 the one decision the owner had to make was asked at 06:28 before any of the seven independent findings from the same review round were fixed, and the branch sat untouched for 11 hours 26 minutes. In session 69c7d0fb the same shape cost 175 minutes. In session c01a72e3, 39 percent of the session was spent waiting on the owner. A question asked after the independent work is committed costs the same wait but leaves the branch further along; a question phrased as a default the owner can veto costs no wait at all.

### 2.3 GUI vocabulary

The tabs "Library", "Characters" and "Package" came from the PRD's "GUI pages" section, which the owner ratified in the grilling sessions of 2026-10-14 and 2026-10-23. The PRD names are model names, not user tasks: a "package" is "a version considered as a deployable unit", which is correct and tells a user nothing about what the tab does. The owner's reaction ("what happens if I directly go to this tab? why is it on the same level as library tab") was a structural question that followed from the vocabulary gap, and the agent removed the tab in response to a question rather than a request. No page carried a one-line purpose text; no label defined "package", "slot", "clash", "global", "promoted" or "pending"; the similar-family lines showed slugified ids; and the empty state said "No mods yet." without saying that files can be dropped. Three Opus reviewers read the GUI code twice for logic and never asked what a user would understand from it, and nobody ran the window before the owner did, who found five rendering defects in one look. The PR 34 layout was replaced in PR 44 before any human saw it.

### 2.4 The review skill

Across 38 rounds the context-free design did what it was built for. The findings that changed behaviour came from reviewers reading primary material the author had skipped: the live `Mods` folder (the RabbitFX namespace bug), the vendored `junction` crate source, the fixture INIs grepped by section, the 3DMigoto loader source, and the fixture archives regenerated by hand. About ten findings were regressions the previous round's fixes had introduced, which is the strongest argument for re-reviewing fix commits. False positives that reached the author were rare and each was declined with a reason.

The skill as written and the skill as run are two different processes:

| Step in SKILL.md | What happened in 38 rounds |
|---|---|
| `python3 scope_detect.py` | Failed on every run on this Windows host ("Python was not found"); each reviewer retried with `py` or `python`, several needed `PYTHONUTF8=1`, one gave up and scoped by hand. Two to three wasted calls per round. |
| A4 convention scout on haiku | Ran in about six rounds; zero findings every time; skipped as "weak" otherwise. |
| Step 5 verifiers (sonnet, haiku) | Never dispatched by an Opus or Sonnet orchestrator. Every report said the orchestrator "checked by reading" and most stamped findings CONFIRMED anyway. The Fable orchestrator in the experiment was the only run that dispatched verifiers. |
| Knowledge base and memory proposals | No `.claude/knowledge/` was ever created, because the reviewer is a non-interactive subagent and may not ask; the business-logic agent's proposals were discarded in every run (at least fifteen times), and later rounds re-derived the same loader facts from source. |
| "Still dispatch business logic" for a focused diff | Ignored in at least four rounds; PR 24 round 1 skipped A3 and missed the one HIGH that round 2's A3 found. |
| Fresh-context finders | Orchestrators handed nested finders their thesis, and in PR 49 round 3 the API finder's prompt contained the findings the orchestrator wanted back. |
| `/code-review` at medium | The wrapper agent asked for medium; the skill ran with a "high effort, recall, no verify" banner each time; the dispatching agent learned to add "check each finding against the source", which halved the surviving list. |

Three structural gaps are not in the skill at all. There is no delta mode: a second round receives the same prompt as the first, re-reads every file, re-derives a thesis, and carries no record of what was declined, so PR 30's six rounds reversed two policies and re-raised a declined finding. There is no stop rule in the loop for rounds: "re-review when fixes changed logic" is satisfied forever on a logic-heavy PR, and the agent improvised a stop at round five of PR 30 and then met a HIGH. There is no runtime aspect: nothing runs the binary or the window, so the defects the owner saw in one look were invisible to three reviewers.

The experiment on the merged PR 49 (all three original rounds already applied) compares orchestrator tiers with the finders pinned to Opus as the skill specifies:

| Orchestrator | Wall clock | Subagents | Verifiers ran | Findings | Estimated cost |
|---|---|---|---|---|---|
| Opus 5.5 medium | 7 min | 3 | no | 1 MEDIUM (duplicate detection section when the body override sits in a peer INI), 2 LOW | $3.0 |
| Sonnet 5.5 medium | 12 min | 3 | no | 2 MEDIUM (one latent on a future registry change; the persisted `Vec<Slot>` type) | $4.0 |
| Fable 5.1 medium | 16 min | 6 | yes, three on Sonnet | 1 HIGH (a stale gate under a later recorded edit can never be dropped; trigger: rebind, then move slots), 1 MEDIUM (same as Opus's), 2 LOW | $7.9 |

All three found something the original three rounds had missed, and the Fable run was the only one that followed the skill's process. The reports are in [pr49-reviews/](implementation-loop-retrospective/pr49-reviews/) beside the three original rounds.

### 2.5 Loop mechanics

- **Pauses and continuation prompts.** Two sessions printed a continuation prompt with no pause condition (the owner's replies: "why are you giving me a continuation prompt when there's still plenty of context left"; "cache is still warm and looks like context window is still fine"). One session ended with "the earlier prompt still applies, except..." instead of a fresh block, leaving a "Waiting on" line that was wrong in two of three items. The "open owner question: fixture licensing" item rode four continuation prompts after ADR 0004 had settled it, and the owner's first question after an eight-hour gap was what it meant. The merge-then-check order for changes that need an in-game check is not stated, and PR 37 was tested in game on a binary built before the second review's fixes.
- **Idle time.** The main thread waited on reviewers for about 40 minutes per session with nothing in flight, while its context was replayed on every turn. The loop permits the wait but does not say what to do with it.
- **Environment friction that repeated.** Bash heredocs with backslashes failed at least fifteen times across the six sessions although a memory note recorded the cause after the first session; each session relearned to write edit scripts with the Write tool. Clippy's 100-line function limit, which `agents/build.md` does not mention, cost about twelve rebuild cycles. The rustfmt binary's location under the test runfiles was re-derived from nothing. `core.autocrlf` warnings were echoed into every commit. The docs cited issue numbers before the issues were created, twice.
- **Decisions taken alone.** The agents changed PRD sentences (mod-root rule, fixture layout, Ctrl+Alt+F10), decided reviewer NEEDS-DECISION items from the PRD, declined a HIGH on scope grounds, and designed features the ticket did not name (a family merge with redirects, a lock file, the credit-overlay suppression). Each was disclosed in a PR comment or a report; two were refuted a round later and cost two rounds each.
- **Reporting accuracy.** "17 tests pass" appeared 28 times where 17 is the number of test targets; one crate alone holds 86 test functions.

## 3. Proposals

Each proposal names where it goes. "Generic" means this repository's skills or a new skill; "phaethon" means the repository's own loop file, build reference or docs.

### 3.1 Writing rules (generic, tech-writing)

1. **Add a negation rule to the corpus.** Negate the verb, not the object: "does not write a value", not "writes no value"; "the page has no logic of its own" stays allowed when the object is the point. Add golden pairs and a deterministic candidate scan for `<verb> no|nothing` in `prose_checks.py`. Evidence: 2.1.
2. **Add a term-layer rule.** A coined or model-level term that reaches a human carries its layer the first time it appears in a message: product concept (link the glossary), code identifier (backticks), tracker item (#N), UI label (quotes). A message that needs more than two such terms per sentence is rewritten around an example. Evidence: 2.1, 2.2.
3. **Enforce deterministically, not by rewriting.** Run the scanner from a hook on the artifacts that persist (PR bodies, PR comments, question text, docs under `docs/`) and leave transient status text alone. The middle ground the owner asked for is exactly this split: the model's dialect is tolerated where nobody reads it later, and the persisted prose gets a mechanical check that costs no tokens. Evidence: 2.1, the scanner's hit counts.
4. **Cut the status reports.** The loop writes one report per pause and otherwise points at the PR. Evidence: 2.1.

### 3.2 Questions and decisions (generic, a loop skill; phaethon loop file until then)

5. **Decide-and-flag as the default.** When the agent has a recommendation and the choice is reversible, it proceeds with the recommendation, records it under a "Decisions taken" heading in the PR body and in the repository's decision log, and continues. It blocks only for an irreversible change, an external service, a product trade-off it cannot rank, or an in-game check. Evidence: 19 of 21 answers were the recommendation; the 11-hour and 175-minute stalls.
6. **Ask after the independent work.** A blocking question is asked only once every finding or step that does not depend on it is committed and pushed. Evidence: 2.2.
7. **A question template.** One sentence of situation in the owner's words with a concrete example, each model term glossed in brackets with its layer, at most two such terms per sentence, the options as consequences, and the recommendation first. The grilling skill's rule that "yes" accepts the recommendation applies. Evidence: the questions that worked versus the ones that stalled or reversed.
8. **New vocabulary goes in the glossary before it goes in a question or a label.** The PRD's Concepts table is the glossary; "gate", "promote", "slug" and "entry" were used for a day before any definition a human would see. The domain-modeling skill already owns the glossary format. Evidence: 2.1, 2.3.

### 3.3 GUI copy (generic rule, phaethon application)

9. **Two-column glossary.** Each concept gets an internal name and a user-facing word; labels, empty states and messages use the user-facing column ("mod" for package, "outfit" for an outfit slot, "character" for the grid) and never the internal one. The PRD's three page names are an open question below.
10. **Every page states its purpose in one line**, and every empty state says what the user can do there. Evidence: 2.3.
11. **Run the window before the human does.** A GUI PR gets a screenshot or a recorded run before the in-game check, and the review of a GUI diff gets a copy aspect: what a first-time user would understand from the visible strings. Evidence: five defects found by the owner in one look that three reviewers missed.

### 3.4 Review skill (generic, deep-code-review and business-logic-review)

12. **Make the host-portability fix.** Probe `py -3`, `python`, `python3` once and run the scripts with `-X utf8`; this is the open bug #24 with 38 rounds of evidence attached. Evidence: 2.4 table.
13. **Add a delta mode for repeat rounds.** The dispatching loop passes the previous report, the author's disposition comment and the range since the last round; the reviewer re-reads only the delta plus the files the delta touches, and treats declined findings as settled unless the fix changed the facts. Keep the first round context-free. Evidence: PR 30's six rounds, PR 49's three, the two reversed policies.
14. **Give rounds a budget.** The loop caps review rounds per PR (two, with a third only for a HIGH introduced by a fix) and says that a fix which adds mechanism becomes a ticket, not a commit on the branch. Evidence: PR 30 grew by 1,150 lines across its fix rounds and every HIGH after round 1 was in code a fix had added.
15. **Decide what the verifier and knowledge-base steps are.** Either the skill makes them run (a verifier batch is cheap on Sonnet, and the Fable run shows the process is followable), or the skill declares when the orchestrator's own reading suffices and the knowledge base is created by the loop once per repository rather than asked for by a subagent that cannot ask. Today the skill text describes a process that does not happen, and every Coverage line reports its absence. Evidence: 2.4 table.
16. **Keep finders fresh.** The orchestrator's hand-off to a finder carries the thesis and the scope, never candidate findings. Evidence: PR 49 round 3.
17. **Respect the effort argument in `/code-review`**, or stop asking for one; and make "check each finding against the source" part of the dispatch text. Evidence: the "high effort, recall, no verify" banner on every medium request.
18. **Name the primary material in the reviewer prompt.** The loop's prompt should list what exists on disk (local loader checkout, fixtures, the live install, generated outputs) so reviewers read it instead of downloading it. Evidence: the 3DMigoto source downloaded by one reviewer while another read the local checkout.
19. **Add a runtime aspect for GUI and CLI diffs**, or state that the skill does not cover behaviour that only shows when the program runs. Evidence: 2.3.

### 3.5 Loop mechanics (generic skill; phaethon loop file until then)

20. **State the pause conditions as a checklist the agent must quote** when it pauses, so a pause with no condition cannot be printed. Evidence: two premature continuation prompts.
21. **Re-verify "Waiting on" items against the repository** before printing a continuation prompt, and always print the whole block. Evidence: the fixture-licensing item, the "still applies, except" ending.
22. **The human gate tests the merge candidate.** For a change that needs an in-game check, the check runs on a binary built from the branch head after the last review fix, and the loop says whether the check gates the merge or follows it. Evidence: PR 37, PR 44.
23. **Use the reviewer's wait.** While a review runs, the main thread reads the next ticket's material or does nothing that grows its context. Evidence: 40 idle minutes per session at 600K context.
24. **Environment facts go in the build reference, not in memory.** Clippy's thresholds, the rustfmt path, the interpreter name, the heredoc rule and the CRLF setting belong in `agents/build.md` and are checked once per session. Evidence: fifteen heredoc failures after the memory note existed.
25. **Report test counts from the test log**, not from the target count. Evidence: "17 tests pass" 28 times.

### 3.6 Context resets without a human

The harness survey ([harness-features.md](implementation-loop-retrospective/harness-features.md)) rules out some options and supports three. No hook starts a successor session; a session cannot clear its own context from inside; subagent results return only to the caller; agent teams are experimental and interactive-only; the Workflow tool takes no mid-run user input. What does exist: automatic compaction with a `SessionStart` hook on the `compact` matcher whose stdout is injected afterwards; headless `claude -p` chaining by session id with a prompt on stdin; subagents with `isolation: "worktree"`, nesting to depth three, twenty concurrent; and `claude --worktree <name>` for parallel interactive sessions on one repository.

- **Option A, compaction as the reset.** Lower `autoCompactWindow` to about 200K, have the loop write a checkpoint file at every merge (the continuation block, kept current), and inject it from the compact hook. The human disappears from the handoff, and the context cost drops by about two thirds on the evidence in section 1. The risk is summary quality for work in flight, which the checkpoint file bounds. This is the cheapest change and composes with the others.
- **Option B, one PR per headless session.** A PowerShell driver runs `claude -p` with the continuation block on stdin, auto permission mode and a turn cap, reads the JSON result for the next block, and loops until the block says "Waiting on" something a human must do. Each PR starts from a fresh context, which is the cheapest possible shape, and the in-game checks end the chain cleanly. The cost is a script and the loss of the VS Code view while it runs.
- **Option C, lead and workers in one session.** The interactive session becomes the lead: it runs the frontier, spawns one worker subagent per ticket in a worktree, the worker runs the implement-review-fix cycle and spawns its own reviewers (depth three allows it), and returns a report. Worker contexts are discarded, so the lead's context grows by reports only; a worker cannot ask the owner, which forces decide-and-flag; the lead asks the batched questions at the end of each ticket. This works today without scripts and keeps the owner's session as the place where questions arrive.
- **Not recommended now:** agent teams (experimental, no split panes in VS Code or Windows Terminal), cloud routines (the build is Windows-only and the in-game check is local), the Workflow tool as the outer loop (no mid-run input, and sign-off between stages means one workflow per stage anyway).

Recommendation: C for interactive days, B for unattended runs, and A under both as the safety net. The three share the checkpoint file and the decide-and-flag policy.

### 3.7 Parallel top-level sessions

With `claude --worktree`, two or three interactive sessions can each take a ticket. The coordination points are the tracker (a claim is the assignee plus a pushed branch; the frontier excludes claimed tasks), `main` (rebase before opening the PR, rerun the gate after the rebase, squash-merge one at a time), and the singletons: the live ZZMI install and the game, which only one session may touch at a time, and the Bazel output base, which is separate per worktree and costs a cold build each. Cross-session messaging exists on native Windows and could carry "I hold the live install" notices, but the tracker is enough. The PRD's construction order limits the gain for phaethon today: of the open tasks, #20 and #47 touch the change record, #21 and #22 touch composition, #28 touches deploy, and #38, #42 and #43 are independent, so two sessions on disjoint areas is the realistic ceiling until the compose stage opens. A monorepo with front-end and back-end epics would gain more.

### 3.8 Model and effort

The implementation on Opus 5.5 at medium effort was fast and the reviewers rarely found the kind of defect a stronger implementer would have avoided; the defects were design gaps and lifecycle cases that a reader of the diff finds. The lever is context size, not model. For reviewers, the finders should stay on Opus; the orchestrator on Fable followed the full process and found the only HIGH in the experiment at about 2.5 times the cost of the Opus orchestrator, which argues for Fable on the last round before a merge and Opus on the first. Whether a Sonnet implementer with Opus reviewers is cheaper per merged PR is untested and is a cheap experiment: one ticket, two worktrees, same prompt.

## 4. Open questions

Tickets already filed from this document: epic #31 (the loop skill, needs a spec), tasks #32 (delta re-review and round budget), #33 (verifier and knowledge-base steps) and #34 (negation and term-layer rules), idea #35 (parallel sessions), and a comment with the evidence on bug #24 (Windows interpreter). The questions below decide the rest.

Each question carries a recommendation; "yes" accepts it.

**Q1, scope of the loop skill.** Should the implementation loop become a skill in this repository (pick, branch, implement, context-free review, delta re-review, merge, tracker update, pause rules, checkpoint file, decide-and-flag), with phaethon's `agents/implementation-loop.md` reduced to repository-specific facts? Recommendation: yes, as an epic that needs a spec, with this document as its input and the proposals in 3.2, 3.5 and 3.6 as its scope.

**Q2, decide-and-flag.** Do you accept that the agent proceeds on its recommendation for reversible decisions and records them, asking only for irreversible changes, product trade-offs it cannot rank, external services and in-game checks? Recommendation: yes; the evidence is 19 of 21 answers.

**Q3, the context reset.** Which of A (compaction plus checkpoint), B (headless chain, one PR per session) and C (lead and worker subagents) do you want first? Recommendation: C first, because it needs no script and keeps your session as the question channel, with A as the safety net; B when you want unattended overnight runs.

**Q4, review round budget.** Two rounds per PR, a third only for a HIGH that a fix introduced, and fixes that add mechanism become tickets? Recommendation: yes.

**Q5, delta re-review.** Should the second round receive the first report and the disposition comment, at the cost of some independence? Recommendation: yes; the first round stays context-free and the regressions the second round exists to catch are in the delta.

**Q6, verifiers and the knowledge base.** Should the loop create `.claude/knowledge/` once per repository and the skill dispatch the verifier batch as written, or should the skill drop both steps? Recommendation: create the directory from the loop, keep verifiers on Sonnet, and measure for ten rounds.

**Q7, orchestrator tier.** Opus for the first review round and Fable for the round before merge? Recommendation: yes, measured over the next ten PRs.

**Q8, prose enforcement.** A hook that runs the prose scanner on PR bodies, PR comments, question text and `docs/` files, with no rewriting pass on transient text? Recommendation: yes.

**Q9, the negation and term-layer rules.** Add both to the tech-writing corpus with golden pairs and a scan? Recommendation: yes.

**Q10, GUI vocabulary.** Keep "Library" and "Characters" as the two tabs, or rename to the user's words ("Mods" and "Characters")? Should "package" become "mod" in every visible string, with the internal term kept in code and docs? Recommendation: rename in the UI, keep the internal terms, and add the user-facing column to the glossary.

**Q11, parallel sessions.** Do you want the tracker claim rule and the live-install lock written into the loop now, or wait until the compose stage opens two independent fronts? Recommendation: write the rules now, run one parallel session when #21 starts.

**Q12, the implementer model experiment.** Run one ticket twice, Sonnet 5.5 and Opus 5.5 as implementer with the same reviewers, and compare rounds and cost? Recommendation: yes, on #43 (YAML config), which is small and independent.

**Q13, phaethon tickets.** Should I file the phaethon-specific items (clippy thresholds and rustfmt path in `agents/build.md`, the heredoc rule in CLAUDE.md, the pause checklist, the merge-candidate rule for in-game checks, the stale-item check for continuation prompts) as tasks under epic #1, or as one housekeeping task? Recommendation: one task for the build reference and one for the loop file.

**Q14, tracker area.** The loop skill fits none of this repository's areas; should `area/loop` be added, or does the loop live under `area/pm`? Recommendation: `area/loop`, since the skill cluster is new.

## 5. Method

The six transcripts (about 35 MB of JSONL) were condensed with [condense_transcripts.py](implementation-loop-retrospective/condense_transcripts.py), which keeps user turns, assistant text, one line per tool call with a truncated result, questions and agent prompts in full, and reviewer hand-backs in full, and writes per-session statistics (usage deduplicated by API message id, peak context, idle gaps). Six analysis agents each read one condensed session end to end with the same brief and wrote the reports under [sessions/](implementation-loop-retrospective/sessions/); their claims were spot-checked against the questions, the user turns and the PR comments, which were read first-hand. A guide agent fetched the harness documentation for section 3.6. Three reviewer agents re-ran `/deep-code-review` on the merged head of PR 49 in a worktree, one per orchestrator tier, at medium effort. Costs use the price table of 2026-10-06. The analysis agents' reports are kept verbatim as evidence and are not in the house voice.
