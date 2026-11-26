// node scripts/scaffold-test.mjs — logica pura del drag handle (dist/scaffold, dopo npm run build)
import assert from "node:assert/strict";
import { clampWidth, snapWidth, keyboardWidth, M3_PANE_SNAP_WIDTHS } from "../dist/scaffold/index.js";

assert.deepEqual([...M3_PANE_SNAP_WIDTHS], [360, 412], "larghezze di aggancio M3");

assert.equal(clampWidth(100, 240, 640), 240);
assert.equal(clampWidth(900, 240, 640), 640);
assert.equal(clampWidth(400.4, 240, 640), 400);

// aggancio entro la soglia, al piu' vicino; fuori soglia resta il valore
assert.equal(snapWidth(350, [360, 412], 24), 360);
assert.equal(snapWidth(390, [360, 412], 24), 412); // 30 da 360, 22 da 412
assert.equal(snapWidth(386, [360, 412], 24), 386); // 26 da entrambi: fuori soglia
assert.equal(snapWidth(500, [360, 412], 24), 500);
assert.equal(snapWidth(385, [360, 412], 24), 385); // 25 / 27: nessuno entro 24
assert.equal(snapWidth(384, [360, 412], 24), 360); // 24 da 360: entro la soglia

const k = { min: 240, max: 640, step: 8, shift: false, side: "start", rtl: false };
assert.equal(keyboardWidth("ArrowRight", 360, k), 368, "pannello a inizio: destra allarga");
assert.equal(keyboardWidth("ArrowLeft", 360, k), 352);
assert.equal(keyboardWidth("ArrowRight", 360, { ...k, shift: true }), 400, "Shift: passo x5");
assert.equal(keyboardWidth("ArrowRight", 360, { ...k, side: "end" }), 352, "pannello a fine: destra stringe");
assert.equal(keyboardWidth("ArrowRight", 360, { ...k, rtl: true }), 352, "RTL: le frecce si invertono");
assert.equal(keyboardWidth("Home", 360, k), 240);
assert.equal(keyboardWidth("End", 360, k), 640);
assert.equal(keyboardWidth("ArrowRight", 636, k), 640, "limite massimo");
assert.equal(keyboardWidth("Tab", 360, k), null, "tasti che non ridimensionano");

console.log("scaffold: ok");
