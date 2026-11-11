# Cursor adapter templates

This folder contains **reference templates** that can be automatically scaffolded by the
meta-prompt v2.13 (`bootstrap-multiadapter-protocol`). They are **consistent starters**: the
operational content (responsibilities, scope, gates, rules) is IDENTICAL to the
meta-framework's `.claude/<corresponding>.md`; only the tool invocation and the
Cursor `.mdc` format differ.

## Present files (complete translation examples)

| Type | Path | Claude Code reference |
|---|---|---|
| Agent | `rules/orchestrator.mdc` | `.claude/agents/orchestrator.md` |
| Agent | `rules/wiki-keeper.mdc` | `.claude/agents/wiki-keeper.md` |
| Skill | `rules/skills/ingest-protocol.mdc` | `.claude/skills/ingest-protocol.md` |
| Skill | `rules/skills/branch-resolver.mdc` | `.claude/skills/branch-resolver.md` (EP-034 v2.25) |
| Skill | `rules/skills/vcs-preflight-protocol.mdc` | `.claude/skills/vcs-preflight-protocol.md` (EP-034 v2.25) |
| Command | `commands/run.md` | `.claude/commands/run.md` |
| Command | `commands/vcs-status.md` | `.claude/commands/vcs-status.md` (EP-034 v2.25) |

## Missing files (scaffolded at bootstrap from the manifest)

All other files declared in `../manifest.yaml`. The `bootstrap-multiadapter-protocol`:

1. Reads `manifest.yaml`.
2. For each template not already present in this folder, generates the `.mdc` file
   by translating from the meta-framework's `.claude/<corresponding>.md` via the
   mappings in `manifest.yaml.mappings`.
3. Writes to `<factory>/.cursor/`.

## Translation convention

### Frontmatter

| Claude Code | Cursor `.mdc` |
|---|---|
| `name: <slug>` | (absent — use the filename) |
| `description: ...` | `description: ...` |
| `model: claude-sonnet-4-6` | (absent — Cursor uses the global model) |
| `tools: [Read, Write, Edit, Glob, Bash]` | `globs: <pattern>` (Cursor activates via glob match) |

### Body

| Claude Code | Cursor `.mdc` |
|---|---|
| `See \`<skill>\`.` | `See [<skill>](mdc:.cursor/rules/skills/<skill>.mdc).` |
| `Invoke \`Agent(subagent_type=<X>)\`` | "Manually invoke Compose agent with rule `<X>.mdc`" |
| `Read <file>` | `@<file>` (mention) or "Open `<file>` in agent mode" |
| `Write <file>` | "Create `<file>` via Edit/Apply" |
| `Bash <cmd>` | "Run `<cmd>` in the embedded terminal" |

### Body sections

Canonical sections of the `.claude/agents/<X>.md` template:
- `## ROLE: <name>` — unchanged
- `## Scope` — unchanged (Read / Write / Never write to)
- `## Trigger` — unchanged
- `## Procedure` — skill references updated with `mdc:` URIs
- `## Rules` — unchanged (cites PATTERN §7)

See `rules/orchestrator.mdc` as a complete translation example.

## Validation

After scaffolding, verify:
- Every `.mdc` has valid frontmatter (`description` required; `globs` or `alwaysApply: true`).
- `mdc:` links point to files that were actually scaffolded (no broken links).
- The body correctly cites PATTERN.md §X (not `<claude>/path/...`).

`wiki-lint` (also in Cursor) will check routing↔layers consistency as for `.claude/`.
