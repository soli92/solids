---
name: repo-handover-protocol
description: "Travaso di un albero di codice da un repo sorgente (a SHA immutabile) a un repo target senza trasferire history. Gate fail-closed G1-G4 sequenziali. Push e merge sempre gate umani (§7 r.14). Registro di provenienza obbligatorio nel commit di import. Nessuna scrittura nel repo sorgente."
status: active
pattern_version: "2.44"
---

# Skill — `repo-handover-protocol` (travaso sorgente → target senza history)

Governa il **travaso** di un albero di codice da un repo sorgente a un repo target,
quando i due hanno history non correlata e si vuole che il target riceva il codice
come commit di import pulito (nessuna history trasferita, nessun merge-base condiviso).

> **Reuse-first — cosa questa skill NON fa.**
> La migrazione di componenti, il porting da una versione a un'altra, la verifica di
> parità funzionale, e la pubblicazione su feed/registry non rientrano in questo
> protocollo. Questa skill inizia dopo che il sorgente è già in uno stato valido e
> pronto per il travaso.

---

## Nota di gating (opt-in, default off)

Verificare il flag in `factory.config.yaml`:

```yaml
repo_handover:
  enabled: true   # default: false
```

Se `repo_handover.enabled` è `false` o assente: **fallback esplicito** — segnalare
in chat che la capability è spenta (`repo_handover.enabled: false`). La skill non
avanza e non modifica nulla. Questo flag non va modificato da questa skill.

> Per il blocco di config completo (con tutti i campi disponibili) vedi il file
> `.claude/skills/references/repo-handover-protocol/config-block.md`.

---

## Principio di design — fail-closed

**Nessuna fase avanza su un'assunzione rotta.** Gate G1–G4 **sequenziali e dipendenti**:
non si esegue Gn+1 se Gn non è verde. Ogni verifica si basa su **evidenza effettiva
sul tree o sul repo** (comandi git, asserzioni su file, diff), mai su messaggi di
commit o documentazione pregressa.

---

## Parametri

| Parametro | Significato |
|---|---|
| `source_repo` | Path assoluto al repo sorgente (read-only durante il travaso) |
| `source_sha` | SHA del commit sorgente — deve essere immutabile (tag o commit già condiviso) |
| `target_repo` | Path assoluto al repo target (deve esistere, può essere vuoto o scaffoldato) |
| `target_branch` | Branch di arrivo nel target (deve essere dichiarato, mai implicito) |
| `include_paths` | Lista di path relativi da includere nel travaso (default: tutto l'albero) |
| `exclude_patterns` | Lista di pattern `.gitignore`-style da escludere (default: vuoto) |
| `registry_note` | Stringa libera per il registro di provenienza nel commit di import |

---

## I 4 gate — sequenza fail-closed

```
G1  Preflight                           → sorgente a SHA immutabile, target pulito,
  │                                       branch di arrivo dichiarato e verificabile
G2  Selezione dell'albero               → include/exclude applicati, perimetro
  │                                       confermato (lista file) — gate umano G1
G3  Import nel target (gate worktree)   → git archive + estrazione, nessuna history
  │                                       portata, registro di provenienza nel commit,
  │                                       gate locali via worktree-gate se configurati
G4  Conferma push / apertura PR         → mai push automatico (§7 r.14); gate umano
```

---

### G1 — Preflight

**Obiettivo:** verificare che le precondizioni del travaso siano tutte soddisfatte
prima di toccare qualsiasi file.

Checklist:

**(a) SHA immutabile nel sorgente.** Il SHA dichiarato deve esistere nel repo sorgente
e non deve coincidere con HEAD se HEAD è su un branch attivo (rischio di avanzamento
involontario). Comando di verifica:
```bash
git -C "$source_repo" cat-file -t "$source_sha"   # deve stampare "commit"
```

**(b) Target pulito.** Il working tree del target non deve avere modifiche non
committate. Comando di verifica:
```bash
git -C "$target_repo" status --porcelain   # deve essere vuoto
```

**(c) Branch di arrivo dichiarato.** `target_branch` deve essere valorizzato.
Se il branch non esiste ancora nel target, deve essere creato **prima** di procedere.
```bash
git -C "$target_repo" checkout -b "$target_branch" 2>/dev/null || \
git -C "$target_repo" checkout "$target_branch"
```

**(d) Sorgente non modificato.** Il repo sorgente non viene mai toccato da questa
skill. Verificare che il proprio working dir non sia nel sorgente prima di procedere.

**Oracolo G1:** tutti i punti (a)–(d) verdi → G1 PASS. Qualsiasi punto rosso → STOP.

---

### G2 — Selezione dell'albero

**Obiettivo:** determinare il perimetro esatto dei file che entreranno nel target.

1. Applicare `include_paths` e `exclude_patterns` per calcolare la lista finale.
2. Presentare la lista all'utente (conteggio + campione top-20).
3. **Gate umano G2**: l'utente conferma il perimetro prima di procedere al travaso.

Comandi di verifica del perimetro (modalità dry-run):
```bash
python3 tools/vcs/repo_handover.py \
  --source "$source_repo" --sha "$source_sha" \
  --target "$target_repo" \
  --dry-run
```

Il dry-run elenca i file senza scrivere nel target (§7 r.14).

---

### G3 — Import nel target

**Obiettivo:** portare il codice del sorgente nel target come **commit di import**,
senza trasferire history né creare merge-base.

Passi chiave:

**(3a)** Il target rimane la base — lo scaffold preesistente non viene toccato.

**(3b)** Export via `git archive` (non `cp -r` né `rsync`):
```bash
git -C "$source_repo" archive "$source_sha" \
    --prefix="" \
    -- $include_paths \
    | tar -x -C "$target_repo"
```
I file esclusi da `exclude_patterns` vengono rimossi dopo l'estrazione.

**(3c)** Il messaggio di commit di import include il **registro di provenienza**:
```
chore: import da <source_repo_slug>@<source_sha_short>

Sorgente: <source_repo_path>
SHA: <source_sha>
Data: <YYYY-MM-DD>
<registry_note se presente>
```

**(3d)** Se il target ha `ai_attribution_policy.suppress_ai_traces: true` in
`factory.config.yaml`, il commit usa `tools/vcs/sm_commit.py` con i filtri
§ai_policy, mai un `git commit` diretto.

**(3e)** Gate locali (opzionale): se configurati in `repo_handover.local_gates[]`,
eseguiti via `worktree-gate` sul commit di import prima della conferma push.

**(3f)** Nessun commit con date o autori artificiali. L'autore è l'identità git
attiva nel target al momento dell'import.

---

### G4 — Conferma push / apertura PR

**Obiettivo:** rendere il codice visibile nel remote del target, **mai in automatico**.

1. Presentare il diff di riepilogo (`git log --oneline origin/$target_branch..HEAD`
   nel target).
2. **Gate umano G4**: l'utente decide se fare push diretto, aprire una PR, o
   mantenere il lavoro in locale.

```
STOP — §7 r.14: nessuna operazione VCS outward automatica.
Il push e l'apertura di PR sono sempre espliciti e confermati dall'utente.
```

---

## Contratto di sequenziamento

| Da → A | Precondizione | Se non soddisfatta |
|---|---|---|
| — → G1 | SHA dichiarato, target path esiste | STOP — verificare i parametri |
| G1 → G2 | Tutti i punti (a)–(d) verdi | STOP — fix nel sorgente/target, poi G1 di nuovo |
| G2 → G3 | Perimetro confermato da gate umano | STOP — non si procede senza conferma esplicita |
| G3 → G4 | Commit di import creato; gate locali PASS se configurati | STOP — irrisolvibile in autonomia se gate locali falliscono |
| G4 | Push/PR confermato da gate umano | Lavoro rimane in locale fino a conferma |

---

## §ai_policy

- **Commit nel target con `suppress_ai_traces: true`**: usare `tools/vcs/sm_commit.py`
  con i filtri §ai_policy. Mai `git commit` diretto in questo caso.
- **Nessuna operazione VCS automatica distruttiva** (§7 r.14): push e PR sono sempre
  gate umani.
- **Nessuna scrittura nel repo sorgente**: la skill è read-only verso il sorgente
  in ogni fase.

---

## Reuse-first — cosa il protocollo NON fa

- **Non migra** componenti: fuori scope.
- **Non verifica la completezza** del target rispetto al sorgente: il travaso è snapshot.
- **Non genera test**: fuori scope.
- **Non pubblica** su feed o registry: fuori scope.
- **Non tocca `factory.config.yaml`, `PATTERN.md` o `CLAUDE.md`** (§7 r.13).
- **Non modifica mai il repo sorgente** in nessuna fase.
