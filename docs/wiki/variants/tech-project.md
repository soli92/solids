# Variant: tech-project

Use when this LLM Wiki lives **inside a code repository** (typically as `docs/wiki/`) and
documents a software project: a service, a library, a product. Code is the primary artifact;
the wiki is the layer of meaning around it.

To activate, set `active_variant: tech-project` in `AGENTS.md` §2.

---

## What changes vs. the base schema

### Folder layout (recommended)

When this variant is active, the wiki sits at `docs/wiki/` of the host repo, and its internal
structure is:

```
docs/wiki/
├── index.md
├── log.md
├── sources/         # external: papers, RFCs, vendor docs that informed the project
├── concepts/        # domain concepts: "idempotency in our payment flow", "tenant isolation"
├── decisions/       # ADRs (Architecture Decision Records). One per decision. Append-only.
├── runbooks/        # "if X breaks, do Y". Operational knowledge.
├── incidents/       # post-mortems. Append-only.
├── components/      # one page per non-trivial code component, linked to its source path
└── syntheses/       # cross-cutting answers worth pinning
```

The `docs/raw/` folder still exists at repo root (or under `docs/raw/`) for ingestible external
sources: papers, RFCs, vendor PDFs, screenshots of dashboards.

### Behavioral overrides

- **Code IS a source.** Component pages must reference the actual file path in the repo
  (e.g., `src/payments/processor.ts`). When the agent re-indexes, it should diff the code
  against the component page and flag drift. Code locations are cited the same way as raw files:
  `[^code: src/payments/processor.ts:142]`.
- **ADRs are immutable.** Once a decision page is written and merged, it is not edited; it is
  superseded by a new ADR that links back. Same for incident post-mortems.
- **Runbooks have a freshness contract.** Every runbook has a `last-verified: YYYY-MM-DD` field;
  lint flags runbooks not verified in 90 days.
- **PII / secrets / customer data**: never ingest raw logs or DB dumps that contain them.
  If the human asks to ingest such a file, the agent must refuse and explain what to redact first.

### What "non-trivial claim" means here

Anything about how the system actually behaves: timeouts, retry logic, schemas, ownership,
SLAs, dependencies. Always cite — to a code path, an ADR, an incident, or an external source.
Generic statements about the language/framework ("React components re-render on state change")
do not need citations.

### Multi-actor / enterprise notes

- The wiki is **versioned with the code** and goes through PR review like code does.
- Every wiki PR should be reviewable in under 15 minutes. If a single ingest produces a 50-file
  change, split it.
- The agent must never push directly to the main branch. Always work on a branch, always open
  a PR, always include the `docs/wiki/log.md` entry in the PR.
- A `CODEOWNERS`-style mapping for `docs/wiki/` is recommended so domain owners review their areas.
