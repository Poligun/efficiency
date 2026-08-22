# Voice: register and house tone rules

Load this file when setting or checking a document's register: its tone, person, tense, and
how the prose treats the reader and the software. This file is the primary tone layer of the
corpus; [clarity.md](clarity.md) and [structure.md](structure.md) supply the sentence-level
and structural layers; the corpus design is ratified by
[ADR 2](../../../docs/decisions/0002-technical-writing-skill.md).

Rule IDs are unique across the corpus and are never renumbered or reused; a new rule takes
the next free number in its family, whichever file it lands in. The family letter names the
level a rule governs
(`D` document, `P` paragraph or block, `S` sentence, `W` word). Source tags map each rule to
its provenance: `[TW1/...]` and `[TW2/...]` are Google Technical Writing course units,
`[devstyle/...]` is the Google developer documentation style guide, `[Williams]` is Joseph M.
Williams, *Style: Toward Clarity and Grace* (1995), and `[house]` is house-original. A
`Check:` line marks whether a rule is decidable mechanically or requires editorial judgment.

## Authoring-time merges

Every tension between sources was resolved once, at authoring time, into the single rules
below. The seven merges are binding: review mode cites the merged rule, and no runtime
precedence reasoning between sources is permitted.

- **M1: voice vs. cohesion.** Google's active-voice rule yields to Williams' topic strings:
  prefer active voice unless the passive preserves the paragraph's topic string. Resolved in
  S5 (clarity.md) and P1.
- **M2: short sentences vs. fragments.** Google's short-sentence advice is adopted as
  compression inside complete sentences, never as fragments; the global-audience
  short-sentence emphasis is dropped except for the idiom ban. Resolved in S1 and in W6
  (clarity.md).
- **M3: em-dash digressions vs. staccato.** Google's dash style is adopted only within
  S12's mechanics, and dashes never substitute for connectives. Resolved in S12
  (clarity.md), with the register side in S1 and S4.
- **M4: question headings.** Question headings are banned. Consumer-oriented traditions
  (plainlanguage.gov,
  Microsoft) endorse question headings for citizen and consumer audiences; this corpus writes
  for professional audiences and rejects that counter-position. Resolved in D2.
- **M5: jargon.** Google's "write around jargon" default is dropped. For expert readers the
  term of art is the clear choice: define once, use consistently. Resolved in W5 and W4
  (clarity.md).
- **M6: conversational vs. condescending.** The style guide's "knowledgeable friend"
  framing is dropped; its operational avoidance list is adopted. Conversational register is
  permitted where a section's intent calls for it; condescension never is. Resolved in D3.
- **M7: contractions.** The general pro-contraction stance is dropped. Contractions are
  permitted, not required; the one adopted preference is negation contractions as a clarity
  aid. Resolved in S15 (clarity.md).

## Document register

### D1: Write for experts reading at volume
Source: [house], [TW1/audience]. Check: judgment.

The reader is a professional who processes large amounts of text; every sentence competes
for working memory. The document's job is education, not marketing: transfer facts and
reasoning, and cut anything whose only function is enthusiasm. Do not re-explain what the
audience demonstrably knows; state assumptions once (D4 in structure.md) and proceed at the
audience's level.

### D2: Do not phrase headings as questions
Source: [house]; merge M4. Check: mechanical.

Write headings as statements or noun phrases. A question heading makes the reader parse a
rhetorical device before learning what the section covers, and it reads as advertising
copy.

- *Why does the cache expire early?* → *Early cache expiration*
- *What can I deploy with this?* → *Supported deployment targets*

Wikipedia's Manual of Style states the same ban. Consumer-facing style guides endorse
question headings for lay audiences; that context does not apply here (M4).

### D3: Conversational register is permitted; condescension is not
Source: [house], [devstyle/tone]; merge M6. Check: judgment.

Conversational phrasing is legitimate, and for some paragraphs or sections ideal, when the
section's intent calls for it: an aside in a tutorial, a migration note that acknowledges a
painful step. The violation is condescension: phrasing that treats the reader as unable to
comprehend longer or more formal phrasing. Apply the condescension test: does the passage
talk down, simplify vocabulary the audience demonstrably has, or over-explain what an expert
already knows?

The following markers are banned:

- "simple", "easy", "quick", "just", "simply" as difficulty judgments (the reader decides
  what is easy)
- placeholder courtesy: "please note", "at this time", "please" outside a genuine request
- exclamation points
- pop-culture references and slang
- over-explaining: restating a concept the stated audience (D4 in structure.md) already
  holds

## Paragraph register

### P1: Begin sentences with known information; end with new
Source: [Williams], [house]; merge M1. Check: judgment.

Open each sentence with information the reader already holds (Williams' topic position)
and place new or unfamiliar information at its end (the stress position). Paragraph
cohesion comes from topic strings: successive sentences open with the same small cast of
characters. When a sentence's grammatical subject would break the string, restructure it; the passive
voice is legitimate exactly when it keeps the established topic in front (S5 in
clarity.md). Deleting "there is / there are" (S6 in clarity.md) is also a known-first
repair, because it promotes the real topic to the opening.

The first passage below hops topics; the second repairs it:

- *The scheduler assigns each job a priority. A red-black tree stores the jobs. Preemption
  relies on the priorities.*
- *The scheduler assigns each job a priority. The jobs are held in a red-black tree, ordered
  by that priority. When a higher-priority job arrives, the scheduler preempts the running
  one.*

Williams' caution stands: no mechanical rule decides what to topicalize. Choose a point of
view, decide what the reader currently holds as old information, and design sentences to
meet both.

### P2: Do not spray one-sentence paragraphs
Source: [house]. Check: mechanical (detection) plus judgment (the verdict).

A paragraph is a unit of argument, not a beat in a monologue. A run of single-sentence
paragraphs, or of bolded one-line pronouncements, is the block-level form of the staccato
register banned at sentence level by S1. One single-sentence paragraph as a deliberate
transition or emphasis is fine; a rhythm of them is the violation. The positive rules for
paragraph construction are P3-P6 in structure.md.

## Sentence register

### S1: Write complete sentences; short is fine, fragments are not
Source: [house]; merge M2. Check: mechanical.

Every sentence carries a subject and a finite verb. Shortness comes from cutting words
inside complete sentences (S6, S7, S10 in clarity.md), never from amputating grammar.
These shapes are banned:

- verbless fragments deployed for punch: *Important distinction.*
- clipped rhetorical chains: *Miss it, and the retries pile up. Badly.*
- em-dash splices standing in for connectives (S12 in clarity.md)

Do not flag short sentences that are complete: a passage of brief, fully formed sentences is
good technical writing, and Google's own model passages have this shape. Completeness, not
length, is the test.

### S2: Attribute behavior to the mechanism, not to a mind
Source: [devstyle/anthropomorphism], [house]. Check: mechanical (verb list) plus judgment.

Software does not think, want, know, complain, or speak. A sentence that claims it does
costs precision twice: the reader must translate the metaphor back into a mechanism, and
the metaphor translates poorly across languages. Name what the component actually does:

| Anthropomorphic | Mechanism |
|---|---|
| the parser thinks, believes, assumes | determines, detects, defaults to |
| the service remembers | stores, caches |
| the client sees | receives, detects, reads |
| the compiler complains | reports an error, emits a warning |
| the server refuses | rejects, fails to |
| the API wants, expects | requires |
| the proxy speaks PostgreSQL | implements the PostgreSQL wire protocol |
| the object tells the splitter where to split | specifies where to split |

Do not flag literal machine actions: *the service reads the config file*, *the program
searches the tree*, *the client sends a request*, *a process listens on a port*. The test:
does the verb name actual I/O or computation, or does it ascribe intent, perception, or
speech?

### S3: Address the reader as "you"; refer to software in the third person; use the present tense
Source: [devstyle/person], [devstyle/tense]. Check: mechanical.

Use the second person, or the imperative, for the reader. Refer to software by name or as
"it": the software is an object with behavior, not a companion, and third-person reference
reinforces S2. Describe behavior in the present tense; software that "will return an error"
returns it now for any reader running it now. Do not use the hypothetical "would": *the
request would fail* → *the request fails*. Reserve the future tense for genuinely future
events, such as a deprecation with a date.

### S4: Do not use assistant-prose constructions
Source: [house]. Check: mechanical (patterns are greppable) plus judgment on density.

Model-generated prose has recognizable syntactic tells. All of the following are banned:

- negative parallelism: *It's not just a cache, it's a consistency layer.*
- copula avoidance: *serves as*, *stands as*, *acts as* where the meaning is *is*
- vague attribution: *industry experts agree*, *many developers find*
- rule-of-three compulsion: triads of adjectives or clauses imposed as rhythm (*fast,
  scalable, and reliable*) on content that does not have three parts; a list of three
  genuine items is fine
- formatting as emphasis: scattered boldface, emoji, em-dash rhetoric (S12 in clarity.md),
  one-line paragraph spam (P2)

## Word register

### W1: Coin no hype terms, make no unverifiable claims, force no analogies
Source: [house], [devstyle/excessive-claims]. Check: judgment.

One principle, that the reader is never made to hold an object doing no explanatory work,
yields three bans:

- No coined marketing terms for ordinary mechanisms. *Consistency Fabric* forces the reader
  to allocate a new concept for known machinery; use the standard term.
- No superlatives or performance claims that are not verifiable and durable. *Screamingly
  fast* → *225-250% faster than the v2 parser on the wire-format benchmark*. A claim that
  cannot carry a number or a citation is deleted, not softened.
- No decorative analogies. *Like a group chat for your database* adds a second object to
  track without removing any complexity. An analogy earns its place only when it replaces
  explanation.

### W2: Avoid the assistant vocabulary
Source: [house]. Check: mechanical (detection) plus judgment (the verdict).

These are the word-level tells of model-generated prose, with plain replacements where one
exists: delve (examine), tapestry, testament, underscores (shows), pivotal (central), landscape (as
a domain metaphor), intricate, foster, boasts (has), meticulously, crucial (important, or
nothing). Any single use can be innocent; treat a hit as a prompt to reconsider the
sentence, and treat density as the violation.

---

Portions of this file are modifications based on work created and shared by Google and used
according to terms described in the
[Creative Commons 4.0 Attribution License](https://creativecommons.org/licenses/by/4.0/):
the [Technical Writing courses](https://developers.google.com/tech-writing) and the
[Google developer documentation style guide](https://developers.google.com/style).
The assistant-prose inventories (S4, W2) paraphrase, with credit, the Wikipedia essay
["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
(CC BY-SA 4.0). Williams material is cited from *Style: Toward Clarity and Grace* (1995);
the rules restate his argument rather than reproducing his text.
