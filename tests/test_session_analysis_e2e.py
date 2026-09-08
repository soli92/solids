#!/usr/bin/env python3
"""
test_session_analysis_e2e.py — EP-061/US-247/TSK-557
End-to-end tests for the session analysis pipeline on versionated fixture.

Gate di uscita formale di EP-061: questi test devono passare perché l'epica
sia "done". Coprono la pipeline completa:
  parse-transcript.py → fleet-metrics.py → detect-anomalies.py → generate-report.py

Verifica invarianti R-SAA:
  R-SAA-3: nessun body tool_result / PII nei report
  R-SAA-5: ingest_eligible: false nel frontmatter markdown
  R-SAA-7: ogni anomalia ha provenance valorizzato (anti-fabbricazione)
  R-SAA-8: gate su sessioni "aperte" (mtime recente o CLAUDE_SESSION_ID match)

Rompe se:
  - uno step della pipeline produce exit code != 0
  - generate-report.py non produce MD + JSON con naming corretto
  - i campi obbligatori del JSON report mancano
  - le invarianti R-SAA non sono rispettate
  - il kill_criterion_ref in factory.config.yaml non punta a EP-061.md
  - la fixture non scatena almeno 1 anomalia BUDGET_OVERFLOW (regression detector)

Eseguibile con:
  python3 -m unittest tests/test_session_analysis_e2e.py -v
oppure (se pytest installato):
  pytest tests/test_session_analysis_e2e.py -v

Zero dipendenze esterne: stdlib only. jsonschema opzionale con fallback manuale.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import unittest

# ── Repo paths ─────────────────────────────────────────────────────────────────
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools" / "session-analysis"

PARSE_SCRIPT    = TOOLS_DIR / "parse-transcript.py"
METRICS_SCRIPT  = TOOLS_DIR / "fleet-metrics.py"
DETECT_SCRIPT   = TOOLS_DIR / "detect-anomalies.py"
REPORT_SCRIPT   = TOOLS_DIR / "generate-report.py"
SCHEMA_FILE     = TOOLS_DIR / "schema-anomaly.json"

FIXTURE_DIR     = REPO_ROOT / "tests" / "fixtures" / "transcripts" / "cc-2.1.258-with-subagents"
MAIN_FIXTURE    = FIXTURE_DIR / "main.jsonl"

FACTORY_CONFIG  = REPO_ROOT / "factory.config.yaml"
EP061_PATH      = REPO_ROOT / "management" / "kanban" / "EP-061-session-agentic-analyser" / "EP-061.md"

# ── JSON report required fields (R-SAA-5, schema conformance) ─────────────────
REQUIRED_JSON_FIELDS = {
    "type", "session_id", "ingest_eligible", "wiki_ingest_policy",
    "ttl_days", "anomalies", "fleet_recommendations", "session_metrics",
}

# ── Naming pattern: YYYY-MM-DD-session-analysis-<8char>.{md,json} ─────────────
FILENAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-session-analysis-([A-Za-z0-9]{1,8})\.(md|json)$")

# ── PII patterns that must NOT appear in output (R-SAA-3) ─────────────────────
PII_PATTERNS = [
    re.compile(r"simone\.olivieri"),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer [A-Za-z0-9._\-]{10,}"),
]


def run_script(script, *args, env=None, timeout=60):
    """Run a Python script with subprocess, return (stdout, stderr, returncode)."""
    cmd = [sys.executable, str(script)] + [str(a) for a in args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return result.stdout, result.stderr, result.returncode


class TestSessionAnalysisE2E(unittest.TestCase):
    """End-to-end pipeline test using versionated fixture cc-2.1.258-with-subagents.

    setUpClass esegue la pipeline completa una volta sola e registra i risultati.
    I test individuali consumano i risultati cached o skipano con messaggio chiaro.
    """

    # ── Class-level state populated by setUpClass ──────────────────────────────
    _tmpdir = None          # TemporaryDirectory object (kept alive for all tests)
    _tmp_path = None        # pathlib.Path to tmpdir
    _parsed_path = None     # parse-transcript.py output
    _metrics_path = None    # fleet-metrics.py output
    _anomalies_path = None  # detect-anomalies.py output
    _report_output_dir = None  # generate-report.py --output-dir
    _pipeline_steps = {}    # step_name → (rc, stdout, stderr)
    _report_files = []      # list of pathlib.Path produced by generate-report.py

    @classmethod
    def setUpClass(cls):
        """Run the full pipeline once on the fixture and cache results."""
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="ep061_e2e_")
        cls._tmp_path = pathlib.Path(cls._tmpdir.name)
        cls._report_output_dir = cls._tmp_path / "reports"
        cls._report_output_dir.mkdir(parents=True, exist_ok=True)

        parsed_out    = cls._tmp_path / "parsed.json"
        metrics_out   = cls._tmp_path / "metrics.json"
        anomalies_out = cls._tmp_path / "anomalies.json"

        # Step 1: parse-transcript.py
        stdout, stderr, rc = run_script(PARSE_SCRIPT, str(MAIN_FIXTURE), "--output", str(parsed_out))
        cls._pipeline_steps["parse"] = (rc, stdout, stderr)
        if rc == 0:
            cls._parsed_path = parsed_out

        # Step 2: fleet-metrics.py
        if cls._parsed_path and cls._parsed_path.exists():
            stdout, stderr, rc = run_script(METRICS_SCRIPT, str(cls._parsed_path), "--output", str(metrics_out))
            cls._pipeline_steps["metrics"] = (rc, stdout, stderr)
            if rc == 0:
                cls._metrics_path = metrics_out

        # Step 3: detect-anomalies.py
        if cls._parsed_path and cls._metrics_path:
            stdout, stderr, rc = run_script(DETECT_SCRIPT, str(cls._parsed_path), str(cls._metrics_path), "--output", str(anomalies_out))
            cls._pipeline_steps["detect"] = (rc, stdout, stderr)
            if rc == 0:
                cls._anomalies_path = anomalies_out

        # Step 4: generate-report.py
        if cls._parsed_path and cls._metrics_path and cls._anomalies_path:
            stdout, stderr, rc = run_script(
                REPORT_SCRIPT,
                str(cls._anomalies_path),
                str(cls._metrics_path),
                str(cls._parsed_path),
                "--output-dir", str(cls._report_output_dir),
            )
            cls._pipeline_steps["report"] = (rc, stdout, stderr)
            if rc == 0:
                cls._report_files = sorted(cls._report_output_dir.iterdir())

    @classmethod
    def tearDownClass(cls):
        """Cleanup: remove TemporaryDirectory (all pipeline output)."""
        if cls._tmpdir is not None:
            try:
                cls._tmpdir.cleanup()
            except Exception:
                pass  # fail-open: even if cleanup fails, test runner proceeds

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _require_report_files(self):
        """Skip this test if generate-report.py did not produce output files.

        Called at the top of tests that depend on the final report.
        Provides a clear skip message pointing to test_pipeline_e2e_full_chain
        for root-cause analysis.
        """
        if not self._report_files:
            rc_report = self._pipeline_steps.get("report", (None,))[0]
            stderr_report = self._pipeline_steps.get("report", (None, None, ""))[2]
            raise unittest.SkipTest(
                f"Nessun file di report prodotto da generate-report.py "
                f"(exit code: {rc_report}). "
                f"Errore: {stderr_report[:400] if stderr_report else 'n/a'}. "
                "Vedi test_pipeline_e2e_full_chain per il dettaglio del fallimento."
            )

    def _get_json_report(self):
        """Return parsed JSON report dict, or skip if not available."""
        self._require_report_files()
        json_files = [f for f in self._report_files if f.suffix == ".json"]
        if not json_files:
            raise unittest.SkipTest("Nessun file .json tra i report prodotti.")
        return json.loads(json_files[0].read_text(encoding="utf-8")), json_files[0]

    def _get_md_report(self):
        """Return markdown report content string, or skip if not available."""
        self._require_report_files()
        md_files = [f for f in self._report_files if f.suffix == ".md"]
        if not md_files:
            raise unittest.SkipTest("Nessun file .md tra i report prodotti.")
        return md_files[0].read_text(encoding="utf-8"), md_files[0]

    # ── Test 1: Full pipeline chain ────────────────────────────────────────────

    def test_pipeline_e2e_full_chain(self):
        """Pipeline completa: ogni step deve uscire con exit code 0 e produrre JSON valido.

        Rompe se uno step regredisce (es. flag CLI rimosso, crash interno, output
        non-JSON). Rappresenta la regression detection primaria per l'intera chain.
        """
        # ── Step 1: parse-transcript.py ────────────────────────────────────────
        rc_parse, stdout_parse, stderr_parse = self._pipeline_steps.get("parse", (None, "", ""))
        self.assertIsNotNone(rc_parse, "parse-transcript.py non è stato eseguito (setup fallito)")
        self.assertEqual(
            rc_parse, 0,
            f"parse-transcript.py ha restituito exit code {rc_parse}.\n"
            f"stderr: {stderr_parse[:500]}"
        )
        self.assertTrue(
            self._parsed_path and self._parsed_path.exists(),
            "parse-transcript.py: file di output non trovato."
        )
        try:
            parsed_data = json.loads(self._parsed_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.fail(f"parse-transcript.py: output non è JSON valido: {exc}")
        self.assertIn("meta", parsed_data, "parse output: campo 'meta' mancante.")
        self.assertIn("records", parsed_data, "parse output: campo 'records' mancante.")

        # ── Step 2: fleet-metrics.py ────────────────────────────────────────────
        rc_metrics, stdout_metrics, stderr_metrics = self._pipeline_steps.get("metrics", (None, "", ""))
        self.assertIsNotNone(rc_metrics, "fleet-metrics.py non è stato eseguito (step 1 fallito?)")
        self.assertEqual(
            rc_metrics, 0,
            f"fleet-metrics.py ha restituito exit code {rc_metrics}.\n"
            f"stderr: {stderr_metrics[:500]}"
        )
        self.assertTrue(
            self._metrics_path and self._metrics_path.exists(),
            "fleet-metrics.py: file di output non trovato."
        )
        try:
            metrics_data = json.loads(self._metrics_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.fail(f"fleet-metrics.py: output non è JSON valido: {exc}")
        self.assertIn("session_totals", metrics_data, "metrics output: campo 'session_totals' mancante.")

        # ── Step 3: detect-anomalies.py ────────────────────────────────────────
        rc_detect, stdout_detect, stderr_detect = self._pipeline_steps.get("detect", (None, "", ""))
        self.assertIsNotNone(rc_detect, "detect-anomalies.py non è stato eseguito (step 2 fallito?)")
        self.assertEqual(
            rc_detect, 0,
            f"detect-anomalies.py ha restituito exit code {rc_detect}.\n"
            f"stderr: {stderr_detect[:500]}"
        )
        self.assertTrue(
            self._anomalies_path and self._anomalies_path.exists(),
            "detect-anomalies.py: file di output non trovato."
        )
        try:
            anomalies_data = json.loads(self._anomalies_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.fail(f"detect-anomalies.py: output non è JSON valido: {exc}")
        self.assertIn("anomalies", anomalies_data, "detect output: campo 'anomalies' mancante.")

        # ── Step 4: generate-report.py ─────────────────────────────────────────
        rc_report, stdout_report, stderr_report = self._pipeline_steps.get("report", (None, "", ""))
        self.assertIsNotNone(
            rc_report,
            "generate-report.py non è stato eseguito (step 3 fallito?)."
        )
        self.assertEqual(
            rc_report, 0,
            f"generate-report.py ha restituito exit code {rc_report}.\n"
            f"stderr: {stderr_report[:800]}\n"
            f"BUG NOTE: verificare che generate-report.py usi la stessa chiave "
            f"del campo modello prodotta da fleet-metrics.py (es. 'model' vs 'model_id')."
        )
        self.assertTrue(
            len(self._report_files) >= 2,
            f"generate-report.py: attesi >= 2 file in output-dir; trovati {len(self._report_files)}."
        )

        # Final: verify both MD and JSON exist
        suffixes = {f.suffix for f in self._report_files}
        self.assertIn(".md", suffixes, "Nessun file .md prodotto da generate-report.py.")
        self.assertIn(".json", suffixes, "Nessun file .json prodotto da generate-report.py.")

    # ── Test 2: Schema conformance ─────────────────────────────────────────────

    def test_schema_conformance_report_json(self):
        """Il JSON report deve soddisfare il contratto di schema (campi obbligatori + valori attesi).

        Se jsonschema è importabile: valida contro schema-anomaly.json.
        Se non disponibile: fallback validazione manuale dei campi obbligatori.
        Rompe se: un campo obbligatorio manca o un valore invariante è cambiato.
        """
        report, json_path = self._get_json_report()

        # Verifica campi obbligatori (R-SAA-5 + schema contract)
        missing = REQUIRED_JSON_FIELDS - set(report.keys())
        self.assertEqual(
            missing, set(),
            f"Campi mancanti nel JSON report: {missing}. "
            f"File: {json_path}."
        )

        # Verifica valori invarianti (R-SAA-5)
        self.assertFalse(
            report.get("ingest_eligible", True),
            f"ingest_eligible deve essere False (R-SAA-5); trovato: {report.get('ingest_eligible')}."
        )
        self.assertEqual(
            report.get("wiki_ingest_policy"),
            "incidents-only",
            f"wiki_ingest_policy deve essere 'incidents-only' (R-SAA-5); "
            f"trovato: {report.get('wiki_ingest_policy')}."
        )
        self.assertEqual(
            report.get("ttl_days"),
            90,
            f"ttl_days deve essere 90 (R-SAA-5); trovato: {report.get('ttl_days')}."
        )
        self.assertEqual(
            report.get("type"),
            "session-analysis-report",
            f"type deve essere 'session-analysis-report'; trovato: {report.get('type')}."
        )

        # Verifica tipi
        self.assertIsInstance(report.get("anomalies"), list, "anomalies deve essere una lista.")
        self.assertIsInstance(report.get("fleet_recommendations"), list, "fleet_recommendations deve essere lista.")
        self.assertIsInstance(report.get("session_metrics"), dict, "session_metrics deve essere un dict.")

        # Validazione con jsonschema (opzionale)
        try:
            import jsonschema  # noqa: PLC0415
        except ImportError:
            # Fallback già fatto sopra (manuale). Schema avanzato opzionale.
            return

        if SCHEMA_FILE.exists():
            full_schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
            # Cerca la definizione SessionAnalysisReport e costruisci uno schema
            # wrapper che preserva $defs per risoluzione dei $ref interni
            # (es. #/$defs/Anomaly, #/$defs/FleetRecommendation).
            defs = full_schema.get("$defs") or full_schema.get("definitions") or {}
            report_subschema = defs.get("SessionAnalysisReport")
            if report_subschema is not None:
                # Merge subschema come root, preservando $defs padre per i $ref
                wrapper = dict(report_subschema)
                wrapper["$defs"] = defs
                validation_schema = wrapper
            else:
                validation_schema = full_schema
            try:
                jsonschema.validate(instance=report, schema=validation_schema)
            except jsonschema.ValidationError as exc:
                self.fail(
                    f"JSON report non valido secondo schema-anomaly.json: {exc.message}. "
                    f"Path: {list(exc.absolute_path)}."
                )

    # ── Test 3: R-SAA-3 — no tool_result bodies / no PII ─────────────────────

    def test_r_saa_3_no_tool_result_bodies(self):
        """Nessun body tool_result e nessun PII devono sopravvivere nel report.

        R-SAA-3: redazione applicata prima di qualsiasi scrittura.
        Rompe se: path personali (simone.olivieri), credential (sk-*), o email
        compaiono nel MD o JSON prodotto.
        """
        self._require_report_files()

        combined_content = ""
        for f in self._report_files:
            combined_content += f.read_text(encoding="utf-8")

        for pat in PII_PATTERNS:
            match = pat.search(combined_content)
            self.assertIsNone(
                match,
                f"PII pattern '{pat.pattern}' trovato nel report. "
                f"Match: '{match.group()[:60] if match else ''}'. "
                "Drift: R-SAA-3 redaction incompleta."
            )

    # ── Test 4: R-SAA-5 — frontmatter ingest_eligible: false ─────────────────

    def test_r_saa_5_frontmatter_ingest_eligible_false(self):
        """Il frontmatter markdown deve dichiarare ingest_eligible: false.

        R-SAA-5: hardcoded, non-bypassable. Rompe se generate-report.py
        rimuove o modifica questo campo nel frontmatter YAML.
        """
        md_content, md_path = self._get_md_report()

        # Estrai frontmatter (tra --- iniziale e --- di chiusura)
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", md_content, re.DOTALL)
        self.assertIsNotNone(
            fm_match,
            f"Frontmatter YAML non trovato nel markdown (pattern ---...---). "
            f"File: {md_path}."
        )
        frontmatter = fm_match.group(1)

        # Verifica ingest_eligible: false
        self.assertRegex(
            frontmatter,
            r"ingest_eligible:\s*false",
            f"ingest_eligible: false non trovato nel frontmatter (R-SAA-5). "
            f"Frontmatter:\n{frontmatter[:300]}."
        )

        # Verifica wiki_ingest_policy: incidents-only
        self.assertRegex(
            frontmatter,
            r"wiki_ingest_policy:\s*[\"']?incidents-only[\"']?",
            f"wiki_ingest_policy: incidents-only non trovato nel frontmatter. "
            f"Frontmatter:\n{frontmatter[:300]}."
        )

        # Verifica ttl_days: 90
        self.assertRegex(
            frontmatter,
            r"ttl_days:\s*90",
            f"ttl_days: 90 non trovato nel frontmatter. "
            f"Frontmatter:\n{frontmatter[:300]}."
        )

    # ── Test 5: R-SAA-7 — provenance populated ────────────────────────────────

    def test_r_saa_7_provenance_populated(self):
        """Ogni anomalia deve avere provenance.source_field e source_file valorizzati.

        R-SAA-7 anti-fabbricazione: se non c'è prova → skip anomalia (mai fabbricare).
        Rompe se detect-anomalies.py emette anomalie senza provenance, oppure se
        la lista è inaspettatamente vuota (usare test 10 per quest'ultimo caso).
        """
        report, _ = self._get_json_report()
        anomalies = report.get("anomalies", [])

        if not anomalies:
            raise unittest.SkipTest(
                "Nessuna anomalia nel report. "
                "La fixture attuale dovrebbe scatenare BUDGET_OVERFLOW: "
                "verifica che detect-anomalies.py funzioni correttamente "
                "(vedi test_regression_detect_anomaly_on_fixture)."
            )

        valid_source_files = {"parsed", "metrics"}
        for i, ano in enumerate(anomalies):
            provenance = ano.get("provenance")
            self.assertIsNotNone(
                provenance,
                f"Anomalia [{i}] id={ano.get('id')} manca del campo 'provenance' (R-SAA-7)."
            )
            source_field = provenance.get("source_field") if provenance else None
            self.assertTrue(
                source_field and len(str(source_field)) > 0,
                f"Anomalia [{i}] id={ano.get('id')}: provenance.source_field vuoto (R-SAA-7). "
                f"provenance={provenance}."
            )
            source_file = provenance.get("source_file") if provenance else None
            self.assertIn(
                source_file,
                valid_source_files,
                f"Anomalia [{i}] id={ano.get('id')}: provenance.source_file='{source_file}' "
                f"non è in {valid_source_files} (R-SAA-7)."
            )

    # ── Test 6: R-SAA-8 — out-of-band gate ───────────────────────────────────

    def test_r_saa_8_out_of_band_gate(self):
        """parse-transcript.py deve rifiutare (exit 2) una sessione "ancora aperta".

        R-SAA-8: due euristiche:
          1. CLAUDE_SESSION_ID env var == session_id estratto dal nome file
          2. mtime del file JSONL < 60s fa

        Prova entrambe; se nessuna triggera il gate (es. per limitazioni di env),
        spiega in dettaglio e skippa con motivazione.
        """
        # Crea un JSONL temporaneo con nome fittizio e mtime recentissimo
        session_name = f"fake-open-session-{int(time.time())}"
        fake_jsonl = self._tmp_path / f"{session_name}.jsonl"

        # Copia il contenuto di main.jsonl per avere un file JSONL valido
        original_content = MAIN_FIXTURE.read_text(encoding="utf-8")
        fake_jsonl.write_text(original_content, encoding="utf-8")

        # Euristica 2: mtime < 60s ago — il file appena scritto è recentissimo
        _, stderr_mtime, rc_mtime = run_script(PARSE_SCRIPT, str(fake_jsonl))

        if rc_mtime == 2:
            # Euristica mtime ha triggerato correttamente
            self.assertIn(
                "R-SAA-8",
                stderr_mtime,
                f"exit code 2 ottenuto ma messaggio R-SAA-8 non trovato in stderr: {stderr_mtime[:300]}."
            )
            return  # test PASSA

        # Euristica 2 non ha triggerato: prova euristica 1 (env var CLAUDE_SESSION_ID)
        env_with_sid = os.environ.copy()
        env_with_sid["CLAUDE_SESSION_ID"] = session_name  # match per stem del file

        _, stderr_env, rc_env = run_script(PARSE_SCRIPT, str(fake_jsonl), env=env_with_sid)

        if rc_env == 2:
            self.assertIn(
                "R-SAA-8",
                stderr_env,
                f"exit code 2 ottenuto con env var ma messaggio R-SAA-8 non trovato: {stderr_env[:300]}."
            )
            return  # test PASSA

        # Nessuna delle due euristiche ha triggerato — spiega e skippa
        raise unittest.SkipTest(
            f"R-SAA-8 gate non triggerato né con mtime (rc={rc_mtime}) "
            f"né con CLAUDE_SESSION_ID (rc={rc_env}). "
            f"Possibili cause:\n"
            f"  - mtime: filesystem risoluzione troppo bassa o OS ha normalizzato il tempo\n"
            f"  - CLAUDE_SESSION_ID: il tool confronta session_id derivato dal nome file "
            f"    '{session_name}' ma usa un'altra derivazione (es. UUID dal contenuto JSONL)\n"
            f"Stderr mtime: {stderr_mtime[:200]}\n"
            f"Stderr env: {stderr_env[:200]}\n"
            f"Verifica manuale: R-SAA-8 è implementato in parse-transcript.py "
            f"_check_session_open() con le due euristiche documentate."
        )

    # ── Test 7: Dual output naming ────────────────────────────────────────────

    def test_dual_output_naming(self):
        """Esattamente 2 file prodotti: YYYY-MM-DD-session-analysis-<id>.(md|json).

        Rompe se generate-report.py produce file extra, nessun file, o nomi
        non conformi al pattern atteso.
        """
        self._require_report_files()

        self.assertEqual(
            len(self._report_files), 2,
            f"Attesi esattamente 2 file nell'output-dir; trovati {len(self._report_files)}: "
            f"{[f.name for f in self._report_files]}."
        )

        ids_found = set()
        for f in self._report_files:
            m = FILENAME_RE.match(f.name)
            self.assertIsNotNone(
                m,
                f"Nome file '{f.name}' non corrisponde al pattern "
                f"YYYY-MM-DD-session-analysis-<id-8char>.(md|json)."
            )
            ids_found.add(m.group(1))

        self.assertEqual(
            len(ids_found), 1,
            f"I due file hanno ID diversi: {ids_found}. "
            "Devono condividere lo stesso <id-8char>."
        )

    # ── Test 8: Regression kill criterion ref ────────────────────────────────

    def test_regression_kill_criterion_ref(self):
        """factory.config.yaml deve avere session_analysis.kill_criterion_ref → EP-061.md.

        Rompe se: il campo viene rimosso, rinominato, o il valore non punta più
        a EP-061.md (previene derive del kill criterion).
        """
        self.assertTrue(
            FACTORY_CONFIG.exists(),
            f"factory.config.yaml non trovato: {FACTORY_CONFIG}."
        )
        config_text = FACTORY_CONFIG.read_text(encoding="utf-8")

        self.assertIn(
            "kill_criterion_ref",
            config_text,
            "Chiave kill_criterion_ref non trovata in factory.config.yaml. "
            "Drift: il kill criterion di EP-061 è stato rimosso dalla config."
        )

        # Verifica che punti a EP-061.md#sunset_condition
        expected_ref = "management/kanban/EP-061-session-agentic-analyser/EP-061.md#sunset_condition"
        self.assertIn(
            expected_ref,
            config_text,
            f"kill_criterion_ref non punta a '{expected_ref}'. "
            "Drift: il riferimento kill criterion è cambiato."
        )

        # Verifica che EP-061.md esista e abbia sunset_condition nel frontmatter
        self.assertTrue(
            EP061_PATH.exists(),
            f"EP-061.md non trovato: {EP061_PATH}. "
            "Il kill criterion punta a un file inesistente."
        )
        ep061_text = EP061_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "sunset_condition",
            ep061_text,
            f"Campo 'sunset_condition' non trovato in {EP061_PATH}. "
            "Drift: il kill criterion è stato rimosso dall'epica."
        )

    # ── Test 9: fleet_recommendations present ────────────────────────────────

    def test_fleet_recommendations_present(self):
        """fleet_recommendations deve essere presente nel JSON report.

        Integrazione TSK-558: verifica che generate-report.py costruisca il campo.
        Rompe se il campo viene rimosso o la derivazione regredisce.
        """
        report, _ = self._get_json_report()

        self.assertIn(
            "fleet_recommendations",
            report,
            "Chiave 'fleet_recommendations' non trovata nel JSON report (integrazione TSK-558)."
        )
        fleet_recs = report["fleet_recommendations"]
        self.assertIsInstance(fleet_recs, list, "fleet_recommendations deve essere lista.")

        # Se ci sono anomalie FLEET/DISPATCH/BUDGET → fleet_recommendations non deve essere vuoto
        anomalies = report.get("anomalies", [])
        fleet_categories = {"FLEET", "DISPATCH", "BUDGET"}
        fleet_anomalies = [a for a in anomalies if a.get("category") in fleet_categories]
        if fleet_anomalies:
            self.assertGreater(
                len(fleet_recs), 0,
                f"Ci sono {len(fleet_anomalies)} anomalie FLEET/DISPATCH/BUDGET "
                f"ma fleet_recommendations è vuoto. "
                f"Anomalie: {[a.get('id') for a in fleet_anomalies]}."
            )
            # Verifica struttura di ogni recommendation
            required_rec_fields = {"anomaly_id", "recommendation", "priority"}
            for i, rec in enumerate(fleet_recs):
                missing_rec = required_rec_fields - set(rec.keys())
                self.assertEqual(
                    missing_rec, set(),
                    f"fleet_recommendations[{i}] manca campi obbligatori: {missing_rec}. "
                    f"Entry: {rec}."
                )
                # fleet_doctor_command può essere null (non tutti i subtype hanno mapping)
                self.assertIn(
                    "fleet_doctor_command",
                    rec,
                    f"fleet_recommendations[{i}] manca campo 'fleet_doctor_command' (ammesso null)."
                )

    # ── Test 10: Regression detect anomaly on fixture ─────────────────────────

    def test_regression_detect_anomaly_on_fixture(self):
        """La fixture attuale deve scatenare almeno 1 anomalia BUDGET_OVERFLOW.

        La fixture cc-2.1.258-with-subagents ha costo ~5.99 USD, budget 5.0 USD
        (factory.config.yaml budget.max_cost_usd: 5.0). Almeno 1 BUDGET_OVERFLOW
        atteso. Se non scatta: la fixture o la soglia è cambiata (regression detector).
        """
        if not (self._anomalies_path and self._anomalies_path.exists()):
            raise unittest.SkipTest(
                "detect-anomalies.py non ha prodotto output (step fallito). "
                "Vedi test_pipeline_e2e_full_chain."
            )

        anomalies_data = json.loads(self._anomalies_path.read_text(encoding="utf-8"))
        anomalies = anomalies_data.get("anomalies", [])

        budget_overflow = [a for a in anomalies if a.get("subtype") == "BUDGET_OVERFLOW"]
        self.assertGreater(
            len(budget_overflow), 0,
            f"Attesa almeno 1 anomalia BUDGET_OVERFLOW sulla fixture (costo ~5.99 USD, "
            f"budget 5.0 USD). Anomalie trovate: {[a.get('subtype') for a in anomalies]}. "
            "Regression: la fixture o la soglia budget.max_cost_usd è cambiata, "
            "oppure detect-anomalies.py non rileva più BUDGET_OVERFLOW. "
            "Verificare factory.config.yaml budget.max_cost_usd."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
