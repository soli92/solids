"""show-session-tokens.py: una risposta API = un message.id (EP-073 TSK-788).

Claude Code scrive una riga per content block della stessa risposta, ognuna con message.usage
(identico nel main, parziali crescenti nei subagent): sommarle contava ogni risposta 2-3 volte.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_P = Path(__file__).resolve().parents[1] / "analytics" / "show-session-tokens.py"
_s = importlib.util.spec_from_file_location("sst", _P)
sst = importlib.util.module_from_spec(_s)
_s.loader.exec_module(sst)


def _riga(mid, out, cr=100):
    return json.dumps({"type": "assistant", "message": {"id": mid, "model": "claude-opus-5-5",
                       "usage": {"input_tokens": 2, "output_tokens": out, "cache_read_input_tokens": cr,
                                 "cache_creation_input_tokens": 10}}})


def test_righe_dello_stesso_messaggio_contate_una_volta(tmp_path):
    t = tmp_path / "s.jsonl"
    # msg_a: tre blocchi con usage ripetuto; msg_b: parziali di streaming crescenti
    t.write_text("\n".join([_riga("msg_a", 50), _riga("msg_a", 50), _riga("msg_a", 50),
                            _riga("msg_b", 3), _riga("msg_b", 40), _riga("msg_b", 90)]) + "\n")
    tot, modelli = sst.parse_tokens(str(t))
    assert tot == {"input": 4, "output": 140, "cache_read": 200, "cache_write": 20, "cache_write_1h": 0}
    assert modelli == {"claude-opus-5-5"}


def test_righe_senza_id_contate_una_per_una(tmp_path):
    t = tmp_path / "s.jsonl"
    righe = [json.loads(_riga("x", 5)) for _ in range(2)]
    for r in righe:
        del r["message"]["id"]
    t.write_text("\n".join(json.dumps(r) for r in righe) + "\n")
    assert sst.parse_tokens(str(t))[0]["output"] == 10
