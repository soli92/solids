# /worst-case — Lista membri (Item + Avatar + Badge) — 2026-11-11

Story: `src/stories/lista-membri.stories.tsx` (+ `lista-membri.fixtures.ts`). Toggle solo dev: arg `dati` = demo | peggiore | vuoto | uno | mille
(Controls di Storybook, oppure `iframe.html?id=solids-esempi-lista-membri-caso-peggiore--lista&viewMode=story&args=dati:peggiore`).
Stati validati via DOM (`data-modalita`, numero righe, intestazione) in `metriche.json` prima di leggere gli screenshot.

| # | Gravita | Campo | Valore | Cosa si rompe | Fix proposto | Decisione | Prova |
|---|---|---|---|---|---|---|---|
| 1 | Rotto | email (ItemDescription) | `ops@sub.reparto.regione.example.co.uk` (nessun punto di a-capo) | A 200% (root 32px) esce dalla card (3 righe con item-title/description oltre il bordo, scrollWidth > clientWidth); a 320 tocca il bordo | `item.tsx` ItemContent: `min-w-0`; ItemTitle/ItemDescription: `[overflow-wrap:anywhere]` | no | peggiore-zoom200.png, peggiore-320.png |
| 2 | Rotto | email / ruolo (ItemDescription) | email PEC da 78 car., ruolo da 69 car. | `line-clamp-2` tronca in silenzio in coda: a 320/200% si perde il dominio, nessun modo di vedere il valore intero | `item.tsx` ItemDescription: tooltip/`title` o clamp opt-out (prop); per email troncamento al centro | si (a capo, clamp o centro) | peggiore-320.png (riga 2), peggiore-zoom200.png |
| 3 | Brutto | immagine Avatar | panorama 4000x200 | AvatarImage ha `aspect-square h-full w-full` senza `object-cover`: l'immagine e' schiacciata in una linea di 2px | `avatar.tsx` AvatarImage: aggiungere `object-cover` | no | peggiore-480.png (riga 1) |
| 4 | Brutto | ItemActions + Badge | `Invito scaduto da 1284 giorni`, 320 px / 200% | Item e' `flex-wrap`: l'azione scende sotto il testo in modo incoerente (alcune righe badge a destra, altre sotto); Badge senza `whitespace-nowrap` va su 2-3 righe (altezza 74px a 200%) | `badge.tsx`: `whitespace-nowrap` (+ `max-w-full truncate` o `min-w-0` in ItemActions); decidere se l'azione deve restare in riga | si | peggiore-320.png, peggiore-zoom200.png |
| 5 | Brutto | nome mancante (ItemTitle) | `nome` assente | Titolo vuoto: altezza 0, riga senza identita (solo email); il DS non offre un placeholder | `item.tsx` ItemTitle: nessun fallback automatico, documentare/story con «—» o email come titolo | si (cosa mostrare) | peggiore-480.png (riga 4) |
| 6 | Brutto | AvatarFallback | `🦊 Volpe` -> `�V`; `王秀英`/arabo -> 1 glifo | Il DS non fornisce iniziali: il consumatore improvvisa `split(" ").map(p=>p[0])` e spezza la coppia surrogata. Nota: l'helper e' nella story (codice del consumatore), non in `src/components/` | Helper `getInitials` esportato dal DS con `Intl.Segmenter` | si | peggiore-480.png (riga 5) |
| 7 | Fragile | RTL, stringhe miste | `<script>alert(1)</script> & **grassetto**` | Il layout si specchia bene, ma il titolo con simboli e `&amp;` viene riordinato dal BiDi (`**script>...`, `;amp&`) senza `dir="auto"` | ItemTitle/ItemDescription: `dir="auto"` opzionale | si | peggiore-rtl.png |
| 8 | Fragile | lista | 1.284 righe non paginate | Nessuna virtualizzazione: 14.079 nodi DOM, ~660 ms al primo render in headless (misura in `metriche.json`) | Paginare o virtualizzare nel consumatore; il DS non ha un componente lista virtualizzata | si | mille-480.png |
| 9 | Fragile | conteggio | `1` | Plurale cablato nella story («1 membri»): il DS non fornisce formattazione; il ruolo e' del consumatore | `Intl.PluralRules` nella composizione | no | uno-480.png |

Ha retto (non toccare): escape letterale di `<script>`/`&amp;`/`**`; CJK e arabo; diacritici vietnamiti (`ĐT`, nessun taglio); nome di una lettera; avatar 404 -> fallback delle iniziali di pari dimensione (40x40 ovunque); tema scuro (nessun overflow); duplicati; vuoto (stato «Nessun membro»); nessun errore JS in nessuno stato.
Toggle: story `SoliDS/Esempi/Lista membri (caso peggiore)`, arg `dati` (5 stati). Verificato a vista/DOM: 600, 320, 200% font, dark, RTL.
Fix applicati: vedi la sezione seguente.

## Dopo i fix (2026-11-12)

Rerun su `storybook-static` (stessa fixture, stessi stati e misure del primo run; chrome-headless-shell). Screenshot in `dopo/`, misure in `dopo/metriche.json`. Asserzioni DOM su ogni stato: elementi oltre il bordo della card = 0 (`totalOver: 0`, anche 320, root 32px, dark, RTL), nessun errore JS, nessun overflow del documento.
Correzione in corsa: `min-w-0` + `overflow-wrap:anywhere` da soli facevano collassare ItemContent a un carattere per riga accanto a un badge largo (riga 2 a 320: 707px di altezza) invece di mandare a capo le azioni. ItemContent ora ha `flex-[1_1_12rem]`: sotto quella larghezza utile va a capo l'intera riga actions.

| # | Esito | Misura |
|---|---|---|
| 1 | risolta | `totalOver = 0` a root 32px e a 320; email lunga spezzata dentro la card |
| 2 | lato consumatore | `line-clamp-2` resta; la story espone il valore intero con `title=` (`title=` nel codice della story, non asserito nel DOM); nota in `docs/getting-started.mdx` |
| 3 | risolta | `AvatarImage` `object-fit: cover` (riga 0, tutti gli stati) |
| 4 | risolta | badge 1 riga in tutte le righe (altezza 22px, 42px a 200%); a 320 e a 200% `actionsWrapped = true` su 12/12 righe (a capo l'intera riga, coerente); a 600 nessuna riga a capo; demo 320/600 con le stesse altezze di prima (127/95) |
| 5 | lato consumatore | nessun fallback nel componente; la story usa l'email come titolo (`titleEmpty = false` su 12/12) |
| 6 | risolta (helper in `src/lib/initials.ts`) | `🦊 Volpe` -> `🦊V`; `scripts/initials-test.mjs`: `initials: ok` (emoji, ZWJ, D'Alessandro, una lettera, vuota, spazi multipli, CJK, arabo) |
| 7 | risolta | `dir="auto"` presente su ItemTitle/ItemDescription in tutte le righe, sovrascrivibile |
| 8 | lato consumatore | nessuna virtualizzazione nel DS (1.284 righe: 13.972 nodi, 461 ms headless); nota docs: paginare o virtualizzare |
| 9 | lato consumatore | story con `Intl.PluralRules`: `1 membro`, `0 membri`, `1284 membri`; nota docs |

Demo normale prima/dopo: altezze e larghezze identiche a 600 e 320 (metriche); i PNG non sono byte-identici (il primo run usava un altro binario Chrome, non verificato come causa). 
