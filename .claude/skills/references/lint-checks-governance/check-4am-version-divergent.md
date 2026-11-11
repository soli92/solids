# Check 4am — Versioni divergenti da factory.config.yaml (dettaglio completo)

Ambito: dettaglio del Check 4am in `lint-checks-governance.md`. Leggere prima di eseguire.

---

**Trigger**: sempre attivo — nessun flag richiesto. Fonte di verità: `factory.config.yaml.pattern_version`.
**Severità**: WARNING — non ERROR (le versioni nei commenti storici non devono bloccare la factory). Non `heal-eligible` (il bump manuale richiede giudizio).
**Esenzioni**: `CHANGELOG.md` (contiene versioni storiche per natura — non viene scansionato).
**Audience**: maintainer che producono release e bump di versione.

## Implementazione

```
python3 tools/lint/check-version-coherence.py [--json] [--root <path>]
```

- `--json` per output machine-readable.
- `--root <path>` per eseguire il check su un'altra factory della flotta senza copiare lo script.
- Exit 0 sempre (WARNING-only); exit 2 solo se `factory.config.yaml` e' assente o privo di `pattern_version`.

## Algoritmo

1. **Leggi** `factory.config.yaml` → campo `pattern_version` (es. `"2.43"`). Se assente → exit 2 (graceful degradation).
2. **Leggi il profilo** `version_coherence.profile` (`framework` | `derived`; chiave assente =
   `derived`). Solo il meta-framework dichiara `framework`; la chiave **non** va propagata.
3. **Controlla ogni sito** dichiarato nella lista `SITES` dello script, secondo il suo scope:
   - scope `all` (PATTERN.md, copiato identico ovunque): assente o regex non matcha →
     finding `version-site-missing` (un sito dichiarato che non matcha e' indistinguibile dal
     silenzio — e' un finding, non uno skip).
   - scope `framework` (CLAUDE.md, README, sprint.md, dispatcher, meta-prompts): come `all`
     con profilo `framework`; con profilo `derived` un sito assente o senza la riga e'
     **elencato come non applicabile** nell'output (dichiarato, non saltato).
   - scope `optional`: assente → silenzio.
   - In ogni scope, versione trovata diversa da `pattern_version` → finding `version-divergent`.
4. **CHANGELOG.md è esente** — non fa parte dei siti e non viene scansionato.

> Perche' il profilo (2026-10-05): con `--root` su una derivata i siti erano quelli della
> madre, cablati come obbligatori. Ogni factory della flotta dava 5-7 `version-site-missing`
> su file che per progetto non porta, e il finding vero — `PATTERN.md` indietro in 7
> derivate su 7 — annegava nel rumore.

## Invariante chiave — sito dichiarato che non matcha = finding

Un sito dichiarato che non matcha la sua regex produce `version-site-missing`, non uno skip
silenzioso. Il silenzio del check e' indistinguibile dal successo: se il pattern cambia (ad
esempio qualcuno riscrive l'intestazione di un file), il check deve segnalarlo invece di
smettere di guardare. Questo e' il difetto che ha reso la divergenza di `sprint.md`
invisibile per giorni (2026-09-25, misurato).

## Versione corrente chiamata «candidate» (EP-080)

Un sito puo' dichiarare la versione giusta e contraddirsi due righe sopra. Il 2026-10-18 il
dispatcher diceva «v2.44 corrente» alla riga 14 e «v2.44 candidate ... non e' ancora la
versione corrente» alla riga 5: il check di sito era verde. `version-stale-candidate` legge
ogni sito presente, in ogni profilo, e segnala `v<corrente> candidate` (anche `**v2.44
candidate**` e `v2.44-candidate`). `management/kanban/sprint.md` e' esente: le intestazioni
degli sprint chiusi registrano la versione bersaglio di allora.

## Invarianti generali

- **Warning-only**: mai ERROR — il bump manuale richiede giudizio sul repo completo.
  Non `heal-eligible`.
- **Esenzione CHANGELOG.md**: la cronologia della release history e' legittima per natura.
- **SSOT**: `factory.config.yaml.pattern_version` e' la fonte autoritativa.
- **Graceful degradation**: se `pattern_version` e' assente in `factory.config.yaml` → exit 2
  (segnalato su stderr), non un crash.

## Output format

```
SSOT factory.config.yaml#pattern_version = 2.43
Root: /path/to/factory
Profilo: framework
- [WARNING][version-divergent][4am] management/kanban/sprint.md (frontmatter `pattern_version:`): dichiara versione 2.42 divergente da factory.config.yaml (pattern_version: 2.43)

1 WARNING. Check advisory: non blocca, il bump richiede giudizio sul repo completo.
```

## Scenari di verifica

| # | `pattern_version` | PATTERN.md | CLAUDE.md | sprint.md `pattern_version:` | CHANGELOG.md | esito atteso |
|---|---|---|---|---|---|---|
| 1 | `"2.43"` | `2.43` | `v2.43` | `"2.43"` | `v2.42`, `v2.41` | OK (CHANGELOG esente, tutti allineati) |
| 2 | `"2.43"` | regex non matcha | `v2.43` | `"2.43"` | — | **WARNING 4am** `version-site-missing` (PATTERN.md) |
| 3 | `"2.43"` | `2.42` | `v2.43` | `"2.43"` | — | **WARNING 4am** `version-divergent` (PATTERN.md) |
| 4 | `"2.43"` | `2.43` | `v2.43` | `"2.42"` | — | **WARNING 4am** `version-divergent` (sprint.md) |
| 5 | assente | qualsiasi | qualsiasi | qualsiasi | — | exit 2 (graceful degradation) |
| 6 | `"2.43"` | `2.43` | `v2.43` | `"2.43"` | qualsiasi | OK (CHANGELOG esente) |
| 7 | `"2.43"`, profilo `derived` | `2.43` | assente | assente | — | OK; CLAUDE.md e sprint.md elencati come non applicabili |
| 8 | `"2.43"`, profilo `derived` | `2.27` | assente | assente | — | **WARNING 4am** `version-divergent` (PATTERN.md) |

## Cross-link

4am → `factory.config.yaml.pattern_version` (SSOT versioning) +
`tools/lint/check-version-coherence.py` (implementazione) +
EP-052 (Tech Debt Cleanup) + US-187 (versioning canonico) + US-297 (Check 4am eseguibile) +
skill `bump-version` (procedura allineamento).
