# Check 4aq — Path portabili cross-platform (dettaglio)

Ambito: dettaglio del Check 4aq in `lint-checks-config.md`. Leggere prima di interpretare un finding.

---

**Origine**: incidente 2026-09-16. Tre log di release-gate erano stati scritti con
timestamp ISO-8601 **esteso** (`2026-06-26T18:00:00Z-pass.log`) perche'
`release-validation-gate.md` documentava `<timestamp>` con un esempio che conteneva i
due punti. Un collega su Windows non riusciva a clonare il repo.

### Regole verificate

| # | Regola | Perche' |
|---|---|---|
| 1 | nessun carattere fra `< > : " \| ? *` e nessun carattere di controllo | vietati nei nomi file su Windows (`:` e' il separatore di unita') |
| 2 | nessun nome riservato DOS: `CON`, `PRN`, `AUX`, `NUL`, `CLOCK$`, `COM1`-`COM9`, `LPT1`-`LPT9` | Windows li interpreta come device, non come file |
| 3 | nessun segmento con spazio o punto finale | Windows li tronca silenziosamente |
| 4 | nessuna collisione case-insensitive fra due path | Windows non puo' tenere entrambi i file |
| 5 | nessuna collisione dopo normalizzazione NFC | macOS scrive NFD, Windows si aspetta NFC |
| 6 | nessun path oltre 200 caratteri | `MAX_PATH` = 260 contando il prefisso del clone |
