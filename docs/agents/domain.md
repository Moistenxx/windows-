# Domain Docs

This is a single-context repo.

## Before exploring, read these when present

- `CONTEXT.md` at the repo root
- `docs/adr/` for architectural decisions relevant to the current work

If these files do not exist yet, proceed silently. They should be created lazily when domain language or architectural decisions are actually resolved.

## Layout

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use project vocabulary

When output names a domain concept in an issue, implementation plan, test, or review, use the vocabulary from `CONTEXT.md` when it exists.

If a needed concept is missing, note it for `/domain-modeling` rather than inventing competing terms.

## ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly instead of silently overriding it.
