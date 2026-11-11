"""voice/tts/sentence_splitter.py — split testo in frasi per sintesi progressiva.

Nessuna dipendenza esterna: solo stdlib.
"""

import re


def split_into_sentences(text: str) -> list[str]:
    """Divide il testo in frasi per la sintesi progressiva (latenza ridotta).

    Splitta su fine frase ('.', '!', '?') seguita da spazio, oppure su
    doppio newline ('\\n\\n' o piu').  Rimuove frasi vuote dopo la pulizia
    degli spazi iniziali/finali.

    Utile per sintetizzare e riprodurre una frase alla volta:
        for sentence in split_into_sentences(full_text):
            audio = await asyncio.to_thread(tts.synthesize, sentence)
            playback.play(audio)

    Args:
        text: Testo grezzo da dividere.

    Returns:
        Lista di frasi non vuote, ognuna ripulita da spazi iniziali/finali.
    """
    # Split su fine frase (.!?) seguita da spazio bianco, o su doppio newline
    parts = re.split(r'(?<=[.!?])\s+|\n{2,}', text.strip())
    return [s.strip() for s in parts if s.strip()]
