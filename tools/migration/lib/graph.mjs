// graph.mjs — Grafo degli import: cicli, profondita', ordine bottom-up. Puro, senza I/O.

/**
 * @param {string[]} nodes            chiavi ordinate
 * @param {Map<string,string[]>} edges nodo -> importati (solo nodi del grafo)
 * @param {string[]} [starts]          radici di visita preferite (entry point)
 * @returns {{ depth: Map<string,number>, cycles: string[], roots: string[], bottomUp: string[], usedBy: Map<string,string[]> }}
 */
export function analyzeGraph(nodes, edges, starts = []) {
  const usedBy = new Map(nodes.map((n) => [n, []]));
  for (const [from, tos] of edges) for (const to of tos) usedBy.get(to)?.push(from);
  for (const list of usedBy.values()) list.sort();

  const roots = nodes.filter((n) => (usedBy.get(n) ?? []).length === 0);

  // DFS iterativa (colori) per individuare gli archi all'indietro.
  const color = new Map(); // undefined bianco, 1 grigio, 2 nero
  const back = new Set(); // "from\0to"
  const cycleNodes = new Set();
  const order = [...new Set([...starts, ...roots, ...nodes])];
  for (const s of order) {
    if (color.get(s)) continue;
    const stack = [[s, 0]];
    color.set(s, 1);
    while (stack.length) {
      const top = stack[stack.length - 1];
      const [node, i] = top;
      const kids = edges.get(node) ?? [];
      if (i < kids.length) {
        top[1]++;
        const k = kids[i];
        const c = color.get(k);
        if (c === 1) {
          back.add(`${node}\0${k}`);
          cycleNodes.add(k);
          if (k === node) cycleNodes.add(node);
        } else if (!c) {
          color.set(k, 1);
          stack.push([k, 0]);
        }
      } else {
        color.set(node, 2);
        stack.pop();
      }
    }
  }

  // Profondita' = cammino piu' lungo da una radice sul DAG (archi all'indietro rimossi).
  const indeg = new Map(nodes.map((n) => [n, 0]));
  for (const [from, tos] of edges) {
    for (const to of tos) if (!back.has(`${from}\0${to}`)) indeg.set(to, indeg.get(to) + 1);
  }
  const depth = new Map();
  const queue = nodes.filter((n) => indeg.get(n) === 0);
  for (const n of queue) depth.set(n, 1);
  for (let qi = 0; qi < queue.length; qi++) {
    const n = queue[qi];
    for (const k of edges.get(n) ?? []) {
      if (back.has(`${n}\0${k}`)) continue;
      depth.set(k, Math.max(depth.get(k) ?? 0, depth.get(n) + 1));
      indeg.set(k, indeg.get(k) - 1);
      if (indeg.get(k) === 0) queue.push(k);
    }
  }
  for (const n of nodes) if (!depth.has(n)) depth.set(n, 1); // difensivo: non dovrebbe accadere

  const bottomUp = [...nodes].sort((a, b) => depth.get(b) - depth.get(a) || (a < b ? -1 : a > b ? 1 : 0));
  return { depth, cycles: [...cycleNodes].sort(), roots, bottomUp, usedBy };
}
