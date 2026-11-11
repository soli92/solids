"""
voice — Voice Channel Factory module (EP-041).

Canale di interazione vocale (STT/TTS) opt-in per la factory multi-agente.
Il modulo e' un front-end alternativo: si mette davanti al runtime LLM esistente
senza modificare la factory. Abilitato solo quando voice_channel.enabled: true
in factory.config.yaml.

Struttura:
    audio/      I/O audio real-time (capture, playback, devices, aec)
    vad/        Voice Activity Detection + endpointing
    stt/        Speech-to-Text (faster-whisper)
    tts/        Text-to-Speech (piper-tts)
    runtime/    Adattatori FactoryRuntime (unico contatto col runtime)
    core/       Orchestrazione: state_machine, router, cancellation, session
    app.py      Entry point CLI (python -m voice.app)
    config.py   Lettura sezione voice_channel: da factory.config.yaml
"""

__version__ = "0.1.0"
