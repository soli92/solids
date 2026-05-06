# Variant: research-project

Use when the wiki **is** the project: a topic you are studying, a book you are reading,
a research area you are tracking, a personal journal of ideas.

This variant is the **default** in `AGENTS.md` §2.

---

## What changes vs. the base schema

### Page types emphasized

- `docs/wiki/sources/` — one page per ingested source. **Required for every raw file.**
- `docs/wiki/concepts/` — concept pages. The bulk of the wiki lives here.
- `docs/wiki/people/` — author/researcher pages, when 2+ sources reference a person.
- `docs/wiki/syntheses/` — answers to substantive query operations, pinned for reuse.
- `docs/wiki/overviews/` — periodic high-level maps of a sub-area (manually requested).

Do NOT create: `decisions/`, `runbooks/`, `incidents/`. Those are tech-project pages.

### Behavioral overrides

- **Synthesis is a first-class operation.** Encourage filing query answers as wiki pages more
  aggressively than the base schema (lower threshold for "this is worth keeping").
- **Author voice matters.** Concept pages should distinguish how different authors frame the same
  concept, not collapse them into a single neutral definition. E.g., "Sutton's framing" vs.
  "Karpathy's framing" sections under one concept page.
- **Open questions are valuable.** The "Open questions" section on each page is not optional in
  this variant — it drives the next round of source-seeking.

### What "non-trivial claim" means here

In research, almost every specific statement is non-trivial. Be generous with citations.
Definitional framing of common terms ("a transformer is a neural network architecture") does not
need a citation; specific properties, history, comparisons, and any author's opinion always do.

### Lint cadence

Recommend full lint every ~10 ingests, citation audit every ~25 ingests.
