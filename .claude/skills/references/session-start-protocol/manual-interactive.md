# session-start-protocol — prompt della modalita' `manual`

Ambito: prompt e comandi eseguiti **solo** in `manual` (Fase 1.1, 1.2, 1.3, 1.4, 1.5,
4.2, 4.3). In `--quick`/`--auto` queste fasi sono SKIP o risolte col default
conservativo del core. Comandi di shell secondo `.claude/skills/shell-portability.md`.

## 1.1 — Working tree non pulito

```
[SESSION-START Fase 1 — working tree non pulito]
File modificati: <max 10 righe di git status --short>
  [s] stash delle modifiche locali
  [c] continua (le modifiche restano)
  [a] interrompi
Risposta [s/c/a]:
```
Risposta non valida: ripropone una volta, poi `a` con avviso.

## 1.2 — Pull della factory

```bash
git -C <factory_root> pull --ff-only
```
Merge conflict, rete o autenticazione → STOP con il comando di diagnosi
(`git -C <factory_root> status`). Mai `--force`, mai `reset`.

## 1.3 — Divergenza oltre soglia

```
[divergenza] il pull ha introdotto N commit (soglia: <dispatch_gate_divergence_threshold>).
Confermi di proseguire? [si/no]:
```
`no` o nessuna risposta → STOP.

## 1.4 — Selezione dei submodule

Candidati: entry di `code_paths[]` con `vcs.mode: submodule` (path da
`vcs.submodule_path`, altrimenti `path`). Stato da `git -C <factory_root> submodule status`:
` ` in sync · `+` puntatore diverso · `-` non inizializzato · `U` conflitto.

```
[SESSION-START Fase 1 — selezione submodule]
  [1] <name>   <stato>   <N commit da origin/<base_branch>>
  ...
  [nessuno]  salta (lavoro solo sulla factory)
Quali allineo? [1 2 ... | nessuno] (invio = nessuno):
```
`base_branch` per target: `vcs.base_branch` della entry (default `main`), mai un
nome cablato. Su avvio caldo la domanda si ripropone comunque.

## 1.5 — Doctor e update, solo sui selezionati

```bash
python3 tools/vcs/sm_doctor.py --target <name>      # exit != 0: avviso, si continua
git -C <factory_root> submodule update --init --remote --merge <path>   # stato `-`
git -C <factory_root> submodule update --remote --merge <path>          # altri stati
git -C <factory_root>/<path> rev-parse --short HEAD                     # hash per il log
```
Senza `--init` su un submodule `-` il comando termina senza errori e senza fare nulla.
Errore di update → `[avviso] <name> non aggiornato: <motivo>`, si continua.

## 4.2 — Scope (se `--context` assente)

Fino a 4 opzioni dedotte dallo stato di Fase 3 + `[5] altro`. Invio vuoto → `scope: all`.
Massimo due tentativi.

## 4.3 — Focus (se TSK in corso + bloccati > 3)

```
Ci sono TSK su cui concentrarsi, o vuoi il prossimo consigliato? (invio per saltare)
```
