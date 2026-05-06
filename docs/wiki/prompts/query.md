# Query prompt

Use this when you want to ask the wiki a question. Pick the variant that fits your need.

---

## Direct lookup

> Question: <your question>
>
> Answer using only the wiki. Cite every non-trivial claim with `[[page-name]]`. If the wiki
> doesn't contain enough to answer, say so explicitly — do not fall back to general knowledge.

## Synthesis across sources

> Question: <your question>
>
> This is a synthesis question. Read `docs/wiki/index.md`, then traverse `[[links]]` to gather every
> page relevant to the question. Build the answer from connections between pages, not from any
> single page. Cite. At the end, propose a filename under `docs/wiki/syntheses/` if the answer is
> worth keeping; ask me before creating it.

## Devil's advocate

> Question: <your question>
>
> Answer twice: once steelmanning the most-supported position in the wiki, then once arguing
> the strongest counter-position the wiki contains (or that its sources hint at). Cite both.
> If the wiki has no real counter-position, say so plainly — do not invent one.

## Gap-finding

> Topic: <topic>
>
> What does the wiki currently say about this topic, and — more importantly — what is missing?
> List specific questions a reader would have that the wiki cannot answer. These become the
> next sources to seek out.
