---
description: Scrive la documentazione funzionale di un servizio (manuale cliente e/o guida utente) dalla wiki, seguendo il protocollo con fonti e lacune dichiarate, poi la rende in HTML e Word. Le bozze restano in stato bozza fino all'approvazione umana.
argument-hint: "<servizio> --pubblico=cliente|utente|entrambi [--solo-render]"
---

# /doc-funzionale — Documentazione funzionale di un servizio

Argomenti utente: `$ARGUMENTS`

Esegue la skill `functional-docs-protocol` (`.claude/skills/functional-docs-protocol.md`):
leggila prima di procedere. La scrittura la fa la sessione principale, non un sotto-agente.

Gate: se `documentation.enabled` è `false` in `factory.config.yaml` (default di questa factory) non scrivere nulla e non lanciare il render: lo script `build_functional_docs.py` stampa un messaggio ed esce con codice 0, non è un errore. Riportalo all'utente e indica come attivare la capability (`documentation.enabled: true`).

## Argomenti

| Argomento | Effetto |
|---|---|
| `<servizio>` | chiave del servizio (es. `servizio-esempio`) |
| `--pubblico=cliente` | solo `manuale-cliente.md` |
| `--pubblico=utente` | solo `guida-utente.md` |
| `--pubblico=entrambi` | entrambi i documenti |
| `--solo-render` | salta la scrittura: rende i `.md` già presenti |

Senza `<servizio>` mostra l'elenco dei servizi e chiedi quale. Senza `--pubblico` chiedi
quale pubblico (default proposto: `entrambi`).

## Elenco dei servizi

1. Chiavi di `factory.config.yaml → documentation.functional_docs.services` (con `title`).
2. Se il catalogo è vuoto: i file di `wiki/user-flows/*.md` tranne `index.md`; la chiave è il nome file senza estensione.

Se la chiave non è in nessuno dei due elenchi, fermati e riporta l'elenco valido.

## Procedura

1. Con `--solo-render` vai al punto 4.
2. Fase A del protocollo: raccogli le fonti (pagina `user-flows`, wikilink, ricerca fts5) e
   scrivi l'elenco esplicito delle fonti usate.
3. Fasi B e C: scrivi i documenti richiesti in
   `deliverables/doc-funzionale/<servizio>/` sui template di
   `.claude/skills/references/functional-docs/`, con «Fonti:» in ogni sezione, «Lacune» per
   ciò che manca, conflitti dichiarati, stato `bozza`. Non toccare `stato`, `approvata_da`,
   `approvata_il` di documenti già presenti.
4. Fase D, dalla radice della factory:

   ```bash
   python3 tools/docs/build_functional_docs.py <servizio>
   ```

   Exit 2 = redazione fallita: riporta i finding così come sono e non aggirare il controllo.
5. Riporta in chat: file scritti, fonti usate, lacune e conflitti principali, e ricorda che
   la revisione umana è richiesta prima di consegnare (stato `approvata` solo a mano).

## Esempi

```bash
/doc-funzionale servizio-esempio --pubblico=entrambi
/doc-funzionale altro-servizio --pubblico=utente
/doc-funzionale servizio-esempio --solo-render
```

## Fonti nelle guide per gli utenti finali

Le righe «Fonti:» e la sezione «Fonti» restano nel markdown e nel render finché il documento è
`bozza`, così chi revisiona controlla ogni affermazione. Quando una guida con `pubblico: utente`
passa ad `approvata`, il render HTML e Word le toglie; il markdown resta invariato. Il manuale
per il cliente le mantiene sempre.
