# Catalogo dei valori del caso peggiore

Valori realistici che rompono una UI, raggruppati per tipo di dato renderizzato. Si usano le righe che
corrispondono ai campi della mappa (fase 1 di `kowalski-worst-case-data`). Adattato da `CATALOG.md` di
`break-ui` (emilkowalski/skills, MIT). Ogni valore è ottenibile da un utente reale; la nota dice cosa tende a
rompere. Email e URL usano solo domini `.example` o `.test`. Tutti i nomi sono inventati.

## Persone e nomi

| Valore | Cosa rompe |
|---|---|
| `Maria Grazia D'Alessandro-Wiśniewska` | Lungo, doppio cognome con trattino e apostrofo; va a capo e il trattino è un punto di a-capo |
| `Giovanni Battista Montefalcone di San Severino` | Particelle minuscole e cognome lungo; iniziali `GM` o `GS`, ordinamento per cognome |
| `Niccolò De Vecchi-Bartolomeo III` | Suffisso; iniziali ingenue `NI` |
| `Jo` | Due lettere; colonna quasi vuota, iniziali ingenue `J` |
| `A` | Una lettera; iniziale singola, bersaglio di click minuscolo se il nome è il link |
| `Ólafur Darri Ólafsson` | Maiuscola accentata iniziale; logica uppercase/ordinamento, iniziali `ÓÓ` |
| `Đặng Thị Ngọc Hân` | Diacritici vietnamiti impilati; tagliati da `line-height` stretto con `overflow: hidden` |
| `王秀英` | CJK senza spazi; «prima + ultima parola» trova una parola sola, l'a-capo avviene ovunque |
| `نور الهدى عبد الرحمن` | RTL; punteggiatura e icone dal lato sbagliato senza `dir="auto"` |
| `Seán Ó Súilleabháin` | Accenti e apostrofi; escape, iniziali, ricerca |
| `Cesare Pavese e Lucia dell'Arco` | Due persone in un campo; separatori e apostrofo tipografico `’` |
| `dana` | Tutto minuscolo; le iniziali devono comunque essere maiuscole |
| `🦊 Volpe` | Emoji in testa; `.charAt(0)` restituisce metà coppia surrogata |
| `👩🏽‍💻 Priya` | Sequenza ZWJ; `.length` oltre 7, lo slicing la spezza |
| `  Sam   Lee ` | Spazi iniziali, finali, ripetuti; iniziali da parole vuote |
| *(mancante)* | Nessun nome, solo l'email: la UI deve ripiegare su qualcosa |

## Email, URL, identificativi

Stringhe senza spazi: il browser non ha dove andare a capo.

| Valore | Cosa rompe |
|---|---|
| `bartolomeo.fitzgerald@industrie-meccaniche-riunite-holding.example` | Il classico: spinge via ogni elemento di riga senza `overflow-wrap: anywhere` |
| `amministrazione.contabilita@studio-associato-rossi-bianchi-e-verdi.pec.example` | PEC lunga: dominio con più segmenti, troncamento che nasconde il dominio |
| `a@b.test` | Il più corto realistico; layout pensato per l'email lunga sembra vuoto |
| `nome.cognome+fatture-notifiche@example.org` | Plus-addressing; validazione che rifiuta `+`, troncamento che nasconde la parte significativa |
| `ops@sub.reparto.regione.example.co.uk` | Molti sottodomini, TLD in due parti; estrazione del «dominio» |
| `https://example.com/aree/nord/progetti/lancio-trimestre/documenti/9f8e7d6c5b4a?scheda=commenti&filtro=aperti` | URL lungo; overflow, il troncamento in coda nasconde la parte che differisce |
| `9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f` | UUID; larghezza monospace, candidato al troncamento al centro |
| `RSSMRA80A01H501U` | Codice fiscale (16 caratteri, tutto maiuscolo, senza spazi): colonne strette, copia, maiuscole |
| `IT60X0542811101000000123456` | IBAN italiano (27 caratteri): senza spazi non va a capo; raggruppato a blocchi di 4 va formattato |
| `Verbale CdA — DEFINITIVO (rev. 2) v12 [approvato dal legale].pdf` | Nome file; la coda tronca versione ed estensione, parentesi e trattini nei percorsi |
| `IMG_20251014_183022_HDR_ritratto_modificato_modificato.HEIC` | Nome da fotocamera; senza spazi, estensione maiuscola |
| `@a` / `@un_nome_utente_lunghissimo_ma_consentito` | Estremi degli handle |

## Etichette, titoli e testi da dati

| Valore | Cosa rompe |
|---|---|
| `Responsabile Senior Sviluppo Prodotto, Infrastrutture di Piattaforma` | Qualifica lunga; tre righe in uno slot secondario |
| `Invito scaduto da 12 giorni` | Badge di stato lungo; va a capo o schiaccia la colonna del nome |
| `Benachrichtigungseinstellungen` | Composto tedesco (30 caratteri, senza spazi); etichetta in overflow |
| `Impostazioni di riservatezza e di sicurezza dell'account` | Espansione italiana di «Privacy e sicurezza»; i testi tradotti crescono del 30% |
| Dodici tag su un elemento: `design`, `frontend`, `urgente`, `da-rivedere`, … | Riga di tag che diventa un muro; serve un `+8` |
| Un tag `feedback-clienti-da-onboarding-enterprise` | Un tag più largo del suo contenitore |
| `Senza titolo` / stringa vuota / `   ` | Titolo mancante: intestazione collassata, riga a altezza zero |
| `<script>alert(1)</script>` / `&amp;` / `**grassetto**` | Escape: va mostrato come testo letterale |
| `Riga uno` + a capo + `Riga due` | A capo in un campo a riga singola: raddoppia l'altezza o sparisce |
| Descrizione incollata da 2.000 caratteri | Clamp, «mostra tutto», crescita della textarea |

## Numeri e importi

| Valore | Cosa rompe |
|---|---|
| `0` | Stati zero: «0 membri», barra vuota, divisione per zero nelle percentuali |
| `1` | Plurali: «1 membri», «1 giorni fa» |
| `1284` | Serve il separatore delle migliaia: `1.284` in `it-IT` |
| `1000000` | Larghezza del badge del conteggio; forma compatta dove la precisione non serve |
| `12345678,9` come valuta | `12.345.678,90 €`; sfora le colonne dei totali |
| `-42,5` | Segno, logica del colore rosso, parentesi nei formati contabili |
| `0,1 + 0,2` | `0.30000000000000004` mostrato grezzo |
| `142%` / `-3%` | Barre di avanzamento oltre i limiti |
| `null` / `undefined` / `NaN` | Renderizzati letteralmente |
| `1.284` in `it-IT` contro `1,284` in `en-US` | Formattazione per locale: separatori cablati sbagliati per mezzo mondo |
| Valore che cambia dal vivo (`99` → `100`) | Salto di larghezza e sfarfallio senza `tabular-nums` |

## Collezioni

| Valore | Cosa rompe |
|---|---|
| 0 elementi | Lo stato vuoto, e se esiste |
| 1 elemento | Griglie che sembrano rotte con una sola card; «1 di 1» |
| Esattamente la dimensione di pagina, e pagina + 1 | Off-by-one in «Mostrati 40 di 40», pagina 2 vuota |
| Oltre 1.000 elementi non paginati | Prestazioni di scroll, tempo di render, memoria; testo «Mostrati 40 di 1.284» |
| Un elemento 10 volte più grande degli altri | Righe di griglia che si allungano sul più alto |
| Elementi con lo stesso nome | Liste in cui il nome è l'unico campo distintivo |

## Tempo

| Valore | Cosa rompe |
|---|---|
| Adesso | «0 secondi fa» invece di «adesso» |
| 12 giorni fa, 11 mesi fa, 3 anni fa | Soglie del tempo relativo; dopo circa una settimana serve una data assoluta |
| Una data futura | «tra 3 giorni» contro «-3 giorni fa» |
| `1970-01-01` | Timestamp zero mostrato come data vera |
| `2025-12-31T23:30:00-08:00` | Giorno diverso in UTC e nel fuso dell'utente; il cambio ora legale a fine marzo e ottobre |
| Durata molto lunga (`1.284 ore`) | Formattazione che non passa mai ai giorni |

Si usano `Intl.RelativeTimeFormat` e `Intl.DateTimeFormat`, non stringhe costruite a mano.

## Immagini e media

| Valore | Cosa rompe |
|---|---|
| URL avatar che dà 404 | Icona di immagine rotta al posto delle iniziali |
| Nessun avatar | Il fallback stesso: iniziali, colore, parità di dimensione con gli avatar veri |
| Panorama 4000×200 come avatar o copertina | Deformazione senza `object-fit: cover` |
| Immagine alta 200×4000 | Idem sull'altro asse; può far esplodere l'altezza della card |
| Logo PNG trasparente, logo scuro in tema scuro | Invisibile sullo sfondo |
| Immagine lenta | Spostamento del layout senza dimensioni fisse o `aspect-ratio` |

## Stati

| Valore | Cosa rompe |
|---|---|
| Caricamento | Skeleton diversi dal layout finale, spinner che spostano il contenuto |
| Errore dall'API | Nessuno stato di errore, o messaggio grezzo (`TypeError: Cannot read properties of undefined`) |
| Dati parziali | Alcuni opzionali compilati e altri no nella stessa lista; righe disallineate |
| Tutti gli stati insieme | Ogni valore dell'enum in una lista (`attivo`, `invitato`, `scaduto`, `sospeso`); larghezze di badge diverse |
| Nessun permesso | Azioni disabilitate: la riga ha lo stesso layout? |
| L'utente corrente nella lista | Etichette «Tu», azioni che non valgono per sé stessi |

## Ambiente

Non sono dati, ma si controllano allo stesso modo: si passa al caso peggiore, poi si cambia questo.

| Condizione | Cosa rompe |
|---|---|
| Contenitore a 320 px | Ogni overflow di cui sopra, insieme |
| Sidebar stretta | Componenti disegnati a larghezza piena e riusati in una colonna da 280 px |
| 2560 px di larghezza | Righe troppo lunghe da leggere, contenuto isolato su un lato |
| Zoom 200% / testo grande | Altezze fisse che tagliano il testo che cresce |
| Tema scuro | Colori cablati, bordi e loghi invisibili |
| `dir="rtl"` | Icone, chevron, padding e ordine delle azioni finali |
| Dispositivo touch | Azioni solo-hover (il menu `•••` che compare al passaggio) irraggiungibili |
