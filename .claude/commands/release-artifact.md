---
description: >-
  Rilascio di un artefatto applicativo dichiarato in release_targets[] di factory.config.yaml.
  Gate locali su SHA immutabile (worktree-gate), gate umano R.14, trigger CI foreground,
  verifica registro/ambiente. Profili: container-gitops, package-registry, manifest-edit.
argument-hint: "<target> <version|ref> [--env=<env>] [--dry-run]"
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /release-artifact — Release artefatto applicativo a profili

Argomenti utente: `$ARGUMENTS`

- **target** (obbligatorio) — nome della voce in `release_targets[]` di `factory.config.yaml`
- **version|ref** (obbligatorio) — versione semver o ref git da rilasciare (es. `1.2.3`, `develop`)
- **--env=\<env\>** (obbligatorio) — ambiente target (deve essere in `environments[]` della voce)
- **--dry-run** (opzionale) — mostra il piano, esegui i gate locali, presenta il gate R.14 ma
  non triggerare il CI; append `wiki/log.md` con `stato: dry-run`

## Prerequisito

`release_targets[]` dichiarato e non vuoto in `factory.config.yaml`.
Se assente o vuoto → risposta esplicita (non errore):
"Nessun target dichiarato in `release_targets[]`. Aggiungere almeno una voce prima di procedere."

## Parsing argomenti

1. Il primo token non prefissato con `--` e' il **target**.
2. Il secondo token non prefissato con `--` e' il **version_or_ref**.
3. `--env=<env>` puo' essere in qualsiasi posizione.
4. `--dry-run` puo' essere in qualsiasi posizione.
5. Se `target` o `version_or_ref` mancano → STOP, chiedi in chat.
6. Se `--env` mancante → chiedi in chat quale ambiente usare tra quelli dichiarati.

## Procedura

1. **Validazione**
   - `target` deve esistere in `release_targets[]`. Altrimenti STOP con lista voci disponibili.
   - `env` deve essere in `environments[]` della voce. Altrimenti STOP con lista ambienti validi.
   - Carica il profilo dichiarato nella voce.

2. **Selezione agente**
   - Invoca `artifact-release-manager` passando: `target`, `version_or_ref`, `env`, `dry_run`.

3. **Esecuzione**
   - L'agente esegue `artifact-release-protocol` (skill) in 6 fasi.
   - Gate locali (worktree-gate) obbligatori se `local_gates[]` non e' vuoto.
   - Un gate umano R.14 obbligatorio (emissione JSON payload) — l'agente lo gestisce.
   - Se `env` corrisponde a un ambiente con `requires_double_confirm: true` (es. prod):
     doppia conferma esplicita e separata prima del trigger CI.

## Esempi

```
# Rilascio standard
/release-artifact my-api 1.2.3 --env=staging
/release-artifact frontend-lib 2.0.0 --env=prod

# Dry-run: mostra piano e gate locali senza triggerare CI
/release-artifact my-api develop --env=test --dry-run

# Con ref git
/release-artifact backend-svc main --env=test
```

## Profili supportati

| Profilo | Artefatto | Note |
|---|---|---|
| `container-gitops` | immagine container + manifest GitOps | build CI, push immagine, update kustomization |
| `package-registry` | pacchetto npm / pypi / maven | publish su registro privato o pubblico |
| `manifest-edit` | field in YAML/JSON | edit inline + commit; `vcs_api: none` = git locale |

## Config di esempio

Il blocco `release_targets[]` va aggiunto a `factory.config.yaml`.
Un esempio commentato e' in:
`/private/tmp/claude-*/scratchpad/config-US-312.yaml`

Struttura minima:
```yaml
release_targets:
  - name: my-api
    code_path: "code_repos/my-api"
    profile: container-gitops
    ci_provider: github
    pipeline_ref: "myorg/my-api/release.yml"
    registry: "ghcr.io/myorg/my-api"
    environments: [test, staging, prod]
    auth_env: GITHUB_TOKEN
    local_gates:
      - "npm test"
    requires_double_confirm: true   # richiede doppia conferma per tutti gli ambienti
```

## Note operative

- Il protocollo e' parametrico: nessun host, pipeline ID o nome di portale e' cablato
  nelle fasi. Aggiungere un target = aggiungere una riga a `release_targets[]`.
- `local_gates[]` vuoto e' lecito: nessun gate locale viene eseguito.
- L'entry su `wiki/log.md` e' sempre scritta, anche in caso di abort o dry-run.
- Il polling CI e' sempre foreground (nessun background task).
- Per il contratto di ogni provider CI vedi `.claude/skills/references/artifact-release-protocol/ci-providers.md`.
