# Passata 7 — Revisione del motion (advisory) (dettaglio completo)

Ambito: dettaglio della Passata 7 (opt-in) di `code-review-protocol.md`. Leggere prima di eseguire
il pass. Condizionale: solo con `ui_craft.enabled: true` **e** `ui_craft.motion_review: true` in
`factory.config.yaml`, **e** se il diff tocca motion.

Pass aggiuntivo, advisory, additivo e non distruttivo: non sostituisce le passate 1-3, **non
produce un verdict**, non entra nelle regole di verdict dell'aggregator (Fase 3) e **non può
cambiare** il verdict calcolato dalle altre passate. Stesso trattamento della Passata 5. Le regole
del motion sono euristiche d'autore, non misure: mai un gate.

## Attivazione

```
IF ui_craft.enabled != true OR ui_craft.motion_review != true:
    SKIP   # default off (R.P3) — comportamento identico a prima
IF il diff (files_in_scope della Fase 0) non contiene motion:
    SKIP   # nessun finding, nessuna sezione
```

Euristica per «il diff tocca motion»: nelle righe aggiunte o modificate del diff, grep di
`transition`, `animation`, `@keyframes`, `motion.`, `animate=`, `useSpring`, `ease-`,
`transform-origin`, `prefers-reduced-motion`; nelle codebase Tailwind anche le classi `animate-`, `duration-`, `ease-`, `origin-`, `transition-`, `delay-` e `keyframes` nei file di config/preset. Basta una corrispondenza. È un'euristica di
attivazione, non di giudizio: un falso positivo costa una passata a vuoto.

## Procedura

La esegue il code-reviewer stesso, con la skill [`kowalski-motion-review`](../../kowalski-motion-review.md):
dieci standard, segnali d'allarme, ordine delle correzioni. Valori citati da
[`../kowalski-motion-review/standard.md`](../kowalski-motion-review/standard.md). **Non rilancia
`/review` e non avvia altri agenti.** Si esaminano solo le righe di motion del diff.

Quando la correzione vive in un file di config o preset (es. l'easing di default di un plugin di
animazione usato in N componenti), il finding è **uno**, ancorato al file di config, con l'elenco dei
punti d'uso: non N finding. Quando il rimedio della skill non è applicabile al vincolo della libreria
(es. altezza di un accordion che deve spingere il contenuto, uscita rilevata con `animationend`), la
colonna `Dopo` lo dice («nessuna correzione equivalente: …») invece di proporre un rimedio che rompe il
componente.

Ciò che non si giudica dal codice (sensazione di una spring o di un crossfade, gesti, reduced-motion
a runtime) non diventa finding: va nell'elenco «da verificare a vista» con il passo concreto.

## Uscita

Una sezione `### Pass 7 — Motion (advisory)` **dentro il report standard** (Fase 4), separata dalle
passate di qualità, nel formato della skill: tabella `Prima | Dopo | Perché` con `file:riga`,
raggruppata per impatto, più l'elenco «da verificare a vista». Nessun Block/Approve.

```markdown
### Pass 7 — Motion (advisory)
| Prima | Dopo | Perché |
|---|---|---|
| `Menu.css:17` `transform: scale(0)` | `transform: scale(0.95); opacity: 0` | `scale(0)` sembra uscire dal nulla |

**Da verificare a vista**: easing del drawer (DevTools al 10%); reduced-motion (emulato).
```

Nessun finding: `> Nessun finding sul motion.` Nel JSON del report la passata non compare in
`findings` né in `passes_run` con effetti sul verdict: se registrata, come `advisory`.

**Invariante**: non può declassare, mascherare o sopprimere finding di sicurezza o accessibilità
delle passate 1-3.
