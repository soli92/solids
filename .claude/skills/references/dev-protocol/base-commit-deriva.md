# Deriva dal `base_commit` — verifica all'avvio dell'esecuzione

**Ambito**: dettaglio del controllo di Fase 0 (step 5) di `dev-protocol.md`. Si applica solo se il
frontmatter del TSK ha `base_commit:`. Campo assente = questo file non si legge e nulla cambia
(il campo stesso e' l'opt-in; nessun flag in `factory.config.yaml`).

## Cos'e' `base_commit`

SHA corto (esadecimale, 7-40 caratteri) del **repo del `code_path`** su cui il TSK e' stato scritto.
Con un `code_path` esterno e' lo SHA di quel repo, non della factory. Lo scrive chi crea il TSK
(`scrivi-task`) quando il TSK cita codice esistente (`file:riga` o estratti); altrimenti e' omesso.
Serve a una cosa: capire se le righe e gli estratti citati sono ancora quelli che l'autore ha visto.

## Procedura

1. Risolvi `<code_path>` (target resolution, step 2-bis). Per ogni file citato dal TSK
   (`file:riga` negli Implementation Steps / Technical Specs; `target:` e `code_path:`):
   ```bash
   git -C <code_path> cat-file -e <base_commit>^{commit}
   git -C <code_path> diff --name-only <base_commit>..HEAD -- <file target...>
   ```
2. **SHA inesistente** (il primo comando fallisce): dichiaralo come tale, non come deriva. E' un'
   **ipotesi** finche' non cita comando ed esito (protocollo di chiusura di `dev-handoff`). Ti fermi
   con `status: blocked` e un handoff «base_commit non risolvibile nel repo <code_path>»: comando,
   esito, e cosa serve (SHA corretto o clone completo). Non procedere «a occhio».
3. **Nessun file cambiato** (output vuoto): il codice citato e' quello visto dall'autore. Procedi.
4. **File cambiati**: non e' ancora un blocco. Confronta, per ogni estratto o riga citata, quanto il
   TSK dichiara con il file attuale.
   - Corrispondono (le modifiche hanno toccato altre parti del file): procedi e annota nell'handoff
     quali file erano cambiati e che gli estratti sono stati verificati.
   - **Non corrispondono**: FERMATI. Non adattare il passo, non indovinare l'intento. Edit
     `status: blocked` (e `updated:`) e handoff «deriva dal base_commit» con, per ogni passo
     fermato: **file**, **estratto atteso** (dal TSK), **trovato** (dal file attuale) e il
     comando che lo prova. Il TPM riscrive il passo e aggiorna `base_commit`.

## Limiti

- Il controllo e' sui file e sugli estratti citati: non garantisce che altro codice, non citato, non
  sia cambiato.
- Non sostituisce il gate di Fase 0: e' un'ulteriore condizione di stop, solo con il campo presente.
