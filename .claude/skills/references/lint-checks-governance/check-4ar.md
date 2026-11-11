# Check 4ar — Annotazioni SUNSET scadute (dettaglio completo)

Ambito: dettaglio del Check 4ar in `lint-checks-governance.md`. Leggere prima di eseguire.

---

**Trigger**: sempre attivo — nessun flag richiesto. Fonte di verità della versione corrente:
`factory.config.yaml.pattern_version` (SSOT, come Check 4am).
**Severità**: **ERROR** — e non WARNING. Un'annotazione `SUNSET: vX.Y` scaduta è un fallimento
*silenzioso* della governance §23.8: senza segnale, la capability sopravvive per inerzia.
**Non `heal-eligible`** per costruzione: uccidere un layer richiede giudizio umano, e un
auto-fix qui equivarrebbe a cancellare una capability senza decisione.
**Esenzioni**: `CHANGELOG.md` (release history storica per natura), `meta-prompts/` e
`archive/` (snapshot immutabili), `wiki/decisions/` (registri di deliberazione),
`management/kanban/` + `raw/` + `validation/` (artefatti che *parlano* di annotazioni
senza portarle), e ogni riga che contiene il marker `SUNSET-EXEMPT` (§23.8 esenzione
dichiarata).
**Audience**: maintainer che producono release.

**Provenienza**: Tavola Rotonda TR-9b4e7c02 (2026-09-17). Reperto misurato: §23.8 è stato
eseguito come annotazione e **mai come azione, 0 su 7** — 7 annotazioni `SUNSET: v2.36`
ancora presenti a `pattern_version: 2.42`, sei release oltre la scadenza dichiarata. Il
check è il prerequisito di credibilità per qualunque nuova capability.

## Algoritmo

1. **Leggi** `factory.config.yaml` → `pattern_version` (es. `"2.42"`). Se assente → skip
   silenzioso, 0 finding (graceful degradation, come 4am).
2. **Scansiona** i file con suffisso `.yaml`/`.yml`/`.md`/`.py`/`.sh`/`.json`, escludendo
   le directory e i nomi esenti.
3. Per ogni riga, cerca `SUNSET:\s*v(\d+)\.(\d+)`. **Salta** la riga se contiene
   `SUNSET-EXEMPT`, o se il match cade **dentro uno span delimitato da backtick**.
4. Se la versione dichiarata è **minore** di `pattern_version` → **ERROR**, con il numero
   di release di ritardo quando il major coincide.

## Invarianti

- **Citazione ≠ annotazione**: un'annotazione racchiusa in backtick è la *menzione* di
  un'annotazione (prosa, `wiki/log.md`, testo di un TSK), non un'annotazione viva su una
  capability. Senza questa regola il check flagga la documentazione di sé stesso — verificato
  in implementazione: 10 finding grezzi → 3 falsi positivi eliminati → 7 reali.
- **Un artefatto di pianificazione non è un'annotazione**: l'esclusione di
  `management/kanban/` è stata aggiunta il 2026-09-18 dopo un falso positivo reale — il
  titolo di `TSK-581`, che è il task *incaricato di risolvere* le 7 annotazioni, cita
  `SUNSET: v2.36` senza backtick e veniva contato come ottava annotazione scaduta. La
  regola dei backtick copre le citazioni inline; questa copre i titoli e il testo dei
  task. **Variante più stretta in attesa di ratifica**: l'emendamento in
  `design_&_architecture/emendamento-pattern-23-8-sunset-2026-09-18.md` §6 propone di
  sostituire questa blocklist con una **allowlist** dei due soli luoghi che §23.8
  prescrive (`factory.config.yaml` + `PATTERN.md`). È più corretta della blocklist, ma
  è sequenziata **dopo** la ratifica della policy: non applicare entrambe.
- **Tre uscite legittime, nessuna delle quali è «ignora»**: rimuovere la capability;
  rinnovare l'annotazione con motivazione esplicita e nuova versione; marcarla
  `SUNSET-EXEMPT`. Il check non impone quale — impone che una sia scelta.
- **Mai auto-fix**: non `heal-eligible` in nessuna circostanza.

## Esecuzione

```bash
python3 tools/lint/check-expired-sunset.py .          # report umano
python3 tools/lint/check-expired-sunset.py . --json   # machine-readable
```

Exit code `1` se almeno un'annotazione è scaduta, `0` altrimenti — utilizzabile come gate.

## Output format

```
## ERROR (governance, mai heal-eligible)
- [ERROR][sunset-expired][4ar] factory.config.yaml:109: annotazione v2.36 con pattern_version v2.42 (6 release oltre la scadenza). Azione: rimuovere la capability, oppure rinnovare l'annotazione con motivazione esplicita, oppure marcarla SUNSET-EXEMPT. Contesto: # SUNSET: v2.36 (N=3 from v2.33, 2026-07-20) — not exercised on external derived factories
```

[^src: wiki/decisions/tavola-rotonda-9b4e7c02-5a1d-4f38-8c61-2d7a3e9f5b40-2026-09-17.md §Sintesi M0.d]
[^src: PATTERN.md §23.8 — sunset policy]
