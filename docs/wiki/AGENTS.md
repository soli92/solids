# AGENTS.md — LLM Wiki Schema

> **This file is the single source of truth for how any LLM agent must behave inside this repository.**
> Both Claude Code (`CLAUDE.md`) and Cursor (`.cursor/rules/wiki.md`) point here. Edit only this file.

---

## 0. What this repository is

This is an **LLM-maintained knowledge base** built on the pattern proposed by Andrej Karpathy
("LLM Wiki", April 2026). Raw sources are immutable inputs. The wiki is a compiled, structured,
interlinked artifact owned by the LLM. The human curates sources and asks questions.

> "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase." — A. Karpathy

---

## 1. Three-layer architecture (do not violate)

```
LAYER 3  — SCHEMA           AGENTS.md, prompts/, variants/   (rules)
LAYER 2  — WIKI             docs/wiki/                            (LLM-owned)
LAYER 1  — RAW SOURCES      docs/raw/                             (immutable)
                            docs/inbox/                           (human scratch, promotable to raw)
```

- **`docs/raw/`** — immutable. The agent **reads but never writes** here. Filenames are stable IDs.
- **`docs/inbox/`** — the human's scratch zone. The agent ignores it during ingest unless explicitly told
  to promote a file from `docs/inbox/` to `docs/raw/`.
- **`docs/wiki/`** — the agent owns this folder entirely. Humans read it; the agent writes it.
- **`prompts/`** — canned prompts for the three operations (ingest, query, lint).
- **`variants/`** — overlays that adjust this schema for specific use cases (tech project, research project).

---

## 2. Active variant

> **Default variant**: `research-project`
> Change the line below to switch behavior. Variants are described in `variants/`.

`active_variant: tech-project`

The active variant adds or overrides rules from this base schema. If the base schema and the variant
disagree, the variant wins.

---

## 3. The three operations

### 3.1 Ingest (`prompts/ingest.md`)

Trigger phrase from the human: `Ingest docs/raw/<filename>` (or a list of filenames).

Steps the agent **must** perform, in order:

1. Read the raw source completely. Do not skim.
2. Read `docs/wiki/index.md` and any wiki page whose name plausibly overlaps with the source's topics.
3. Produce or update these pages:
   - **One source page** in `docs/wiki/sources/<slug>.md` summarizing the source.
   - **Concept pages** in `docs/wiki/concepts/` for each non-trivial concept the source introduces or significantly extends.
   - **Entity pages** in `docs/wiki/people/`, `docs/wiki/orgs/`, `docs/wiki/products/` etc. as appropriate.
   - Updates to **existing** pages where the new source adds, contradicts, or refines prior content.
4. Add Obsidian-style `[[wikilinks]]` aggressively. A page with no incoming or outgoing links is a bug.
5. Append an entry to `docs/wiki/log.md` describing what was changed (see §6).
6. Update `docs/wiki/index.md` if new top-level pages were created.

After ingest, report to the human:
- The list of pages created or modified (with paths).
- Any **contradictions** detected vs existing wiki content. Do not silently resolve them — flag and ask.
- Any concepts mentioned in the source that you chose **not** to give their own page, with one-line reasoning.

### 3.2 Query (`prompts/query.md`)

Trigger: a natural-language question from the human.

Steps:

1. Do **not** re-read files in `docs/raw/` unless the wiki is genuinely insufficient and you say so explicitly.
2. Read `docs/wiki/index.md` first. Then follow `[[links]]` to relevant pages.
3. Answer using only what the wiki contains. If the wiki does not contain enough to answer, say so —
   do not fabricate, and do not silently fall back to your training data without flagging it.
4. Every non-trivial claim in the answer must include a citation to a wiki page (`[[page-name]]`),
   which itself must trace back to a raw source per §4.
5. At the end of a sufficiently substantive answer, ask the human: *"File this synthesis as a new
   wiki page?"* If yes, create it under `docs/wiki/syntheses/<slug>.md`.

### 3.3 Lint (`prompts/lint.md`)

Trigger: `Lint the wiki` (or a scoped variant like `Lint docs/wiki/concepts/`).

The agent audits and produces a **report** (does not auto-fix unless the human says so):

- **Orphan pages**: zero incoming links.
- **Dangling links**: `[[page-name]]` pointing to a page that does not exist.
- **Stub concepts**: concepts mentioned in 3+ pages but without a dedicated page.
- **Contradictions**: claims in two pages that disagree.
- **Source-less claims**: any claim in the wiki violating the rule in §4.
- **Stale pages**: pages not updated in N days when their referenced sources have been (heuristic).

After the report, the agent asks which fixes to apply. Never auto-edits during lint.

---

## 4. Citations to raw sources — HARD RULE

**Every non-trivial claim on every wiki page must be traceable to a raw source.**

- A "non-trivial claim" is anything beyond definitional or common-knowledge framing.
  Common knowledge ("Python is a programming language") does not need a citation.
  Specific factual claims, numbers, attributions, opinions of authors, mechanisms, dates: **always cite.**
- Inline citation format:
  `Sutton argues that general methods leveraging computation eventually win [^src: bitter-lesson.pdf §2].`
- A "source-less claim" detected during lint is a bug, not a style issue.
- The agent must not paraphrase a source so loosely that the original meaning is lost. When in doubt,
  use a short direct quote (under 15 words) and cite.
- **Synthesis pages** (`docs/wiki/syntheses/`) are the only place where claims may chain across sources.
  They must cite every source they synthesize from.

This rule exists because the main failure mode of the LLM Wiki pattern is **hallucinations cementing
as facts**. Citations are the immune system. Do not weaken them.

---

## 5. Page conventions

### 5.1 Frontmatter (mandatory on every wiki page)

```yaml
---
type: source | concept | entity-person | entity-org | entity-product | synthesis | overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [bitter-lesson.pdf, software-2-0.pdf]   # raw filenames this page draws from
status: draft | stable | needs-review
language: en | it
---
```

### 5.2 Filenames

- `kebab-case.md`, lowercase, no spaces.
- Source pages: filename matches the raw filename's slug (`bitter-lesson.pdf` → `bitter-lesson.md`).
- Concept pages: noun phrases (`reinforcement-learning.md`, not `what-is-rl.md`).

### 5.3 Page structure (recommended template)

```markdown
# <Title>

> One-sentence definition or thesis.

## Summary
2–4 sentences. Plain language.

## Key points
- Bullet, with [^src: ...] citations.

## Connections
- Related: [[other-page]] — one line on the relationship.
- Contrasts with: [[other-page]] — one line.

## Open questions
- Things the wiki does not yet answer.
```

Adapt as needed; do not pad to fit the template.

### 5.4 Linking rules

- Use `[[page-name]]`, not Markdown links, for intra-wiki links (Obsidian convention).
- Link generously but only on **first meaningful occurrence** in a page, then optionally again if context demands.
- A new page must have at least one incoming link before the ingest operation completes. If none of
  the existing pages naturally references it, the agent must add a reference somewhere relevant
  (typically `docs/wiki/index.md` or a parent concept page).

---

## 6. The log (`docs/wiki/log.md`)

Append-only. Every ingest, every batch lint-fix, every synthesis-pin appends one entry:

```markdown
## 2026-05-06 — Ingest: bitter-lesson.pdf
- Created: sources/bitter-lesson.md, concepts/search.md, concepts/learning.md, people/rich-sutton.md
- Updated: index.md
- Contradictions: none
- Notes: Did not create a page for "Moore's Law"; mentioned only in passing.
```

The log is the cheapest possible audit trail. Never delete entries. Corrections go in new entries.

---

## 7. Language policy

- **Schema, prompts, variants, frontmatter keys, filenames**: English. Always.
- **Wiki page content**: matches the language of the primary raw source(s) the page draws from.
  If a page synthesizes sources in mixed languages, default to **Italian** for now.
- **Filenames are always English** (kebab-case, ASCII) regardless of content language.

This policy is provisional. It will be revisited once the wiki has ~50 pages and a clear pattern emerges.

---

## 8. Behavioral rules for the agent

1. **Never modify `docs/raw/`.** Period.
2. **Never invent citations.** If you cannot point to a real `docs/raw/` file and a real location in it, do not cite.
3. **Prefer paraphrase over quote.** When you do quote, keep quotes under 15 words and never quote the
   same source twice on the same page.
4. **Flag, don't resolve.** When a new source contradicts the wiki, surface the contradiction to the
   human; don't silently overwrite.
5. **Touch many files in one ingest.** A good ingest typically touches 5–15 wiki files. Touching only
   the new source page is a smell.
6. **No emoji in wiki content.** Frontmatter, headers, prose all stay clean. (Prompts may use them.)
7. **No timestamps inside prose.** Use frontmatter `updated:` instead.
8. **Ask before destructive changes.** Renaming a page, merging two pages, deleting a page: confirm first.
9. **Stay within `docs/wiki/`.** Never write outside `docs/wiki/` and `docs/wiki/log.md` without explicit instruction.

---

## 9. Bootstrap (first-time setup)

On the very first interaction in a new repo cloned from this template, the agent must:

1. Ask the human: *"What is this wiki about? What kinds of sources will you feed it? Roughly how
   many sources are you planning? Tech project or research project variant?"*
2. Based on the answer, set the `active_variant` line in §2 of this file.
3. Write the seed `docs/wiki/index.md` with a 2-sentence description and an empty links section.
4. Write the seed `docs/wiki/log.md` with a "## YYYY-MM-DD — Bootstrap" entry.
5. Confirm: *"Schema initialized. Drop your first source in `docs/raw/` and tell me to ingest it."*
