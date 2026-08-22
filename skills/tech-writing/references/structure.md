# Structure: document, paragraph, list, and heading rules

Load this file when organizing a document or checking its skeleton: what the opening must
establish, how sections and headings are formed, how paragraphs are built, and when prose
becomes a list or a table. Register and tone live in [voice.md](voice.md); sentence
mechanics live in [clarity.md](clarity.md).

In this file, `D` rules govern the document and its headings, and `P` rules govern
paragraphs and block elements (lists, tables). ID families, source-tag syntax, the ID
allocation policy, and the binding authoring-time merges (M1-M7) are defined in
[voice.md](voice.md).

## Document

### D4: Open by stating scope, audience, and prerequisites
Source: [TW1/documents]. Check: mechanical (presence).

The opening section answers three questions: what the document covers (and, where readers
will otherwise assume too much, what it does not), who it is for, and what it assumes the
reader knows or has already read. These statements are load-bearing elsewhere in the
corpus: the audience statement is what D1, D3, and W4 measure "demonstrably knows" against.

### D5: Put the key points first
Source: [TW1/documents], [house]. Check: judgment.

State the conclusion, decision, or result in the opening; supporting reasoning follows for
readers who continue. Experts reading at volume (D1 in voice.md) decide within the first
paragraph whether the document concerns them, and burying the verdict forces every reader
to excavate it.

### D6: Outline large documents; introduce each section
Source: [TW2/large-docs]. Check: judgment.

Outline before drafting, and give each section one job; a section that makes two points is
two sections. Open each major section with a short passage stating what it covers and how
it follows from the previous one. Hold terminology fixed across sections (W3 in clarity.md
at document scale): a concept renamed halfway through reads as a second concept.

### D7: Write headings as sentence-case imperatives or noun phrases
Source: [devstyle/headings], [house]. Check: mechanical.

Use sentence case: *Configure the client*, not *Configure The Client*. Task-based sections
take an imperative heading (*Create an instance*); conceptual and reference sections take a
noun phrase (*Retry semantics*). Do not open a heading with a gerund: *Creating an
instance* → *Create an instance*. Keep heading punctuation minimal: no terminal periods,
no exclamation points, words rather than symbols. Question headings are banned by D2 in
voice.md (merge M4).

### D8: Never stack headings
Source: [TW2/large-docs]. Check: mechanical.

A heading followed immediately by a subheading, with no text between, hides a missing
decision about what the section says. Write at least a sentence of introduction (D6) or
remove one heading level.

## Paragraphs

### P3: Open each paragraph with its topic sentence
Source: [TW1/paragraphs]. Check: judgment.

The first sentence states what the paragraph claims or covers; readers skim by first
sentences, and a paragraph whose point arrives in the middle is invisible to them. The
sentences that follow support the opening (P4), and hang together by topic strings (P1 in
voice.md).

### P4: Give each paragraph one topic
Source: [TW1/paragraphs]. Check: judgment.

A paragraph is a self-contained unit of one argument. Sentences off the topic move to the
paragraph where they belong, or die; a "by the way" sentence has no paragraph.

### P5: Aim for three to five sentences; treat seven as the ceiling
Source: [TW1/paragraphs], [house]. Check: mechanical.

Paragraphs longer than about seven sentences become walls that readers skip. The floor
binds too: a run of one-sentence paragraphs is the staccato register banned by P2 in
voice.md, which owns the single-sentence-paragraph exception.

### P6: Make the paragraph answer what, why, and how
Source: [TW1/paragraphs]. Check: judgment.

A strong instructional paragraph tells the reader what it is claiming, why the claim
matters, and how to use the knowledge. Not every paragraph carries all three, but a
paragraph answering none of them is filler and should be cut.

## Lists

### P7: Make list items parallel
Source: [TW1/lists-tables]. Check: mechanical.

All items in one list share grammar, logical category, capitalization, and punctuation. If
one item opens with a verb, all do; if one is a full sentence, all are. A reader who hits a
non-parallel item re-reads the whole list to find the pattern they missed.

### P8: Number a list only when order matters; open numbered items with imperatives
Source: [TW1/lists-tables]. Check: mechanical.

A bulleted list is an unordered set: if reordering the items would change the meaning, the
list must be numbered. Each numbered step opens with an imperative verb (*Open the
configuration file*, not *The configuration file is opened*) and performs one action, with
any condition stated first (S13 in clarity.md).

### P9: Introduce every list and table with a sentence ending in a colon
Source: [TW1/lists-tables], [TW1/punctuation]. Check: mechanical.

The introductory sentence says what the list enumerates or what the table shows, and it
ends with a colon. A list that interrupts prose without introduction forces the reader to
infer its purpose from the items.

### P10: Punctuate list items consistently by their grammar
Source: [TW1/lists-tables], [house]. Check: mechanical.

Choose sentence items or phrase items per list, not a mix (P7). Sentence items are
capitalized and take terminal periods; phrase items take no terminal punctuation. The
fragment ban (S1 in voice.md) governs running prose only: a noun-phrase list item is
well-formed structure, not a fragment, and review mode must not flag it.

## Tables

### P11: Use a table when readers will compare parallel facts; keep cells short
Source: [TW1/lists-tables], [house]. Check: judgment.

A table earns its place when readers compare values across a small set of dimensions. Give
each column a header, and keep cells to data rather than prose; a cell that needs full
sentences is a section wearing a table's clothes. Explanations belong in the surrounding
prose, not in the cells.

---

Portions of this file are modifications based on work created and shared by Google and used
according to terms described in the
[Creative Commons 4.0 Attribution License](https://creativecommons.org/licenses/by/4.0/):
the [Technical Writing courses](https://developers.google.com/tech-writing) and the
[Google developer documentation style guide](https://developers.google.com/style).
