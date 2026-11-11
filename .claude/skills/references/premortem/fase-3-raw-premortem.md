# Fase 3 — Raw Premortem (dettaglio completo)

Ambito: dettaglio della Fase 3 di `premortem-protocol.md`. Leggere prima di eseguire la fase.

Genera failure reasons per categoria. Cinque categorie standard. Numero non
fisso: **completezza, non padding**. Stop quando la skill non genera più
ragioni non-banali.

[^src: wiki/concepts/premortem-skill.md §Fase 3]

## Le 5 categorie di failure reasons

### Execution

Cosa va male nell'esecuzione del piano (risorse, tempo, processo).

- *Esempio 1*: «La timeline di 3 mesi era irrealistica perché abbiamo
  sottostimato il refactor delle dipendenze legacy. A 6 settimane eravamo già
  al 70% del budget di tempo con il 30% del lavoro fatto.»
- *Esempio 2*: «Scope creep silenzioso: ogni sprint il PM ha aggiunto 1-2 US
  "piccole" senza re-stimare. A fine quarter avevamo raddoppiato lo scope
  iniziale senza accorgercene.»

### External

Eventi esterni alla tua zona di controllo (mercato, normativa, competitor).

- *Esempio 1*: «Un competitor ha rilasciato la stessa feature 2 settimane prima
  di noi, in versione gratis. Il nostro pricing è diventato insostenibile.»
- *Esempio 2*: «Una nuova normativa GDPR-bis ha richiesto un audit obbligatorio
  prima del lancio che non avevamo pianificato. Slittamento di 4 mesi.»

### People

Disallineamento, key person leaves, skill gap, dynamic interpersonali.

- *Esempio 1*: «Il tech lead che aveva progettato l'architettura ha lasciato
  l'azienda a metà progetto. Nessun altro aveva il mental model completo, e
  abbiamo speso 3 sprint a ricostruirlo.»
- *Esempio 2*: «Gli stakeholder business e tech non hanno mai allineato sulla
  definizione di "MVP". A fine quarter c'erano 2 prodotti diversi nelle teste,
  e il delivery non corrispondeva a nessuno dei due.»

### Technical

Debito tecnico, dipendenze fragili, scalabilità, sicurezza, integrazione.

- *Esempio 1*: «Il database scelto in fase di design non scalava oltre 10k
  utenti concorrenti. Quando il lancio ha portato 50k al picco, il sistema è
  collassato e abbiamo perso le prime 6 ore di traffico.»
- *Esempio 2*: «Una dipendenza esterna (OAuth provider) ha deprecato l'API che
  usavamo a 3 mesi dalla nostra release. Migrazione non pianificata, debito
  esploso.»

### Assumptions

Assunzioni implicite sul mercato, costi, comportamento utente, prerequisiti taciti.

- *Esempio 1*: «Assumevamo che gli utenti enterprise volessero SSO. Survey
  post-rilascio: il 70% usa account locali per ragioni di policy IT. Feature
  SSO sviluppata per 2 mesi, usata dal 30%.»
- *Esempio 2*: «Stima costi infrastruttura basata su prezzi cloud 2024 senza
  considerare che il nostro pattern di traffico (bursty) avrebbe fatto scattare
  tariffe premium. Costo reale 3x stimato.»

**Input atteso**: frase Fase 2 emessa + dossier Fase 1.

**Output prodotto**: lista di failure reasons per ciascuna categoria, ognuna in
forma narrativa breve (1-3 frasi).

**Criterio di completamento**: ogni categoria ha ≥ 1 reason esplorata (anche se la
risposta è «non applicabile a questo target» — esplicito > tacito).
