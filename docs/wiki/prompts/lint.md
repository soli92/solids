# Lint prompt

Use periodically (every ~10 ingests, or monthly) to keep the wiki healthy.

---

## Full lint

> Lint the wiki.
>
> Follow `AGENTS.md` §3.3. Produce a structured report with these sections:
>
> 1. **Orphan pages** (zero incoming links) — list with proposed parent pages.
> 2. **Dangling links** — list with the source page that contains them.
> 3. **Stub concepts** — concepts mentioned in 3+ pages but lacking a dedicated page.
> 4. **Contradictions** — pairs of claims that disagree, with both citations.
> 5. **Source-less claims** — non-trivial claims missing `[^src: ...]`.
> 6. **Stale pages** — pages whose `updated:` is older than their cited sources' last ingest.
>
> Do not fix anything. After the report, ask me which categories to address and in what order.

## Scoped lint

> Lint `docs/wiki/concepts/` only. Same procedure as full lint, restricted to this folder.

## Citation audit (most important)

> Audit citations across the entire wiki. For every `[^src: <filename> §<location>]`:
>
> 1. Verify the file exists in `docs/raw/`.
> 2. Spot-check 5 randomly chosen citations by re-reading the cited location and confirming the
>    wiki claim is supported. Report any mismatches verbatim.
> 3. Flag any non-trivial claim that lacks a citation (per `AGENTS.md` §4).
>
> This is the single most important lint. Run it before any major use of the wiki for decisions.
