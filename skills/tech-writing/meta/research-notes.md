# Research notes — tech-writing (2026-08-21)

Research provenance for [ADR 2](../../../docs/decisions/0002-technical-writing-skill.md).
Three passes: Google TW courses extraction, Google dev-docs style guide assessment, golden-set
example hunt plus Williams chapter extraction.

## 1. Google Technical Writing One & Two — distillation input

~90 prescriptive rules extracted, tagged by level (WORD / SENTENCE / STRUCTURE / PROCESS) and
checkability (MECHANICAL / JUDGMENT). Course One official summary checklist captured verbatim.

Most-mechanizable core (candidate deterministic checks): passive-voice detection; "there is/
there are"; sentence length; paragraph sentence-count (3-5, cap ~7); bloated-phrase blocklist
("at this point in time"→"now", "is able to"→"can"); weak-verb flags (be/occur/happen); idiom
blocklist; acronym first-use protocol + consistency; list parallelism/capitalization/punctuation;
imperative-first numbered items; colon before lists; comma splice; which/that; stacked headings;
presence of scope/audience/prereq statements in intro.

Licensing: CC BY 4.0; adapted-content attribution sentence prescribed by Google site policies
("Portions of this page are modifications based on work created and shared by Google...") + link.

Tone: the courses say almost nothing — "education, not marketing", second person, read-aloud
test. House tone rules are the primary tone layer, not an overlay.

## 2. Google developer documentation style guide — adopt as narrow cherry-pick

Verdict: ~15-20 rules from 9 pages; the "conversational and friendly" conflict is ~2 sentences of
framing on one page; the tone page's operational content is restrictions the house voice shares.

Include: anthropomorphism page (whole — states the house rule nearly verbatim, with rationale:
figurative language costs precision and translatability); excessive-claims (superlative ban +
"verifiable and durable" test); tone-page avoidance list only (no "please"-spam, no placeholder
phrases like "please note"/"at this time", no "simple/easy/quick", no exclamation points, no pop
culture/slang, no figurative language); present tense + no hypothetical "would"; second person +
third person for software (supports anthropomorphism ban); conditions before instructions; em
dash mechanics (unspaced, sparing; colon-not-dash for item descriptions; en dash never); headings
(sentence case, no leading gerunds, simple punctuation; question headings not addressed — house
ban stands alone); jargon mechanics recalibrated for expert readers (define once, consistent
terms; drop "write around jargon" default); ~a dozen word-list generics (in order to→to, avoid
etc., leverage→use, crazy/insane→complex, inclusive-language substitutions); negation-contraction
rationale as clarity note (a lone "not" is easy to skim past).

Exclude: "knowledgeable friend / let your personality show" framing; general pro-contraction
stance; "write around jargon" default; global-audience short-sentence emphasis (staccato risk —
keep only no-idioms); word list wholesale (~500 entries, Google-product-heavy); product-name /
HTML / UI-element / formatting-minutiae families.

## 3. Golden-set source material (per banned pattern)

Pattern labels are GP1-GP6 (golden pattern); they are a separate namespace from the corpus
rule IDs, which use the D/P/S/W families defined in references/voice.md.

GP1 anthropomorphism — SOURCED pairs from Google style guide ("A Delimiter object tells the
splitter…"→"specifies where to split"; "The PC sees"→"detects"), IBM verb blocklist (ask, decide,
expect, say, see, think, want), Hyperlint Vale rule (lintable verb list: remembers→stores,
thinks→detects, refuses→fails to, assumes→uses). Constructed: "speaks PostgreSQL"→"implements
the PostgreSQL wire protocol"; "compiler complains"→"reports a warning".
NEAR-MISS COUNTER-FIXTURE (must NOT flag): appropriate machine actions — "the service reads the
config file", "the program searches".

GP2 staccato/fragments — SOURCED choppy-revision pairs (McMurrey shock-absorber pairs, Purdue OWL).
Constructed em-dash-chain fixture ("Retries are configured per client — not per request.
Important distinction. Miss it, and…"). COUNTER-FIXTURE: Google's own short-complete-sentence
example (Fortran/Lisp passage) — short ≠ staccato; completeness is the test.

GP3 question headers — SOURCED: Wikipedia MOS "Headings should not be phrased as questions"
("What languages are spoken in Mexico?"→"Languages"). Google prescribes the positive form
(bare-infinitive tasks, noun phrases) but never addresses questions. CAUTION: plainlanguage.gov
and Microsoft endorse question headings for citizen/consumer audiences — encode as house rule
for professional audiences. (Resolved with issue #7: the counter-positions became the
temptation fixture — question headings stay flagged even when a document cites them; the
near misses that must not be flagged are prose questions and noun-phrase headings.)

GP4 hype/forced analogies — SOURCED: Google jargon page (blast radius→affected area, ingest→
import), word list (leverage, just, simply, easy), TW-One "screamingly fast"→"225-250% faster".
Constructed: "Consistency Fabric is like a group chat…"→plain read-your-writes explanation.

GP5 ChatGPT house style — SOURCED tell inventory (Wikipedia "Signs of AI writing"): negative
parallelism ("not just X, it's Y"), AI vocabulary (delve, tapestry, testament, underscore,
pivotal, landscape, intricate, fostering, boasts, meticulously, crucial), copula avoidance
("serves as"/"stands as" for "is"), puffery, vague attribution, boldface/emoji/em-dash overuse,
rule-of-three compulsion. Bad-snippet seeds from ignorance.ai "Field Guide to AI Slop",
deadlanguagesociety rhetoric analysis, elliestoolbox. Constructed composite technical passage
(caching example) assembling the tells.

GP6 subject continuity (positive) — VERBATIM Williams (Style 1995, pp. 80-133, extracted from
OCR PDF): "Readers need familiar information at the beginnings of sentences"; "A cohesive
paragraph has consistent topic strings"; "we introduce new themes not anywhere in a sentence,
but rather as close to its end as we can manage" (stress position); summary figure: TOPIC =
old/familiar, STRESS = new/unfamiliar; "We cannot follow any mechanical rule about what to
topicalize… decide on a point of view, consider what readers take to be old and new, then design
sentences to meet both needs." Also SOURCED: Federalists pair (experiencemachines), there-is
removal as known-first repair (Google TW-One).
CAVEAT: the famous black-hole passage is NOT in the extracted chapters and secondary sources
disagree on its direction — do not use as ground truth without checking the book's cohesion
chapter. Its point (passive can legitimately serve topic continuity) is independently supported
by the extracted text.

Key merge insight: Williams gives the principled override — prefer active voice UNLESS passive
preserves the topic string. This resolves Google's active-voice rule against house point 6.

Lintable assets found: Hyperlint Vale anthropomorphism rule; Wikipedia AI-vocabulary list —
both convertible to deterministic eval checks alongside LLM judging.

## 4. Attribution obligations

One line per adapted source, "modifications based on" wording, links to
developers.google.com/tech-writing and developers.google.com/style. Wikipedia material (MOS,
Signs of AI writing) is CC BY-SA 4.0 — share-alike; quote sparingly or paraphrase with credit.
IBM/Microsoft style guides are proprietary books: use their rules as facts (uncopyrightable),
don't reproduce their text wholesale.
