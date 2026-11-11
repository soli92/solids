// report.mjs — Rendering markdown del verdetto (verdict.md). Puro.

const ICON = { pass: 'ok', fail: 'NO', missing: '?', partial: '~', 'n/a': '-' };

export function renderVerdictMarkdown(v) {
  const k = v.kpi;
  const lines = [];
  lines.push(`# Verifica di migrazione — ${v.repos.a} -> ${v.repos.b}`);
  lines.push('');
  lines.push(`- **verdetto:** \`${v.verdict}\``);
  lines.push(`- **generato:** ${v.meta.generatedAt} · plugin ${v.meta.plugins.join('+')} · join ${v.joinStrategy}`);
  lines.push(`- **punto di fork:** ${v.forkPoint.commit ?? v.forkPoint.date ?? 'non fornito (input umano)'}`);
  lines.push(
    `- **parity_ratio:** ${k.observed ? `${k.parity_ratio.toFixed(3)} (soglia ${k.threshold}, copertura ${(k.coverage * 100).toFixed(0)}%)` : `non osservato — ${k.reason}`}`,
  );
  lines.push(`- **asse C:** ${v.inputs.census}`);
  lines.push(`- **registro dei debiti:** ${v.inputs.debt}`);
  lines.push('');
  const s = v.summary;
  lines.push(`File: ${s.files} · consolidated ${s.consolidated} · conditional ${s.conditional} · reject ${s.reject} · gate umano ${s.gated} · da portare ${s.porting} · solo nel target ${s.onlyInB}`);
  lines.push('');
  if (v.global.length) {
    lines.push('## Condizioni globali');
    for (const g of v.global) lines.push(`- \`${g.state}\` — ${g.reason}`);
    lines.push('');
  }
  if (v.gates.length) {
    lines.push('## Gate umani aperti');
    lines.push('');
    lines.push('Il verificatore si ferma qui: ogni gate richiede una decisione umana esplicita.');
    lines.push('');
    lines.push('```json');
    lines.push(JSON.stringify(v.gates, null, 2));
    lines.push('```');
    lines.push('');
  }
  lines.push('## Per file (ordine bottom-up)');
  lines.push('');
  lines.push('| file | partizione | ramo | debito | modo | parita\' | verdetto | ragioni |');
  lines.push('|---|---|---|:-:|:-:|:-:|---|---|');
  for (const r of v.files) {
    const g = r.gates;
    const name = r.oracleFile ? `${r.file} (oracolo: ${r.oracleFile})` : r.file;
    lines.push(
      `| \`${name}\` | ${r.partition} | ${r.route} | ${ICON[g.debt.state]} | ${ICON[g.mode.state]} | ${ICON[g.parity.state]} | **${r.verdict}** | ${r.reasons.join('; ').replace(/\|/g, '\\|')} |`,
    );
  }
  if (v.onlyInB.length) {
    lines.push('');
    lines.push('## Solo nel target (nuovo o orfano: verifica esplicita, non un verdetto)');
    for (const f of v.onlyInB) lines.push(`- \`${f}\``);
  }
  lines.push('');
  lines.push('Legenda: ok verde · NO rosso bloccante · ? non osservato (mai un verde) · ~ parziale · - non applicabile.');
  lines.push('');
  return lines.join('\n');
}
