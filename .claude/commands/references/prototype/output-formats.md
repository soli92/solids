# output-formats.md — /prototype: formati di output

**Ambito**: questa foglia contiene i blocchi di display usati dal comando `/prototype`
per comunicare risultati in chat. Copre tre sezioni distinte:
(1) display dry-run — Fase `--dry-run`, nessun artefatto generato;
(2) output finale — esiti positivo / degrado / STOP dopo completamento agente;
(3) suggerimenti handoff — tabella dei comandi downstream da emettere in Fase 4.

Questa foglia e' referenziata da trigger vincolanti hard-fail in Step 4 e Step 6
del corpo del comando: se manca, il comando si interrompe con STOP esplicito.

[^src: .claude/commands/prototype.md Step 4 §Dry-run display + Step 6 §Output finale + §Suggerimenti handoff]

---

## §Dry-run display

Dopo aver invocato la skill `backend-resolver` in modalita' dry-run (Step 4, punto 3),
mostra il seguente display **senza generare artefatti** e termina senza invocare l'agente:

```
[/prototype --dry-run] Risoluzione backend per: <input_ref>
============================================================
Backend configurato: <prototyping.backend>
Fallback chain:      <fallback_chain>
Degrade policy:      <degrade_policy>

RISOLUZIONE DRY-RUN (nessun artefatto generato)
<BACKEND_RESOLVED | BACKEND_DEGRADED | BACKEND_UNAVAILABLE_STRICT>: <dettaglio>
Backend che verrebbe selezionato: <selected_backend>

Per generare il prototipo: /prototype <input_ref> [stessi flag senza --dry-run]
Per lo snapshot globale del layer: /prototype-status
```

---

## §Output finale

Dopo il completamento dell'agente (Step 6), riporta uno dei tre esiti in chat.

**Esito positivo**:

```
/prototype <input_ref> — completato
=====================================
Fase 0 — Backend:    <BACKEND_RESOLVED | BACKEND_DEGRADED>: <selected_backend>
Fase 1 — Source:     <spec_source | "intent only"> / art-director: <on|off>
Fase 2 — Generate:   <backend>-mapping invocata → <marker-mapping>
Fase 3 — Check:      PROTOTYPE_GENERATED: <output_ref>
Fase 4 — Handoff:    log entry scritto · suggerimenti: <N>

Artefatto: <output_ref>
```

**Esito con degrado backend** (marker `BACKEND_DEGRADED`):

Include il riepilogo positivo + nota di degrado:

```
Nota: backend degradato <preferito>→<selezionato> (<motivo>).
      Per ripristinare <preferito>: <remediation da backend-resolver>.
```

**Esito con STOP** (gate umano o errore):

```
/prototype <input_ref> — STOP
==============================
Fase <N> — <motivo del blocco>
Azione richiesta: <descrizione azione umana>
```

---

## §Suggerimenti handoff

I suggerimenti downstream sono emessi dall'agente in Fase 4 e dipendono dal backend
risolto e dai flag abilitati in `factory.config.yaml`. Vengono soppressi silenziosamente
se il comando corrispondente non e' installato o il flag e' `false`:

| Backend | Suggerimenti candidati |
|---|---|
| `html` | `/visual-oracle` · `/functional-oracle` (se stati interattivi) · `/ux-ui-review` · `/a11y` |
| `react` | `/visual-oracle` · `/functional-oracle` · `/review` (CQRL se abilitato) · `/a11y` |
| `figma` | `/ux-ui-review` · round-trip `/figma-sync` · revisione manuale nel file Figma |
| `penpot` | `/ux-ui-review` · revisione manuale nel file Penpot |
