#!/usr/bin/env node
// =============================================================================
// run-monte-carlo.ts — tool run_monte_carlo, runtime TypeScript opt-in (EP-010, US-041, TSK-073)
// =============================================================================
//
// ALTERNATIVA OPT-IN al default Python+numpy (run-monte-carlo.py). Attiva solo se
// analytics.estimation.monte_carlo.runtime: typescript. Stessa capability Task
// Analytics & Cost/Time Estimation (EP-010), stesso pattern [[thin-agents-fat-skills]]:
// è il TOOL (calcolo numerico deterministico, no LLM). Esegue il Monte Carlo
// throughput forecast (§Metodo 3) con `simple-statistics`, per factory JS-only.
//
// PATTERN.md §3 — operazione canonica opzionale «Monte Carlo Throughput».
// Wiki: wiki/concepts/task-analytics-cost-estimation-capability.md
//       [[task-analytics-cost-estimation-capability]] §Stima enterprise.
//       wiki/syntheses/task-analytics-estimation-methods.md §Metodo 3.
// ADR-026 §C — runtime TS opt-in con `simple-statistics`: cap soft 5000 iterazioni
//       (warning sopra), cap hard 50000 (fail-loud sopra), histogram a 50 bin,
//       fail-loud canonico se `simple-statistics` assente. §F `--seed` per
//       riproducibilità. Schema output equivalente al .py entro 5% di drift.
//
// INVARIANTE «mai numero puntuale»: output sempre percentili p50/p85/p95, mai mean.
// OPT-IN / R.P3: no-op a capability spenta; assenza del file non produce ERROR lint.
//
// CONTRATTO INPUT (CLI):  identico a run-monte-carlo.py
//   --throughput-samples '<JSON list>'   required
//   --backlog <int>                       required, >0
//   --iterations <int>                    default 5000 (cap soft TS, ADR-026 §C)
//   --week-count-cap <int>                default 520
//   --seed <int>                          opzionale; default random
//   --config <path>                       default "factory.config.yaml" (no-op check)
//
// CONTRATTO OUTPUT (stdout, JSON): schema equivalente al .py.
// EXIT CODES: 0 ok | 1 input/cap-hard/no-op | 2 dipendenza mancante (simple-statistics).
// =============================================================================

import * as fs from "fs";

// --- Fail-loud simple-statistics (ADR-026 §C) ------------------------------
let ss: any;
try {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  ss = require("simple-statistics");
} catch {
  process.stderr.write(
    "ERROR: simple-statistics non installato. Install:\n" +
      "  npm install --save-dev simple-statistics\n" +
      "Vedi ADR-026 §C.\n"
  );
  process.exit(2);
}

const TS_MAX_ITERATIONS_SOFT = 5000; // warning sopra
const TS_MAX_ITERATIONS_HARD = 50000; // fail-loud sopra
const HISTOGRAM_BINS = 50; // ADR-026 §C: risoluzione ridotta vs Python

function die(msg: string, code = 1): never {
  process.stderr.write(msg.replace(/\n+$/, "") + "\n");
  process.exit(code);
}

function parseArgs(argv: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) {
        out[key] = "true";
      } else {
        out[key] = next;
        i++;
      }
    }
  }
  return out;
}

// R.P3 / ADR-026 §G: no-op a capability spenta (parsing minimale tollerante).
function checkNoOp(configPath: string): void {
  if (!configPath || !fs.existsSync(configPath)) return;
  let text: string;
  try {
    text = fs.readFileSync(configPath, "utf-8");
  } catch {
    return;
  }
  let inAnalytics = false;
  let inEstimation = false;
  let enabled: boolean | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.split("#")[0].replace(/\s+$/, "");
    if (!line.trim()) continue;
    const indent = line.length - line.trimStart().length;
    const stripped = line.trim();
    if (indent === 0) {
      inAnalytics = stripped.startsWith("analytics:");
      inEstimation = false;
      continue;
    }
    if (inAnalytics && stripped.startsWith("estimation:")) {
      inEstimation = true;
      continue;
    }
    if (inAnalytics && inEstimation && stripped.startsWith("enabled:")) {
      const val = stripped.split(":")[1].trim().toLowerCase();
      enabled = ["true", "yes", "on", "1"].includes(val);
      break;
    }
    if (inEstimation && indent <= 2 && !stripped.startsWith("enabled:")) {
      inEstimation = false;
    }
  }
  if (enabled === false) {
    die(
      `Monte Carlo no-op: analytics.estimation.enabled=false in ${configPath}. ` +
        "Attivare la capability (analytics.estimation.enabled: true) o invocare " +
        "con un config diverso. Vedi ADR-026 §G / R.P3.",
      1
    );
  }
}

// PRNG deterministico (mulberry32) seedabile — ADR-026 §F.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));
  const configPath = args["config"] ?? "factory.config.yaml";
  checkNoOp(configPath);

  if (!args["throughput-samples"]) {
    die("ERROR: --throughput-samples richiesto. Es. '[1,2,3,2,4]'.");
  }
  if (!args["backlog"]) {
    die("ERROR: --backlog richiesto (intero > 0).");
  }

  let throughput: number[];
  try {
    throughput = JSON.parse(args["throughput-samples"]);
  } catch (e) {
    die(`ERROR: --throughput-samples non è JSON valido: ${e}. Atteso una lista, es. '[1,2,3,2,4]'.`);
  }
  if (!Array.isArray(throughput!) || throughput!.length === 0) {
    die("ERROR: --throughput-samples deve essere una lista non vuota di numeri.");
  }
  if (!throughput!.every((x) => typeof x === "number" && isFinite(x))) {
    die("ERROR: --throughput-samples deve contenere solo numeri.");
  }
  if (throughput!.some((x) => x < 0)) {
    die("ERROR: --throughput-samples non può contenere valori negativi.");
  }
  if (throughput!.every((x) => x === 0)) {
    die(
      "ERROR: --throughput-samples tutto a zero: throughput nullo, backlog mai " +
        "completabile. Fornire almeno un valore > 0."
    );
  }

  const backlog = parseInt(args["backlog"], 10);
  if (!Number.isInteger(backlog) || backlog <= 0) {
    die("ERROR: --backlog deve essere un intero positivo (> 0).");
  }
  let iterations = args["iterations"] ? parseInt(args["iterations"], 10) : TS_MAX_ITERATIONS_SOFT;
  if (!Number.isInteger(iterations) || iterations <= 0) {
    die("ERROR: --iterations deve essere un intero positivo (> 0).");
  }
  const weekCap = args["week-count-cap"] ? parseInt(args["week-count-cap"], 10) : 520;
  if (!Number.isInteger(weekCap) || weekCap <= 0) {
    die("ERROR: --week-count-cap deve essere un intero positivo (> 0).");
  }

  // Cap hard / soft (ADR-026 §C).
  if (iterations > TS_MAX_ITERATIONS_HARD) {
    die(
      `ERROR: Monte Carlo TS runtime non supporta N>${TS_MAX_ITERATIONS_HARD} iterations ` +
        "(richiesto: " +
        iterations +
        "); switch a runtime: python. Vedi ADR-026 §C.",
      1
    );
  }
  if (iterations > TS_MAX_ITERATIONS_SOFT) {
    process.stderr.write(
      `WARNING: --iterations ${iterations} supera il cap soft TS (${TS_MAX_ITERATIONS_SOFT}); ` +
        "performance degradate. Per N alti usare runtime: python. Vedi ADR-026 §C.\n"
    );
  }

  // Seed sempre presente (ADR-026 §F).
  const seed =
    args["seed"] !== undefined ? parseInt(args["seed"], 10) : (Math.random() * 0xffffffff) >>> 0;
  const rand = mulberry32(seed);

  const start = process.hrtime.bigint();
  const weeksNeeded: number[] = new Array(iterations);
  const n = throughput!.length;
  for (let it = 0; it < iterations; it++) {
    let completed = 0;
    let week = 0;
    while (completed < backlog && week < weekCap) {
      week++;
      completed += throughput![Math.floor(rand() * n)];
    }
    weeksNeeded[it] = week;
  }
  const durationMs = Number((process.hrtime.bigint() - start) / 1000000n);

  const p50 = Math.round(ss.quantileSorted([...weeksNeeded].sort((a, b) => a - b), 0.5));
  const sorted = [...weeksNeeded].sort((a, b) => a - b);
  const pct = (q: number) => Math.round(ss.quantileSorted(sorted, q));

  const maxWeek = Math.max(...weeksNeeded);
  const counts = new Array(maxWeek + 1).fill(0);
  for (const w of weeksNeeded) counts[w]++;
  const histogram: { week: number; count: number }[] = [];
  for (let w = 1; w <= maxWeek; w++) {
    if (counts[w] > 0) histogram.push({ week: w, count: counts[w] });
  }
  // Nota: HISTOGRAM_BINS documenta la risoluzione ridotta TS (ADR-026 §C); per
  // distribuzioni in settimane intere usiamo i bin nativi (≤ maxWeek).
  void HISTOGRAM_BINS;
  void p50;

  const result = {
    iterations,
    backlog,
    percentiles: {
      duration_weeks: { p50: pct(0.5), p85: pct(0.85), p95: pct(0.95) },
    },
    distribution: {
      histogram,
      bins: histogram.map((h) => h.week),
    },
    metadata: {
      runtime: `node-${process.versions.node}`,
      simple_statistics: (ss as any).version ?? "unknown",
      duration_ms: durationMs,
      seed,
    },
  };

  process.stdout.write(JSON.stringify(result) + "\n");
}

main();
