# Ingest prompt

Use this when you have dropped one or more files in `docs/raw/` and want them compiled into the wiki.

---

## Single source

> Ingest `docs/raw/<filename>`.
>
> Follow the ingest procedure in `AGENTS.md` §3.1 exactly. Before writing anything,
> tell me which existing wiki pages you plan to touch and why. Then proceed.

## Batch

> Ingest the following sources, in order, treating each as a separate ingest operation
> (so contradictions between them get surfaced rather than silently merged):
>
> - `docs/raw/<filename-1>`
> - `docs/raw/<filename-2>`
>
> Follow `AGENTS.md` §3.1. After each source, summarize what changed before moving to the next.

## Re-ingest (when a source has been updated)

> Re-ingest `docs/raw/<filename>`. The file has changed since the last ingest. Identify which wiki pages
> currently cite this source, diff their claims against the new content, and report what needs updating.
> Do not edit until I confirm.
