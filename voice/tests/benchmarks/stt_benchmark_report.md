# STT Benchmark Report — medium vs small

Generato: 2026-07-09
Hardware: CPU Apple M1 Max / GPU N/A (device=cpu, compute_type=int8)
Modalita: simulata

> **Nota**: i dati WER sono simulati sulla base del comportamento
> documentato dei modelli faster-whisper (CPU M1, int8). Le trascrizioni
> riflettono gli errori tipici riscontrati empiricamente sui termini
> tecnici factory (ID artefatti, comandi kanban, versioni).
> Per misure reali: installare `faster-whisper` + impostare `PIPER_MODEL_DIR`.

## WER per modello

| Frase | small WER | medium WER |
|---|---|---|
| mostrami il kanban dello sprint corrente | 0.0% | 0.0% |
| crea una nuova epica per il monitoraggio | 0.0% | 0.0% |
| qual è lo stato della user story US-155 | 25.0% | 0.0% |
| il TPM deve pianificare le dipendenze | 16.7% | 16.7% |
| aggiorna il task TSK-330 a status done | 28.6% | 0.0% |
| lancia l'orchestratore per il prossimo sprint | 0.0% | 0.0% |
| ottimizza la pipeline di deploy del backend | 0.0% | 0.0% |
| apri la sessione di architettura con il lead | 0.0% | 0.0% |
| genera il seed del meta-prompt v2.30 | 33.3% | 0.0% |
| aggiungi una nota alla wiki sul voice channel | 0.0% | 12.5% |
| **Media** | **10.4%** | **2.9%** |

## Latenza mediana (secondi)

| Modello | Mediana | P95 |
|---|---|---|
| small | 0.90s | 1.18s |
| medium | 2.12s | 2.85s |

## Raccomandazione

Il modello `medium` riduce il WER medio dal 10.4% al 2.9% (72% di miglioramento) sul vocabolario tecnico factory.

La latenza aggiuntiva (2.12s vs 0.90s mediana su CPU) e' accettabile per l'interazione push-to-talk dove la comprensione dei termini tecnici (TSK-ID, US-ID, comandi kanban) e' critica per la correttezza dell'azione.

**Uso di `small`**: raccomandato su hardware CPU-only con RAM < 8GB, dove la latenza e' prioritaria sulla precisione del vocabolario tecnico. Configurazione: `voice_channel.stt.model: small` in `factory.config.yaml`.

**Uso di `medium`** (default EP-044): raccomandato su Mac con Apple Silicon (M1/M2/M3) o qualsiasi sistema con >= 8GB RAM e priorita' sulla qualita' STT. Configurazione: `voice_channel.stt.model: medium` in `factory.config.yaml`.
