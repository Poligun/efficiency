# Clarity: sentence- and word-level rules

Load this file when drafting or tightening individual sentences and choosing terms: voice,
verbs, sentence scope, punctuation inside the sentence, and word choice. Register and tone
live in [voice.md](voice.md); document and block structure live in
[structure.md](structure.md).

Rule ID families, source-tag syntax, the ID allocation policy, and the binding
authoring-time merges (M1-M7) are defined in [voice.md](voice.md).

## Sentences

### S5: Prefer the active voice, unless the passive preserves the topic string
Source: [TW1/active-voice], [Williams]; merge M1. Check: mechanical (detection) plus
judgment (the exception).

Most sentences name the actor first: actor, verb, target. The active voice is shorter,
and it answers "who did this" before the reader asks. The one principled exception is
cohesion: when the passive keeps the paragraph's established topic in the subject position,
the passive is the better sentence (P1 in voice.md). This merge is resolved; do not weigh
the two sources per document. Separately, flag any passive that hides an actor the reader
needs: *the flag was enabled* leaves "by whom" unanswered.

### S6: Choose precise verbs; delete "there is" and "there are"
Source: [TW1/clear-sentences]. Check: mechanical.

Forms of *be*, *occur*, and *happen* as main verbs usually mark a buried action; recover
the verb the sentence is hiding. *There is / there are* openings bury both the actor and
the action: *There is a variable that controls the timeout* → *A variable controls the
timeout*. This repair also serves cohesion, because it moves the real topic into the
opening position (P1 in voice.md).

### S7: Give each sentence one idea
Source: [TW1/short-sentences]. Check: judgment (sentence length is the mechanical proxy).

A sentence carries one statement. When a draft sentence accumulates clauses, split it at
the clause seams into separate sentences, or into a list when the clauses are parallel
(S8). Sentence length is a proxy, not the rule: a long single-idea sentence can stand, and
a short sentence smuggling two claims cannot.

### S8: Convert embedded series into lists
Source: [TW1/short-sentences]. Check: mechanical.

A sentence that enumerates three or more parallel items reads better as a bulleted or
numbered list. The word *or* repeated through a sentence is the usual signal. List
construction rules are P7-P10 in structure.md.

### S9: Keep subordinate clauses in service of the main idea; distinguish "that" from "which"
Source: [TW1/short-sentences]. Check: judgment (clause scope), mechanical (that/which).

A subordinate clause may amplify the sentence's one idea; a subordinate clause that
introduces a second idea marks a sentence to split (S7). Use *that* for restrictive
clauses, with no comma: the clause narrows which thing is meant. Use *which* for
nonrestrictive asides, after a comma; read aloud, and if a pause precedes the clause,
*which* is the word.

### S10: Replace bloated phrases with their short forms
Source: [TW1/short-sentences], [devstyle/word-list]. Check: mechanical.

The table pairs each bloated phrase with its replacement:

| Bloated | Short |
|---|---|
| at this point in time | now |
| is able to, has the ability to | can |
| in order to | to |
| due to the fact that | because |
| despite the fact that | although |
| in the event that | if |
| a sufficient number of | enough |

### S11: Do not splice independent clauses with a comma
Source: [TW1/punctuation], [house]. Check: mechanical.

Two independent clauses joined by a bare comma are a splice: use a period, a semicolon, or
a conjunction. Do not repair a splice by amputating one clause into a fragment; that trades
this violation for S1 (voice.md).

### S12: Use em dashes rarely, unspaced, and never as sentence glue
Source: [devstyle/dashes], [house]; merge M3. Check: mechanical.

An em dash pair may set off a true digression, and a single em dash may set off a genuine
reversal at a sentence's end; both are rare. The mechanics are these:

- Em dashes are unspaced: *the second phase—compaction—runs nightly*.
- Never chain clauses with dashes for rhythm; that shape is the staccato register (S1 and
  S4 in voice.md).
- Introduce a list item's description with a colon, not a dash: *timeout: how long the
  client waits*, not *timeout — how long the client waits*.
- The en dash is not used. Write number ranges with *to* or a hyphen.

### S13: State conditions before instructions
Source: [devstyle/instructions]. Check: mechanical.

The reader executes instructions in reading order, so a trailing condition arrives after
the action it governs. *Click Delete if you want to remove the file* → *To remove the
file, click Delete.* The same ordering applies to warnings: warn before the step, never
after it.

### S14: Give every pronoun an unambiguous, nearby referent
Source: [TW1/words]. Check: judgment.

Introduce the noun before the pronoun, and keep them close; when other nouns intervene,
repeat the noun instead. *It* and *they* are the usual offenders. A bare *this* or *that*
opening a sentence must be followed by a noun: *this timeout*, not *this*.

### S15: Keep negation visible; contractions are permitted, not required
Source: [devstyle/contractions], [house]; merge M7. Check: judgment.

The corpus takes no general stance on contractions; the friendliness rationale for them is
excluded (M7). One clarity-driven preference survives: in warnings and requirements,
prefer *don't* and *can't* over *do not* and *cannot*, because a skimming reader can drop a
lone *not* and invert the meaning, while a contraction binds the negation to the verb.
Replace double negatives with the positive form: *not incompatible* → *compatible*.

## Words

### W3: Define each new term once; use one term per concept everywhere
Source: [TW1/words]. Check: mechanical (consistency), judgment (what needs defining).

If a term already exists, link its established definition rather than writing a rival one.
If the document introduces a term, define it at first use. Then hold it fixed: do not
rotate synonyms for variety, and do not rename mid-document. When shortening a name,
announce the short form once: *Protocol Buffers (protobufs for short)*.

### W4: Spell out an acronym at first use only when the audience may lack it; then use the acronym consistently
Source: [TW1/words], [house]; merge M5. Check: mechanical.

First use pairs the full term with the acronym: *Transmission Control Protocol (TCP)*;
every later use is the acronym alone, never an alternation between the two. Two
recalibrations for expert readers: do not define acronyms the stated audience demonstrably
has (no *application programming interface (API)* for engineers), and do not introduce an
acronym for a term the document uses only a few times; spell it out each time instead.

### W5: Use the audience's jargon; define once; never write around it
Source: [devstyle/jargon], [house]; merge M5. Check: judgment.

For expert readers the term of art is the clear choice; a paraphrase is longer and vaguer
than the term it avoids. The obligations that come with jargon: define a term once if any
plausible reader lacks it, use it consistently (W3), and use the field's term, not a coined
one (W1 in voice.md). Google's "write around jargon" default is dropped by merge M5.

### W6: Use literal language; no idioms or figures of speech
Source: [TW1/audience], [devstyle/tone]. Check: mechanical.

Idioms exclude non-native readers and translate poorly, and figurative language blurs the
mechanism it stands in for (S2 and W1 in voice.md). *Out of the box* → *by default*;
*under the hood* → *internally*. This is the surviving piece of Google's global-audience
guidance; its short-sentence emphasis is dropped by merge M2.

### W7: Prefer the plain word
Source: [devstyle/word-list], [house]. Check: mechanical.

The table lists the adopted subset of Google's word list, plus its inclusive-language
substitutions:

| Avoid | Write |
|---|---|
| leverage, utilize | use |
| ingest | import |
| blast radius | affected area |
| etc. | name the rest, or "for example" |
| crazy, insane | complex, unexpected |
| sanity check | validation, coherence check |
| whitelist, blacklist | allowlist, blocklist |
| master/slave | primary/replica |

D3 in voice.md owns the condescension markers; treat them as word-level flags under that
rule rather than as entries here. The full ~500-entry word list is deliberately not adopted; the exclusion is recorded in
[meta/open-questions.md](../meta/open-questions.md).

---

Portions of this file are modifications based on work created and shared by Google and used
according to terms described in the
[Creative Commons 4.0 Attribution License](https://creativecommons.org/licenses/by/4.0/):
the [Technical Writing courses](https://developers.google.com/tech-writing) and the
[Google developer documentation style guide](https://developers.google.com/style).
