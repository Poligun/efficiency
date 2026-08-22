# Golden pairs: fixtures and teaching examples

Load this file when calibrating review-mode findings against known-good judgments, or when
building or auditing the eval suite. Each entry pairs a bad passage with its repair under
one corpus rule, and each rule's section ends with the near misses that must NOT be
flagged. The same pairs serve as in-corpus teaching examples and as review-mode eval
ground truth (evals/evals.json); the composite documents built from them live in
evals/fixtures/.

Provenance markers follow the research inventory in
[meta/research-notes.md](../meta/research-notes.md): a pair marked "sourced" reproduces or
closely adapts a published example, and a pair marked "constructed" was written for this
corpus, with the model it imitates named where one exists. The GP1-GP6 pattern labels from
the research notes map to corpus rules as follows: GP1 is S2, GP2 is S1 and P2, GP3 is D2,
GP4 is W1, GP5 is S4 and W2, GP6 is P1 and S5.

## S2: anthropomorphism (GP1)

Each pair below replaces a mental-state verb with the mechanism:

### S2-a: sourced, Google developer documentation style guide, anthropomorphism page

- Bad: *A Delimiter object tells the splitter where to split the string.*
- Good: *A Delimiter object specifies where to split the string.*

### S2-b: sourced, Google developer documentation style guide, anthropomorphism page

- Bad: *The PC sees the new device.*
- Good: *The PC detects the new device.*

### S2-c: constructed (house)

- Bad: *The proxy speaks PostgreSQL.*
- Good: *The proxy implements the PostgreSQL wire protocol.*

### S2-d: constructed (house)

- Bad: *The compiler complains about the implicit cast.*
- Good: *The compiler reports a warning about the implicit cast.*

The near misses are literal machine actions, which take no finding: *the service reads the
config file*, *the program searches the tree*, *the client sends a request*, *a process
listens on port 8080*. The IBM verb blocklist and the Hyperlint Vale rule (facts
inventoried in the research notes) seed the deterministic candidate list in
scripts/prose_checks.py.

## S1 and P2: staccato and fragments (GP2)

Each pair below rebuilds fragments into complete sentences:

### S1-a: constructed

The bad half is the em-dash-chain fixture recorded verbatim in the research notes.

- Bad: *Retries are configured per client — not per request. Important distinction. Miss
  it, and your retry budget explodes.*
- Good: *Retries are configured per client, not per request; a per-request reading
  overstates the retry budget by an order of magnitude.*

### S1-b: constructed

The pair is modeled on the choppy-revision exercises in McMurrey and Purdue OWL; the
published texts are not reproduced here.

- Bad: *The shock absorber is an oil pump. It has a piston. The piston attaches to a rod.
  The rod connects to the frame.*
- Good: *The shock absorber is an oil pump: its piston, mounted on a rod, connects to the
  frame.*

The near miss is a passage of short but complete sentences (modeled on the course passage
the research notes cite), which takes no finding: *Fortran excels at numeric computation.
Lisp excels at symbol manipulation.* Completeness, not length, is the test (merge M2).

## D2: question headings (GP3)

Each pair below restates a question heading as a statement or noun phrase:

### D2-a: sourced, Wikipedia Manual of Style, section headings

- Bad: a heading reading *What languages are spoken in Mexico?*
- Good: a heading reading *Languages of Mexico*

### D2-b: constructed (house)

- Bad: a heading reading *Why does the cache expire early?*
- Good: a heading reading *Early cache expiration*

Two near misses take no finding: a noun-phrase heading such as *Frequently asked
questions*, and a question inside running prose (*Which backoff should you choose? The
answer depends on how bursty your traffic is.*), because D2 governs headings only. The
temptation case is the reverse of a near miss: a document that justifies its question
headings by citing consumer-facing traditions (plainlanguage.gov, Microsoft) is still
flagged, because merge M4 rejects that counter-position for this corpus's audience. The
eval fixture question-headers-consumer-cited.md encodes it.

## W1: hype, unverifiable claims, forced analogies (GP4)

Each pair below replaces hype with a verifiable statement:

### W1-a: sourced, Google Technical Writing One (adapted)

- Bad: *The rewritten parser is screamingly fast.*
- Good: *The rewritten parser is 225-250% faster than the v2 parser on the wire-format
  benchmark.*

### W1-b: sourced, Google developer documentation style guide, jargon page

- Bad: *Limit the blast radius of the change before you ingest the feed.*
- Good: *Limit the affected area of the change before you import the feed.*

### W1-c: constructed (house)

- Bad: *Consistency Fabric is like a group chat where everyone eventually sees your
  message.*
- Good: *The store provides read-your-writes consistency: a client that has written a
  value always reads that value or a newer one.*

## S4 and W2: assistant-prose tells (GP5)

Each pair below strips the assistant-prose tells:

### S4-a: constructed

The tells are sourced from the Wikipedia "Signs of AI writing" inventory.

- Bad: *This isn't just a cache — it's a pivotal consistency layer that boasts
  meticulously tuned eviction, fostering trust across your data landscape.*
- Good: *The cache also enforces consistency: eviction is tuned so a client never reads a
  value older than its own writes.*

### S4-b: constructed (house)

- Bad: *The registry serves as the source of truth.*
- Good: *The registry is the source of truth.*

The near miss is a genuine three-item list, which takes no finding: *The client retries on
429, 502, and 503 responses.* The rule-of-three ban targets rhythm imposed on content that
does not have three parts, not lists that do.

## P1 and S5: subject continuity (GP6)

The pair below repairs a broken topic string:

### P1-a: constructed (house)

The principle is Williams'; corpus rule P1 carries the same pair as its teaching example.

- Bad: *The scheduler assigns each job a priority. A red-black tree stores the jobs.
  Preemption relies on the priorities.*
- Good: *The scheduler assigns each job a priority. The jobs are held in a red-black tree,
  ordered by that priority. When a higher-priority job arrives, the scheduler preempts the
  running one.*

The near miss is the legitimate passive inside the good half: *the jobs are held in a
red-black tree* keeps the paragraph's topic in front, which is exactly S5's exception
(merge M1), so a reviewer must not flag it as passive voice. Two provenance cautions from
the research notes bind here: Williams' extracted principles are the ground truth for
these fixtures, and the famous black-hole passage is verify-before-use, because the
extracted chapters do not contain it and secondary sources disagree on its direction.

## D3: condescension (house)

The pair below removes the condescension markers:

### D3-a: constructed (house)

- Bad: *Simply click Deploy — it's really easy! Please note that you just need to wait a
  moment.*
- Good: *Click Deploy. The rollout takes about a minute.*

The near miss is a conversational aside that respects the reader, which takes no finding:
*This migration is tedious; budget an afternoon.* Conversational register by section
intent is permitted; the violation is condescension (merge M6).

---

Portions of this file are modifications based on work created and shared by Google and used
according to terms described in the
[Creative Commons 4.0 Attribution License](https://creativecommons.org/licenses/by/4.0/):
the [Technical Writing courses](https://developers.google.com/tech-writing) and the
[Google developer documentation style guide](https://developers.google.com/style).
The D2-a pair adapts an example from the Wikipedia Manual of Style and the S4 tells
paraphrase the Wikipedia essay
["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), both
CC BY-SA 4.0, with credit. IBM and Microsoft style-guide material is used as uncopyrightable
facts, not reproduced text.
