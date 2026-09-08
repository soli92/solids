#!/usr/bin/env python3
"""
test_harvest_contract.py — Contract-test per harvest-session-tokens.py su fixture versionata.

Gate di uscita formale di EP-062: questi test devono passare perché l'epica sia "done".
Dipendenze: TSK-545 (walker fan-in), TSK-546 (schema-version guard), TSK-547 (fixture).

Rompe se:
- il formato JSONL drifta e il parser non produce output atteso
- il fan-in walker regredisce (non scopre i sub-agenti nella directory corretta)
- il guard di versione non emette WARNING su versioni ignote o assenti (condizione #2 Critico)
- il contratto di output JSON cambia forma (campo rimosso o rinominato)

NOTA DEBITO TECNICO — doppia struttura fixture (TSK-547):
  La fixture cc-2.1.258-with-subagents/ contiene due directory per i subagent:
    main/subagents/        <- consumata da harvest-session-tokens.py (stem-based walker)
    subagents/             <- path documentata nella spec TSK-547
  I test seguono la struttura effettivamente consumata dallo script (main/subagents/).
  Se il walker viene aggiornato per usare parent(transcript)/subagents/ direttamente,
  la directory main/subagents/ diventerà ridondante. Aprire TSK di follow-up per rimuoverla.

Eseguibile con:
  python3 -m unittest tests/test_harvest_contract.py -v
oppure (fallback):
  python3 tests/test_harvest_contract.py
"""
import json
import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HARVEST_SCRIPT = REPO_ROOT / "tools" / "analytics" / "harvest-session-tokens.py"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "transcripts"

# Fixture principale (versione supportata 2.1.258, con 3 subagent files in main/subagents/)
MAIN_FIXTURE = FIXTURES_DIR / "cc-2.1.258-with-subagents" / "main.jsonl"

# Fixture derivate minimali (poche righe ciascuna, create da TSK-548)
UNSUPPORTED_VERSION_FIXTURE = FIXTURES_DIR / "cc-unsupported-version" / "main.jsonl"
NO_VERSION_FIXTURE = FIXTURES_DIR / "cc-no-version" / "main.jsonl"
NO_SUBAGENTS_FIXTURE = FIXTURES_DIR / "cc-no-subagents" / "main.jsonl"


def run_harvest(transcript_path):
    """Esegue harvest-session-tokens.py --dry-run su transcript_path.

    Ritorna (stdout: str, stderr: str, returncode: int).
    --dry-run garantisce zero side-effect: nessuna chiamata a record-event.sh,
    nessuna scrittura su store, test eseguibile senza rete e senza dipendenze runtime.
    """
    cmd = [sys.executable, str(HARVEST_SCRIPT), str(transcript_path), "--dry-run"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout, result.stderr, result.returncode


class TestHarvestContract(unittest.TestCase):
    """Contract-test per harvest-session-tokens.py.

    Ogni test ha una docstring che specifica quale drift o regressione previene.
    Zero dipendenze esterne: stdlib Python only (unittest, subprocess, json, pathlib, sys).
    """

    def test_fan_in_discovers_subagents(self):
        """Previene regressione del walker fan-in (TSK-545).

        Se collect_jsonl_files() smette di scansionare la directory
        <stem(transcript)>/subagents/, subagent_files torna 0 e l'intera
        attribuzione multi-agente è silenziosamente persa. Questo test rompe
        se il walker regredisce o se la fixture main/subagents/ viene rimossa.

        Struttura attesa: main/subagents/ contiene 3 file agent-*.jsonl.
        """
        stdout, stderr, rc = run_harvest(MAIN_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        data = json.loads(stdout)
        self.assertGreaterEqual(
            data["subagent_files"],
            3,
            f"Attesi >= 3 subagent_files; trovati {data.get('subagent_files')}. "
            "Drift: walker fan-in non ha scoperto i file in main/subagents/. "
            "Se hai aggiornato il walker, aggiorna anche la fixture e questo test."
        )

    def test_scope_attribution_correct(self):
        """Previene mis-attribuzione scope main vs subagent (TSK-545 force_scope).

        Se force_scope='subagent' per i file in subagents/ non viene applicato,
        tutti i record diventano scope='main' per via di isSidechain=True nel
        fallback backward-compat. Questo test rompe se il meccanismo di
        file-location-wins viene rimosso o bypassato.

        Assertion: nell'output dry-run, almeno un actor_id deve contenere
        'subagent' (dal fan-in) e almeno uno deve contenere ':main' (dal main.jsonl).
        """
        stdout, stderr, rc = run_harvest(MAIN_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        data = json.loads(stdout)
        results = data.get("results", [])

        # In modalita' --dry-run ogni result e' {"event": {...}, "recorded": False}
        # actor_id ha forma "claude-code:<scope>" dove scope e' "main" o "subagent"
        actor_ids = [r["event"]["actor_id"] for r in results if "event" in r]

        self.assertTrue(
            any("subagent" in aid for aid in actor_ids),
            f"Nessun actor_id con scope 'subagent' trovato. actor_ids={actor_ids}. "
            "Drift: force_scope per file in subagents/ non applicato."
        )
        self.assertTrue(
            any(":main" in aid for aid in actor_ids),
            f"Nessun actor_id con scope 'main' trovato. actor_ids={actor_ids}. "
            "Drift: scope attribution da main.jsonl via isSidechain non funzionante."
        )

    def test_supported_version_no_warning(self):
        """Previene falsi positive del guard su versioni note (TSK-546).

        La versione 2.1.258 e' in SUPPORTED_CC_VERSIONS: nessun WARNING deve
        comparire su stderr e schema_degraded deve essere False. Se compare un
        warning, il set e' stato ristretto erroneamente o detect_cc_version e'
        rotta. Questo test rompe se 2.1.258 viene rimossa da SUPPORTED_CC_VERSIONS
        senza aggiornare la fixture.
        """
        stdout, stderr, rc = run_harvest(MAIN_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        self.assertEqual(
            stderr.strip(),
            "",
            f"WARNING inatteso su stderr per versione supportata 2.1.258: {stderr!r}. "
            "Regression: il guard ha emesso un avviso su una versione nota."
        )
        data = json.loads(stdout)
        self.assertFalse(
            data.get("schema_degraded", True),
            "schema_degraded=True per versione supportata 2.1.258: "
            "regression nel version guard (TSK-546)."
        )

    def test_unsupported_version_warning(self):
        """Previene parsing silenzioso su versioni ignote (TSK-546, Critico condizione #2).

        La versione 9.9.9 non e' in SUPPORTED_CC_VERSIONS: il guard deve emettere
        WARNING su stderr e impostare schema_degraded=True. Il comportamento deve
        essere fail-loud (non silenzioso) ma fail-open (output prodotto ugualmente).

        Se questo test rompe, il sistema ha rimosso il guard o lo ha reso silenzioso,
        violando il requisito 'nessun parsing best-effort silenzioso' di EP-062.
        """
        stdout, stderr, rc = run_harvest(UNSUPPORTED_VERSION_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        self.assertIn(
            "WARNING",
            stderr,
            f"Nessun WARNING su stderr per versione ignota 9.9.9: {stderr!r}. "
            "Drift: version guard non emette fail-loud su versione non supportata."
        )
        data = json.loads(stdout)
        self.assertTrue(
            data.get("schema_degraded", False),
            "schema_degraded=False per versione ignota 9.9.9: "
            "il guard non ha attivato degraded mode (TSK-546)."
        )
        # Fail-open: l'output deve essere prodotto comunque (non "skip")
        self.assertEqual(
            data.get("status"),
            "ok",
            "Status non 'ok' per versione ignota: fail-open violato. "
            "Il sistema deve produrre output anche in degraded mode."
        )

    def test_missing_version_field_warning(self):
        """Previene silenzio su transcript senza campo version (TSK-546).

        Se il campo 'version' e' assente dal transcript e il sistema non emette
        warning, i consumatori downstream non sanno che il parsing e' incerto.
        detect_cc_version deve ritornare None → degraded path → WARNING.

        Se questo test rompe, detect_cc_version gestisce None silenziosamente
        o il path di guard e' stato rimosso.
        """
        stdout, stderr, rc = run_harvest(NO_VERSION_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        self.assertIn(
            "WARNING",
            stderr,
            f"Nessun WARNING su stderr per transcript senza version field: {stderr!r}. "
            "Drift: detect_cc_version(None) non ha attivato il degraded path."
        )
        data = json.loads(stdout)
        self.assertTrue(
            data.get("schema_degraded", False),
            "schema_degraded=False per transcript senza version field: "
            "regression nel guard (TSK-546) — detect_cc_version=None non gestito."
        )

    def test_backward_compat_no_subagents_dir(self):
        """Previene crash su sessioni pre-2.1.258 senza directory subagents/ (TSK-545).

        Il walker deve essere fail-open: se subagents/ non esiste, l'output
        deve essere identico a prima dell'implementazione fan-in (subagent_files=0,
        solo main.jsonl processato). Nessun crash, nessuna eccezione.

        NOTA DEBITO: la fixture cc-no-subagents/ NON ha una directory main/subagents/
        perche' le sessioni pre-2.1.258 non la creano. Se questo test rompe con un
        OSError, il walker ha perso il fail-open.
        """
        stdout, stderr, rc = run_harvest(NO_SUBAGENTS_FIXTURE)
        self.assertEqual(
            rc,
            0,
            f"Script crash (rc={rc}) su fixture senza subagents/: "
            f"fail-open violato; stderr={stderr!r}"
        )
        data = json.loads(stdout)
        self.assertEqual(
            data.get("subagent_files"),
            0,
            f"Atteso subagent_files=0 per fixture senza subagents dir; "
            f"trovato {data.get('subagent_files')}. "
            "Drift: il walker ha trovato file dove non dovrebbero esisterne."
        )
        self.assertEqual(
            data.get("status"),
            "ok",
            "Status non 'ok' per fixture senza subagents: "
            "fail-open non rispettato (deve processare solo main.jsonl)."
        )

    def test_output_shape_stable(self):
        """Previene drift silenzioso del contratto di output JSON.

        Se lo script rimuove o rinomina un campo top-level, i consumatori
        downstream (EP-061, CI, show-session-tokens.py) ricevono KeyError o
        None silenzioso invece di fallire esplicitamente. Questo test rompe
        se il contratto di output cambia.

        Campi attesi: status, transcript, subagent_files, schema_degraded,
        groups, results. Se aggiungi campi, aggiorni anche questo test.
        Se rimuovi campi, verifica prima l'impatto sui consumatori.
        """
        stdout, stderr, rc = run_harvest(MAIN_FIXTURE)
        self.assertEqual(rc, 0, f"Script uscito con codice {rc}; stderr={stderr!r}")
        data = json.loads(stdout)

        required_fields = {
            "status",
            "transcript",
            "subagent_files",
            "schema_degraded",
            "groups",
            "results",
        }
        missing = required_fields - set(data.keys())
        self.assertEqual(
            missing,
            set(),
            f"Campi mancanti nell'output JSON: {missing}. "
            "Drift: il contratto di output e' cambiato. "
            "Aggiornare consumatori (EP-061, CI) e poi questo test."
        )
        # Invarianti di tipo
        self.assertIsInstance(data["results"], list, "results deve essere una lista.")
        self.assertIsInstance(data["groups"], int, "groups deve essere un intero.")
        self.assertIsInstance(data["subagent_files"], int, "subagent_files deve essere un intero.")
        self.assertIsInstance(data["schema_degraded"], bool, "schema_degraded deve essere bool.")
        self.assertIsInstance(data["status"], str, "status deve essere una stringa.")
        # Ogni elemento results in dry-run ha "event" e "recorded"
        if data["results"]:
            first = data["results"][0]
            self.assertIn(
                "event",
                first,
                "Il primo elemento di results non ha il campo 'event' (dry-run mode)."
            )
            self.assertIn(
                "recorded",
                first,
                "Il primo elemento di results non ha il campo 'recorded' (dry-run mode)."
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
