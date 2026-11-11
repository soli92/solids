"""visual/ — Canale visivo della factory (EP-067, US-279..US-281).

Gemello di `voice/`. Il contratto e' lo stesso: `voice.runtime.factory_runtime.FactoryRuntime`
dichiara sette tipi di evento e instrada `Progress`, `Artifact` ed `Error` verso «il canale
visivo», implementato finora come «stdout strutturato in MVP». Questo pacchetto e' quel canale.

INVARIANTI (EP-067 §Cosa NON fa, US-288):

  1. READ-ONLY. Nessun modulo qui apre in scrittura un file sotto `wiki/`,
     `management/` o `analytics/`. Verificato da test, non solo dichiarato.
  2. NON E' UNO SCRITTORE sullo stato della factory. Quando arrivera' lo stadio di
     scrittura (Wave C) ogni azione sara' una `submit()` al contratto: lo scrittore
     resta la sessione, che resta singola.
  3. `Artifact.content` NON raggiunge mai un componente di sintesi vocale. E' l'invariante
     non negoziabile del contratto, qui ereditata nella direzione opposta.
  4. MAI ZERO AL POSTO DI «NON LO SO». Una fonte illeggibile produce
     `Reading(available=False, reason=...)`, non `0`. Le due cose si leggono uguali
     e significano l'opposto.

Zero dipendenze esterne: solo stdlib.
"""

__version__ = "0.1.0"
PATTERN_VERSION_EXPECTED = "2.43"
