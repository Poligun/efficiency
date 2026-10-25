# Evidence tables

The numbers behind [the retrospective](../implementation-loop-retrospective.md). Times are UTC. Sessions are named by the first eight characters of their transcript id under `~/.claude/projects/c--Github-phaethon/`.

## Sessions

| Session | First turn | Last turn | Span | Idle gaps over 10 min | API calls | Peak context | Output tokens (thinking) | Cache-read tokens | Reviewer agents (nested included) | Estimated cost, main + agents |
|---|---|---|---|---|---|---|---|---|---|---|
| 64117bac | 10-24 01:42 | 10-24 02:56 | 1.2 h | 11 min | 148 | 358,752 | 150,698 (36,277) | 33.6M | 13 | $11.4 + $7.6 |
| c01a72e3 | 10-24 02:58 | 10-24 06:10 | 3.2 h | 11, 29, 20, 16 min | 182 | 535,682 | 277,677 (74,029) | 54.7M | 20 | $19.0 + $21.0 |
| 101ca9b8 | 10-24 07:06 | 10-24 18:00 | 10.9 h | 12, 527 min | 278 | 608,658 | 336,777 (91,735) | 99.4M | 23 | $32.3 + $15.4 |
| 69c7d0fb | 10-24 17:56 | 10-25 02:27 | 8.5 h | 13, 175, 59, 61, 62, 11 min | 287 | 625,497 | 338,517 (72,312) | 102.0M | 17 | $37.9 + $18.1 |
| aadd6222 | 10-25 02:35 | 10-25 03:37 | 1.0 h | 17 min | 164 | 344,062 | 136,271 (29,113) | 36.1M | 8 | $11.5 + $3.6 |
| 0e5c87c2 | 10-25 05:29 | 10-25 18:24 | 12.9 h | 33, 686 min | 119 | 392,724 | 144,555 (51,491) | 32.5M | 9 | $12.6 + $10.6 |

Totals: 1,178 main-thread API calls, 1.38M main-thread output tokens, 358M main-thread cache-read tokens, 1.16M reviewer output tokens, 79M reviewer cache-read tokens, about $201. Every session ran on claude-opus-5-5 at medium effort; two haiku convention scouts were the only other model use. No compaction occurred in any session.

Cost formula: input at $4, cache write at $5, cache read at $0.20, output at $20 per million tokens for Opus 5.5; Haiku 5.5 at $0.10, $0.125, $0.01, $0.50. The one session that recorded its own cost, 64117bac at $20.00, matches the estimate within a dollar.

## PRs

| PR | Issue | Opened | Merged | Lines added | Implementation (previous merge to open) | Open to merge | Review rounds | Findings (all rounds) |
|---|---|---|---|---|---|---|---|---|
| 23 | #5 build spike | 10-24 01:53 | 01:59 | 4,234 | 12 min | 6 min | 1 | 6 |
| 24 | #6 fixtures | 02:04 | 02:19 | 760 | 5 min | 15 min | 2 | 11 |
| 25 | #7 INI parser | 02:24 | 02:36 | 802 | 4 min | 12 min | 2 | 14 |
| 26 | Bazel 9.3.1 pin | 02:51 | 02:54 | 51 | 16 min | 3 min | 1 | 9 |
| 27 | #1 license, overlay | 02:53 | 02:56 | 55 | parallel with 26 | 3 min | 1 | 8 |
| 29 | #8 toggle model | 03:12 | 04:26 | 2,487 | 16 min | 74 min | 3 | 24 |
| 30 | #9 library import | 04:38 | 06:09 | 2,961 | 12 min | 91 min | 6 | 51 |
| 31 | #10 attribution | 07:26 | 07:37 | 2,106 | 77 min (includes a question wait) | 11 min | 2 | 13 |
| 32 | #11 inspection | 07:55 | 08:23 | 2,210 | 18 min | 28 min | 3 | 23 |
| 33 | #12 adoption | 08:31 | 08:47 | 729 | 7 min | 16 min | 3 | 15 |
| 34 | #13 Library page | 08:51 | 09:02 | 680 | 4 min | 11 min | 2 | 12 |
| 36 | #35 merge offers | 09:04 | 09:08 | 314 | 2 min | 4 min | 1 | 4 |
| 37 | #14 deploy | 18:16 | 18:54 | 1,733 | 548 min (owner absent, then two questions) | 37 min | 2 | 12 |
| 40 | #15 profiles, state | 19:11 | 23:45 | 2,395 | 18 min | 274 min (a 175-minute question wait, then the in-game check) | 3 | 30 |
| 44 | #16 GUI pages | 23:57 | 10-25 02:15 | 1,665 | 11 min | 139 min (two looks by the owner) | 1 | 8 |
| 46 | #17 change record | 02:49 | 03:01 | 1,259 | 34 min (includes a question wait) | 12 min | 3 | 17 |
| 48 | #18 rebind | 03:27 | 03:36 | 1,187 | 25 min (includes a question wait) | 9 min | 2 | 10 |
| 49 | #19 gating | 06:18 | 18:23 | 1,798 | 163 min (a 33-minute question wait) | 724 min (an 11-hour question wait) | 3 | 14 |

Totals: 38 review rounds, about 290 findings. Review rounds ran between 1 min 13 s and 12 min 34 s; the median is near 5 minutes. The per-session analyses under [sessions/](sessions/) give the findings per round with a judgment on each.

## Questions put to the owner

| Session | Time | Header | Answer |
|---|---|---|---|
| 64117bac | 02:50 | License | recommended |
| c01a72e3 | 03:26 | Label key | recommended, reversed 49 minutes later after a vocabulary clarification, then confirmed |
| c01a72e3 | 04:28 | 7-Zip | "I just installed it" |
| c01a72e3 | 05:01 | Ambiguity | recommended |
| c01a72e3 | 05:31 | Name weight | recommended (reverses the Ambiguity answer's consequence) |
| 101ca9b8 | 07:11 | Roster | recommended |
| 101ca9b8 | 07:11 | Registry fix | recommended |
| 101ca9b8 | 07:37 | Cross-pkg | recommended |
| 69c7d0fb | 17:57 | Deploy slug | recommended |
| 69c7d0fb | 17:57 | Nested root | recommended (the example in the question was wrong) |
| 69c7d0fb | 19:00 | Toggle home | recommended |
| 69c7d0fb | 19:00 | No outfit | recommended |
| 69c7d0fb | 19:00 | Slot clashes | recommended |
| 69c7d0fb | 19:35 | Shared-only | recommended, with a product note on add-on mods; 175-minute wait |
| aadd6222 | 02:36 | Order | recommended |
| aadd6222 | 02:36 | Diff | recommended |
| aadd6222 | 02:36 | Scope | recommended |
| aadd6222 | 02:36 | Dematerial. | recommended |
| aadd6222 | 03:02 | Clash scope | recommended |
| aadd6222 | 03:02 | On clash | recommended |
| aadd6222 | 03:02 | Target | recommended |
| aadd6222 | 03:02 | Deployed | recommended |
| 0e5c87c2 | 05:32 | #18 check | "Passed" |
| 0e5c87c2 | 05:32 | Promotion | recommended |
| 0e5c87c2 | 05:32 | Gate scope | recommended |
| 0e5c87c2 | 05:32 | Test input | recommended |
| 0e5c87c2 | 06:28 | Regate | recommended; 686-minute wait |

The full question texts are in each session's analysis under section 3.

## Owner turns that were not answers to a question

- 69c7d0fb 18:26: "why are you giving me a continuation prompt when there's still plenty of context left"
- 69c7d0fb 18:27 and 18:29: requests for more detailed in-game check instructions ("where is phaeton, is it built or installed or added to path?", "what does the setup do and what file format should it be")
- 69c7d0fb 23:45: two product questions after the check (F10 after a phaethon-set value; integer values hard to remember)
- 69c7d0fb 01:06: six GUI defects from one look, including "Package tab: what happens if I directly go to this tab? why is it on the same level as library tab"
- c01a72e3 04:23: the "key" term collision and a reversed decision
- c01a72e3 04:27: "cache is still warm and looks like context window is still fine"
- 101ca9b8 17:56: "what is fixture-licensing question"
- 64117bac 02:47: bazelisk upgraded; licensing and overlay decisions

## Prose scan

The tech-writing scanner over the six sessions' assistant text (160K characters, status reports and summaries only, reviewer hand-backs excluded):

| Rule | Candidates | Most frequent |
|---|---|---|
| S2 anthropomorphic verb | 104 | say/says (31, many about documents, which the rule allows), refused/refuses (13), want/wants/wanted (12), expect/expected/expecting (12), see/sees (6), decided/decide/decides (7), ask/asking (5), know/knows (3) |
| W2 AI vocabulary | 1 | underscores |

Negation forms in the same text: "does not" 2, "do not" 1, "never" 30, "verb no thing" 15 by regex ("needs no action", "writes no values", "changes no files", "sends no keystrokes", "holds no stray changes", "gives no single root").

Term frequencies in the same text: gate 122, record 110, version 91, family 75, profile 63, key 61, adopt 59, package 51, slot 25, clash 23, entry 22, gating 9, gated 8, working tree 8, promote 5, seam 1.

## PR 49 review comparison

| Run | When | Orchestrator | Nested agents | Wall clock | Output tokens | Cache-read tokens | Estimated cost | Result |
|---|---|---|---|---|---|---|---|---|
| Original round 1 | 10-25 06:18 | Opus 5.5 medium | A3 opus, A2 opus, A4 haiku; no verifiers | 9 min 44 s | about 146K | 7.7M | about $5 | 1 HIGH (gate never redone when slots change), 3 MEDIUM, 4 LOW |
| Original round 2 | 18:01 | Opus 5.5 medium | A3 opus only; no verifiers | 9 min 39 s | about 98K | 6.9M | about $4 | 1 MEDIUM (namespace peers double-decrement the counter), 2 LOW |
| Original round 3 | 18:13 | Opus 5.5 medium | A3 opus, A2 opus; no verifiers | 7 min 32 s | about 88K | 5.3M | about $3 | 1 HIGH (namespace peer re-gated on every redeploy, introduced by the round-2 fix), 1 MEDIUM, 1 LOW |
| Experiment | 10-25 12:43 | Opus 5.5 medium | A2 opus, A3 opus, A4 haiku; no verifiers | 7 min | 56K | 3.7M | $3.0 | 1 MEDIUM (duplicate detection section when the body override sits in a peer INI), 2 LOW |
| Experiment | 12:43 | Sonnet 5.5 medium | A2 opus, A3 opus, A4 haiku; no verifiers, no measured ledger | 12 min | 79K | 4.5M | $4.0 | 2 MEDIUM (one latent on a registry change; the persisted `Vec<Slot>` type) |
| Experiment | 12:43 | Fable 5.1 medium | A2 opus, A3 opus, A4 haiku, three sonnet verifiers | 16 min | 104K | 6.3M | $7.9 | 1 HIGH (stale gate under a later recorded edit can never be dropped), 1 MEDIUM (same as the Opus experiment's), 2 LOW |

The experiments ran on the merged head of PR 49 (commit 7d97e49), after all three original rounds' fixes, in a detached worktree with `origin/main` as trunk. The six reports are under [pr49-reviews/](pr49-reviews/).
