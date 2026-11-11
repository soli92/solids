---
skill: check-4au-algoritmo
part_of: lint-checks-agent-fleet
scope: "Esecuzione del Check 4au — Roll-up di stato TSK/US/epica: script, generalizzazioni G1/G2/G3, regole applicate"
---

# Check 4au — Esecuzione

> Foglia di dettaglio del Check 4au. File principale:
> `.claude/skills/lint-checks-agent-fleet.md` (descrizione, sub-check, severita', vincoli
> V1/V2, output format, invarianti, scenari di verifica).
>
> **Derivazione**: algoritmo di EP-068 / US-296 (2026-09-25), reso eseguibile da EP-071 /
> US-324 (2026-10-06). La procedura passo-passo che stava qui ora la esegue lo script.

---

## Come si esegue

L'algoritmo e' implementato: non va ricostruito, interpretato ne' stimato.

```bash
python3 tools/lint/check-status-rollup.py            # righe nel formato del report
python3 tools/lint/check-status-rollup.py --json     # findings + conteggi per sub-check
python3 tools/lint/run-deterministic.py              # 4au insieme agli altri check eseguibili
```

Le righe si riportano **cosi' come sono** nella sezione `## WARNING (roll-up di stato, mai
heal-eligible)` del report, insieme alle righe diagnostiche (`[Passo 1]`, `[4au] V1`,
`[4au.5] sprint.md: N righe lette`, `Riepilogo 4au: ...`). Exit 0 sempre: il check e'
WARNING-only. Se lo script fallisce, 4au si marca `NON ESEGUITO` con l'errore: nessuna stima
al suo posto.

Opzioni: `--root <factory>` (un'altra factory, o uno snapshot), `--out <file>`,
`--strict` (exit 1 solo con ERROR: per 4au non accade mai).

---

## Generalizzazioni applicate (normative)

| # | Assunzione sorgente | Realta' misurata su questa factory | Forma generale |
|---|---|---|---|
| G1 | ID sempre con prefisso di namespace (`.+-EP-\d+$`) | ID senza prefisso: `EP-068`, `US-296`, `TSK-690`; cartelle con slug | Prefisso **opzionale**, cartella riconosciuta dall'ID iniziale: forma degli ID da `tools/coordinamento/kanban_ids.py`, la stessa fonte del report PM (EP-070) |
| G2 | `sprint.md` con tabella **epica-level** e colonna status dedicata | `sprint.md` **TSK-level**, status nell'**ultima colonna** | 4au.5 = «status nell'ultima colonna della riga di `sprint.md` vs frontmatter dell'artefatto citato, **a qualunque granularita'**» (TSK, US o epica) |
| G3 | US/epiche in tabella come ID nudo (`\| US-268 \|`) | ID in link markdown: `\| [US-268](path/US-268.md) \|` | Prima cella letta come ID nudo, in grassetto o in link markdown |

Senza G1 e G3 il check non matcha nulla e passa in silenzio; senza G2 il 4au.5 non ha righe
da leggere — il difetto che EP-068 combatte.

## Cosa confronta lo script

| Passo | Sub-check | Confronto |
|---|---|---|
| 1 | — | raccolta di EP/US/TSK per nome file (`<ID>.md`, archivio incluso); conteggio in `[Passo 1]` |
| 2 | 4au.1, 4au.2 | status della US vs status dei suoi TSK |
| 3 | 4au.3, 4au.4 | status dell'epica vs status delle sue US |
| 4 | 4au.5 | ultima colonna di ogni riga di `sprint.md` il cui primo campo e' un ID vs frontmatter |
| 5 | 4au.6 | US nella prima colonna di una tabella dell'epica senza file corrispondente |
| 6 | 4au.7 | US il cui campo epica punta a un'epica senza file, o che non la cita |

**Appartenenza.** I TSK di una US sono quelli che la dichiarano in frontmatter (`story:`,
`us:`, ...; in mancanza la cartella che la contiene) piu' quelli elencati dalla US in
`tsk_ids`/`tsk_range`; le US di un'epica quelle con `epic:`/`ep:`/`epic_id:` (in mancanza la
cartella). Il campo epica di 4au.7 si legge con gli stessi nomi.

**V1 — solo frontmatter, primi 64 KB.** Lo `status:` nel corpo (template YAML) non conta mai.
Il frontmatter si legge fino al `---` di chiusura: con il vecchio limite di 4 KB le epiche con
`progress_notes` lunghe restavano senza stato e uscivano in silenzio da tutti i sub-check. Un
artefatto il cui frontmatter si chiude oltre i 64 KB resta fuori dal roll-up, ma **non in
silenzio**: la riga `[4au] V1: N artefatti con frontmatter oltre 64 KB esclusi dal roll-up`
li elenca.

**V2 — normalizzazione.** Minuscole, `-` = `_` (`in-progress` = `in_progress`); dalle celle di
`sprint.md` si tolgono `*` e `~` (`~~cancelled~~` = `cancelled`) e vale la prima parola.
Due stati entrambi terminali non sono un disallineamento (`completed` vs `done`, scenario 11).
Nelle celle `~~in_progress~~ → on_hold` vale lo stato dopo la freccia: scartarle nascondeva
disallineamenti reali.

**V3 — solo stati riconosciuti.** In ogni riga di `sprint.md` lo stato e' l'ultima cella che
contiene uno stato noto (terminale o aperto), anche se non e' l'ultima colonna. Le righe senza
nessuno stato noto (note, «idem», label) non si confrontano: una sola riga INFO le conta.

## Limiti dichiarati

- **ID locali relativi** (`US-003`, anche in link, nella tabella di un'epica le cui US si
  chiamano `XX-US-NNN`). Se **ogni** artefatto del kanban ha il prefisso di namespace, un ID senza
  prefisso e' una numerazione locale: 4au.6 e 4au.7 danno **una riga INFO per epica** invece di
  un finding per US (la misura di portale-servizi-factory: 76 falsi positivi). In un kanban con
  ID senza prefisso la distinzione non e' possibile: 4au.6 segnala ogni ID senza file e 4au.7
  porta il tag `[potenziale falso positivo se tabella usa ID locali relativi]`.
- **4au.5 e le celle di stato ambigue**: una cella di note che comincia con una parola di stato
  («done in parte», «todo: ...») viene letta come stato. V3 riduce il caso, non lo esclude.

## Misura di riferimento

Sul kanban del commit `558bb2f` (quello misurato da TSK-691) lo script da'
`4au.1=4 4au.4=1 4au.5=135 4au.7=6`: il 4au.5 coincide con il conteggio riparato di TSK-691
(178 − 43 falsi positivi da `~~cancelled~~`). Il 4au.7 sale da 1 a 6 per due ragioni misurate:
quattro US (US-171..174) dichiarano l'epica con `epic_id:`, che la procedura precedente non
leggeva; e `US-086` esiste in due file (EP-012 ed EP-024): la procedura indicizzava le US per ID
e ne vedeva una sola, lo script le controlla entrambe.

[^src: management/kanban/EP-068-backport-enforcement-factory-derivata/US-296-check-4au-rollup-stato/TSK-691.md §Conteggio reale, dopo le riparazioni]
[^src: management/kanban/EP-071-backport-esecuzione-derivata/US-324-lint-deterministico/TSK-739.md §Misure]
