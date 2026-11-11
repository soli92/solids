# Check 4al — CHANGELOG ↔ GATE-REPORT coerenza (dettaglio completo)

Ambito: dettaglio del Check 4al in `lint-checks-governance.md`. Leggere prima di eseguire.

---

**Trigger**: sempre attivo — nessun flag richiesto. L'invariante di gate è un contratto di
governance non configurabile: ogni dichiarazione "Gate vX PASS" nel CHANGELOG deve avere
un artefatto GATE-REPORT corrispondente.
**Severità**: ERROR (GATE-REPORT mancante) / WARNING (GATE-REPORT con `verdict: bypass`).
**Esenzione**: versioni v2.18 e precedenti — nessun check (il GATE-REPORT formale non esisteva).
**Audience**: maintainer che producono release dichiarando "Gate vX PASS" nel CHANGELOG.

## Algoritmo

1. **Leggi** `CHANGELOG.md` (se assente → skip silenzioso, 0 ERROR/WARNING).
2. **Scansiona** per pattern `Gate v([0-9]+\.[0-9]+) PASS` (regex, case-sensitive).
3. Per ogni versione `vX` trovata:
   - **Esenzione**: se la parte minor è ≤ 18 con major 2 (es. v2.18, v2.17 ...) → skip silenzioso (nessun check).
   - Verifica esistenza di `validation/release-gates/vX/GATE-REPORT.md`.
   - File **assente** → **ERROR** `changelog-gate-report-missing`:
     `"CHANGELOG dichiara Gate vX PASS ma validation/release-gates/vX/GATE-REPORT.md mancante"`
   - File **presente** ma contiene la stringa `verdict: bypass` → **WARNING** `changelog-gate-report-bypass`:
     `"GATE-REPORT vX ha verdict: bypass (non pass)"`
   - File presente con qualsiasi altro `verdict:` (tipicamente `verdict: pass`) → OK, skip.

## Invarianti

- **Always-on**: nessun gate config — il check rispecchia un'invariante di governance non configurabile
  (distinto da 4w/4x che sono gated da `battle_test_gate.enabled`).
- **Esenzione v2.18-**: le versioni v2.18 e precedenti (minor ≤ 18, major 2) sono esenti; non
  avevano il GATE-REPORT formale. Versioni con major diverso da 2 seguono la stessa logica:
  solo versioni ≥ v2.19 (nel ramo v2.*) sono soggette al check.
- **Mai heal-eligible**: la creazione del GATE-REPORT richiede giudizio semantico (contenuto del run).
- **Read-only**: legge solo `CHANGELOG.md` e `validation/release-gates/*/GATE-REPORT.md`.
- **Graceful degradation**: `CHANGELOG.md` assente → skip silenzioso (0 check, 0 ERROR/WARNING).

## Rilevamento pattern (pseudocodice)

```
if not exists("CHANGELOG.md"):
    return  # graceful degradation

content = read("CHANGELOG.md")
matches = findall(r"Gate v([0-9]+\.[0-9]+) PASS", content)

for version_str in matches:
    major, minor = version_str.split(".")
    if int(major) == 2 and int(minor) <= 18:
        continue  # esenzione v2.18-

    gate_report_path = f"validation/release-gates/v{version_str}/GATE-REPORT.md"

    if not exists(gate_report_path):
        emit ERROR changelog-gate-report-missing
    elif "verdict: bypass" in read(gate_report_path):
        emit WARNING changelog-gate-report-bypass
    # else: verdict: pass o altro valore valido → OK
```

## Output format

```
## ERROR non meccanici (manuali)
- [ERROR][changelog-gate-report-missing][4al] CHANGELOG dichiara Gate v2.20 PASS ma validation/release-gates/v2.20/GATE-REPORT.md mancante.

## WARNING (igiene, mai heal-eligible)
- [WARNING][changelog-gate-report-bypass][4al] GATE-REPORT v2.19 ha verdict: bypass (non pass).
```

## Scenari di verifica

| # | CHANGELOG contiene | GATE-REPORT esiste | `verdict:` | versione | esito atteso |
|---|---|---|---|---|---|
| 1 | `Gate v2.19 PASS` | no | — | v2.19 | **ERROR 4al** (GATE-REPORT mancante) |
| 2 | `Gate v2.19 PASS` | si | `pass` | v2.19 | no ERROR/WARNING (GATE-REPORT valido) |
| 3 | `Gate v2.19 PASS` | si | `bypass` | v2.19 | **WARNING 4al** (GATE-REPORT con bypass) |
| 4 | `Gate v2.18 PASS` | no | — | v2.18 | no check (versione esente ≤ v2.18) |
| 5 | `Gate v2.17 PASS` | no | — | v2.17 | no check (versione esente ≤ v2.18) |
| 6 | nessun pattern `Gate vX PASS` | — | — | — | no ERROR/WARNING |
| 7 | CHANGELOG assente | — | — | — | no ERROR/WARNING (graceful degradation) |
| 8 | `Gate v2.33 PASS` | no | — | v2.33 | **ERROR 4al** (GATE-REPORT mancante) |
| 9 | `Gate v2.33 PASS` | si | `bypass` | v2.33 | **WARNING 4al** |
| 10 | `Gate v2.33 PASS` | si | `pass` | v2.33 | no ERROR/WARNING |

## Cross-link

4al → `CHANGELOG.md` (fonte) + `validation/release-gates/*/GATE-REPORT.md` (artefatto atteso) +
EP-049 (Governance Enforcement) + US-179 (origine) + Check 4w (companion: schema RUN-REPORT,
EP-012) + Check 4x (companion: CHANGELOG validation evidence, EP-012) +
skill `release-validation-gate.md` (enforcement primario a tag-time).
