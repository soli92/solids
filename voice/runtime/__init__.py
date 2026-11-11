# voice/runtime — Adattatori FactoryRuntime (unico contatto col runtime LLM)
#
# Esporta il contratto pubblico del sotto-pacchetto:
#   - FactoryRuntime (ABC) + tassonomia eventi (factory_runtime.py)
#   - MockAdapter — adapter di test, nessuna dipendenza LLM (sempre disponibile)
#   - CustomLoopAdapter (Opzione B) — disponibile solo se 'anthropic' e' installato
#   - OllamaAdapter — runtime locale via Ollama HTTP ndjson; richiede httpx
#     (dipendenza transitiva di 'anthropic') o urllib.request come fallback
#
# Importazione lazy degli adapter LLM: non importarli a livello di modulo
# se le rispettive dipendenze non sono installate (EP-041, dipendenze opzionali).
from voice.runtime.factory_runtime import (
    Acknowledgment,
    Artifact,
    Done,
    Error,
    FactoryRuntime,
    Progress,
    Question,
    RuntimeEvent,
    SpokenSummary,
)
from voice.runtime.mock_adapter import MockAdapter

__all__ = [
    "FactoryRuntime",
    "RuntimeEvent",
    "Acknowledgment",
    "Progress",
    "SpokenSummary",
    "Artifact",
    "Question",
    "Done",
    "Error",
    "MockAdapter",
    # CustomLoopAdapter: importata esplicitamente dal consumer quando anthropic e' disponibile
    # from voice.runtime.custom_loop_adapter import CustomLoopAdapter
    # OllamaAdapter: importata esplicitamente dal consumer (httpx dipendenza transitiva)
    # from voice.runtime.ollama_adapter import OllamaAdapter
]
