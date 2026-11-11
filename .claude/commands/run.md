---
description: Mostra dashboard di stato e suggerisce il prossimo agente.
---

## Step 0 — Preflight kanban (EP-064 US-266, opt-in, no-op a flag spento)

**Prima** di invocare l'orchestrator, esegui il blocco qui sotto **una volta** ed emetti il
suo output (2 righe) sopra il dashboard. È l'innesto dell'osservatore kanban on-demand
(`tools/kanban-observer/kanban-observe.py`, TSK-635) in un'azione che l'utente compie
comunque: la capability **eredita l'attivazione da `/run`** invece di richiedere che
qualcuno si ricordi di lanciarla. `/run` è il punto di innesto **unico** — la duplicazione
del segnale in più ospiti è rumore, e un segnale visto due volte si impara a ignorare.

```bash
python3 - <<'PY' 2>/dev/null || true
import json, pathlib, re, subprocess, sys
try:
    root = pathlib.Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                       capture_output=True, text=True).stdout.strip() or ".")
    cfg = (root / "factory.config.yaml").read_text(encoding="utf-8")
    blk = re.search(r"^kanban_coordination:[^\n]*\n((?:[ \t]+[^\n]*\n|[ \t]*\n)*)", cfg, re.M)
    if not blk or not re.search(r"^\s+enabled:\s*true\b", blk.group(1), re.M):
        sys.exit(0)                      # flag assente o off -> no-op silenzioso
    tool = root / "tools/kanban-observer/kanban-observe.py"
    if not tool.is_file():
        sys.exit(0)                      # capability non installata -> no-op
    out = subprocess.run([sys.executable, str(tool), "--json", "--no-fetch", str(root)],
                         capture_output=True, text=True, timeout=20).stdout
    d = json.loads(out)
    mio = d.get("tuo_silenzio") or {}
    nc, cnp = len(mio.get("non_committato") or []), len(mio.get("committato_non_pushato") or [])
    n = len(d.get("dagli_altri") or [])
    # fetch saltato + lista vuota => NESSUNA INFORMAZIONE sul remoto, non «nessun
    # problema» (kanban-coordination-protocol §Fase 1 «Cosa fare con questi numeri», R.KC7). Mai renderizzare "0".
    altri = ("nessuna informazione (fetch non eseguito)" if n == 0 else
             f"almeno {n} {'transizione' if n == 1 else 'transizioni'} all'ultimo fetch")
    if not d.get("upstream"):
        print(f"◉ KANBAN  nessun upstream: non c'e' un remoto da osservare  ·  "
              f"il tuo silenzio: {cnp} commit + {nc} file non pushati")
        sys.exit(0)
    eta = (d.get("staleness") or {}).get("eta", "sconosciuta")
    silenzio = (f"{cnp} commit + {nc} file non pushati" if (cnp or nc)
                else "niente — quello che hai fatto e' visibile a tutti")
    print(f"◉ KANBAN  il tuo silenzio: {silenzio}  ·  dagli altri: {altri}")
    print(f"          stato all'ultimo push · dato di {eta} · qui non si interroga "
          "il remoto → `/kanban-status` lo fa")
except Exception:
    pass                                 # fail-open: l'ospite non fallisce mai per l'osservatore
PY
```

Output tipico (flag attivo, lavoro locale non pushato):

```
◉ KANBAN  il tuo silenzio: 4 commit + 1 file non pushati  ·  dagli altri: nessuna informazione (fetch non eseguito)
          stato all'ultimo push · dato di 20 h 33 min · qui non si interroga il remoto → `/kanban-status` lo fa
```

**Contratto dell'innesto** (non negoziabile):

- **Nessun processo persistente.** Nessun demone, cron, watcher o hook: il blocco gira una
  volta per invocazione di `/run` e termina. Il watcher continuo è la forma **uccisa** da
  TR-7d2a9f14 per *activation gap* (US-266 AC1); reintrodurla qui sarebbe un errore di
  decomposizione.
- **Fail-open verso l'ospite.** Flag assente/off, tool mancante, JSON malformato, repo senza
  `.git`, `python3` assente: il blocco esce **0 e silenzioso**, e `/run` prosegue identico.
  Il `2>/dev/null || true` e il `try/except` sono parte del contratto, non difensivismo.
- **`--no-fetch` obbligatorio in questo innesto.** `/run` è il comando più lanciato: un
  `git fetch` costa ~2 s con rete buona e fino a 60 s (timeout dell'osservatore) con remote
  irraggiungibile o prompt di autenticazione. Con `--no-fetch` il costo è deterministico
  (~0,7 s) e non c'è I/O di rete nel percorso dell'ospite. Ma la ragione dirimente non è la
  latenza: **la metà che conta non ha bisogno della rete.** «Il tuo silenzio» si calcola da
  `git status` e `@{u}..HEAD`, cioè da stato locale, ed è quindi **esatto anche senza fetch**.
  Il fetch serve solo alla metà meno urgente (cosa hanno fatto gli altri), e quella resta
  all'invocazione esplicita di `/kanban-status`.
- **Read-only.** L'osservatore è invocato con `--json --no-fetch`: nessun `push`, nessun
  `pull`, nessuna scrittura in `management/kanban/` (US-266 AC4, §7 r.14).
- **Onestà sulla staleness.** La seconda riga è **non comprimibile**: dichiara sempre
  «stato all'ultimo push», l'età del dato e che il remoto non è stato interrogato. Un segnale
  compatto che tace la propria età reintrodurrebbe il board «bugiardamente fresco».
- **`0` non si stampa mai per «dagli altri».** Senza fetch, una lista vuota di transizioni
  altrui significa **nessuna informazione**, non «nessun problema»: renderla come `0` sarebbe
  una bugia per omissione, ed è la lettura che `kanban-coordination-protocol` §Fase 1 «Cosa fare con questi numeri» (R.KC7)
  vieta esplicitamente. Perciò il ramo `n == 0` stampa «nessuna informazione (fetch non
  eseguito)», e `n > 0` stampa «almeno N», che è un limite inferiore onesto.
- **La metà che conta prima.** Nel contesto di un ospite si mostra per primo *il tuo
  silenzio* (commit e file che gli altri non vedono): è il dato che previene la collisione,
  perché rende visibile all'autore ciò che sta nascondendo senza saperlo. Il box completo
  (elenco per-TSK delle transizioni altrui) resta a `/kanban-status`.
- **Gating.** Attivo solo con `kanban_coordination.enabled: true` in `factory.config.yaml`.
  Il blocco **si auto-gattiga**: verifica il flag da sé, quindi resta un no-op anche se
  eseguito per errore a capability spenta. A flag assente o `false` la factory si comporta
  esattamente come prima di EP-064.

[^src: management/kanban/EP-064-kanban-multi-user-coordination/US-266-osservatore-on-demand/TSK-636.md]

---

## Step 0-bis — Costi in token (cost-alert, no-op a flag spento)

Subito dopo lo Step 0, esegui una volta ed emetti la riga sopra il dashboard:

```bash
python3 tools/analytics/cost_alert.py check --period daily --compact 2>/dev/null || true
```

Una riga con la regola giornaliera, gli alert pendenti dell'operatore e il numero di note
(dettaglio con `/cost-alert`). Stesso contratto dello Step 0: sola lettura, nessun agente,
nessuna rete, silenzioso con `analytics.cost_alert.enabled` spento, mai bloccante. Le
escalation si gestiscono a `/session-close` o con `/cost-alert`, non da qui.

---

## Dashboard

Invoca l'agente `orchestrator` via `Agent`. Passa eventuale argomento come "focus"
(es. `/run l3` per focus L3). L'orchestrator:

1. Scansiona lo stato del filesystem per i 4 layer.
2. Legge l'ultima entry di `memory/episodic/` per continuità.
3. Emette un dashboard tabellare.
4. Suggerisce il prossimo agente da invocare (mai delega automatica).
5. Append a `memory/episodic/<YYYY-MM-DD-HH-MM>-run.md`.
