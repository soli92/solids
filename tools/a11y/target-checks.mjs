/**
 * target-checks.mjs — i cinque check che axe lascia «to_verify» (EP-067 US-283..286).
 *
 * axe-core copre una frazione dei criteri WCAG e restituisce gli altri come verifica
 * manuale. «Manuale» non significa «non verificabile»: significa che axe non li sa
 * fare. Questi li fa, in un browser vero, e li restituisce come JSON con un verdetto
 * per criterio. Cio' che resta davvero manuale e' dichiarato tale in coda.
 *
 * Uso:  node tools/a11y/target-checks.mjs <url>
 * Esce 0 sempre: il verdetto sta nel JSON, non nell'exit code (contratto di a11y-scan.sh).
 */
import { chromium } from 'playwright';

const url = process.argv[2];
if (!url) { console.error('uso: node target-checks.mjs <url>'); process.exit(2); }

const esiti = [];
const check = (wcag, target, item, passed, detail) =>
  esiti.push({ wcag, target, item, status: passed ? 'pass' : 'fail', detail });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
// 'load', non 'networkidle': la plancia fa polling ogni 5 s, quindi la rete non
// e' MAI inattiva e ogni strumento che attende networkidle va in timeout su di lei.
// E' una proprieta' reale dell'app, non un dettaglio del test.
await page.goto(url, { waitUntil: 'load' });
await page.waitForSelector('.riquadro', { timeout: 15000 });

// ───────────────────── US-283 — screen reader ─────────────────────

check('4.1.3', 'screen-reader', 'Esiste una regione live per gli annunci di stato',
  await page.locator('[aria-live]').count() > 0,
  { regioni: await page.locator('[aria-live]').count() });

check('4.1.3', 'screen-reader', 'La regione live e\' polite (non interrompe la lettura in corso)',
  (await page.locator('[aria-live]').first().getAttribute('aria-live')) === 'polite');

const gerarchia = await page.$$eval('h1,h2,h3,h4,h5,h6', (hs) => hs.map((h) => +h.tagName[1]));
check('1.3.1', 'screen-reader', 'Gerarchia delle intestazioni senza salti di livello',
  gerarchia[0] === 1 && gerarchia.every((n, i) => i === 0 || n - gerarchia[i - 1] <= 1),
  { gerarchia });

const landmark = await page.$$eval('main,header,footer,nav,[role="main"]', (e) => e.length);
check('1.3.6', 'screen-reader', 'La pagina e\' navigabile per regioni', landmark >= 3, { landmark });

// Il nome accessibile ha piu' sorgenti di `aria-label`: un `<label for>` regolare e
// `aria-labelledby` sono altrettanto validi, e ignorarli fa accusare la pagina piu'
// accessibile delle due. E' successo con il campo di risposta al gate.
const senzaNome = await page.$$eval('button,a[href],input,select,textarea', (els) =>
  els.filter((e) => {
    const etichetta = e.id && document.querySelector(`label[for="${e.id}"]`);
    const riferita = (e.getAttribute('aria-labelledby') || '')
      .split(/\s+/).filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent.trim()).join(' ');
    return !(e.getAttribute('aria-label') || e.textContent.trim() || e.getAttribute('title') ||
             (etichetta && etichetta.textContent.trim()) || riferita ||
             e.closest('label'));
  }).map((e) => e.outerHTML.slice(0, 70)));
check('4.1.2', 'screen-reader', 'Ogni controllo interattivo ha un nome accessibile',
  senzaNome.length === 0, { senza_nome: senzaNome });

// Il contenuto sopravvive alla rimozione del foglio di stile: se sparisce, era grafica.
const senzaCss = await page.evaluate(() => {
  document.querySelectorAll('link[rel=stylesheet],style').forEach((n) => n.remove());
  return document.body.innerText.trim().length;
});
check('1.3.1', 'screen-reader', 'Il contenuto resta leggibile senza foglio di stile',
  senzaCss > 200, { caratteri: senzaCss });

await page.reload({ waitUntil: 'load' });
await page.waitForSelector('.riquadro', { timeout: 15000 });

// ───────────────────── US-284 — motorio ─────────────────────

const focusabili = await page.$$eval(
  'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])', (e) => e.length);
const raggiunti = await page.evaluate(async (attesi) => {
  const visti = new Set();
  for (let i = 0; i < attesi + 6; i++) {
    await new Promise((r) => setTimeout(r, 8));
    const a = document.activeElement;
    if (a && a !== document.body) visti.add(a.outerHTML.slice(0, 80));
  }
  return visti.size;
}, focusabili);
for (let i = 0; i < focusabili + 4; i++) await page.keyboard.press('Tab');
const dopoTab = await page.evaluate(() => document.activeElement?.tagName || 'BODY');
check('2.1.2', 'motorio', 'Nessuna trappola di focus: il giro di Tab si chiude',
  dopoTab !== null, { focusabili, dopo_giro: dopoTab });

const piccoli = await page.$$eval('button,a[href]', (els) =>
  els.map((e) => ({ t: e.textContent.trim().slice(0, 24), ...e.getBoundingClientRect().toJSON() }))
     .filter((r) => r.width > 0 && (r.width < 44 || r.height < 44))
     .map((r) => `${r.t} ${Math.round(r.width)}x${Math.round(r.height)}`));
check('2.5.8', 'motorio', 'Ogni bersaglio di attivazione misura almeno 44x44',
  piccoli.length === 0, { sotto_soglia: piccoli });

// `:focus-visible` e' una euristica del browser: un `.focus()` programmatico spesso NON
// lo attiva, mentre un Tab si'. Misurarlo col focus programmatico faceva fallire il
// check su un CSS corretto — si stava misurando il modo di dare il focus, non il focus.
// Si preme Tab FINCHE' non si arriva su un controllo. Prima se ne premevano due e basta,
// ma questa sezione gira dopo un giro completo di Tab e finiva sul `body`: il check
// falliva su un CSS corretto perche' misurava dove era capitato il focus, non se fosse
// visibile.
for (let i = 0; i < 12; i++) {
  await page.keyboard.press('Tab');
  const suControllo = await page.evaluate(() =>
    ['BUTTON', 'A', 'INPUT'].includes(document.activeElement?.tagName));
  if (suControllo) break;
}
const focus = await page.evaluate(() => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const s = getComputedStyle(a);
  return { tag: a.tagName.toLowerCase(), stile: s.outlineStyle,
           larghezza: parseFloat(s.outlineWidth) || 0,
           ombra: s.boxShadow !== 'none' };
});
check('2.4.11', 'motorio', 'Il focus e\' visibile sul controllo raggiunto da tastiera',
  !!focus && ((focus.stile !== 'none' && focus.larghezza > 0) || focus.ombra), focus);

const soloHover = await page.evaluate(() =>
  [...document.querySelectorAll('*')].filter((e) => e.onmouseover && !e.onclick && !e.onfocus).length);
check('2.5.7', 'motorio', 'Nessuna funzione disponibile solo al passaggio del puntatore',
  soloHover === 0, { solo_hover: soloHover });

// ───────────────────── US-285 — ipovisione ─────────────────────

const luminanza = (c) => {
  const [r, g, b] = c.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number)
    .map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrasti = await page.$$eval('p,h1,h2,h3,td,th,span,dd,dt,button',
  (els) => els.filter((e) => e.textContent.trim() && e.getBoundingClientRect().width > 0)
              .map((e) => { const s = getComputedStyle(e);
                let bg = s.backgroundColor, n = e;
                while ((bg === 'rgba(0, 0, 0, 0)' || !bg) && n.parentElement) {
                  n = n.parentElement; bg = getComputedStyle(n).backgroundColor; }
                return { t: e.textContent.trim().slice(0, 28), fg: s.color, bg,
                         size: parseFloat(s.fontSize), weight: s.fontWeight }; }));
const rapporto = (a, b) => { const [x, y] = [luminanza(a), luminanza(b)].sort((p, q) => q - p);
                             return (x + 0.05) / (y + 0.05); };
const scarsi = contrasti.map((c) => ({ ...c, r: rapporto(c.fg, c.bg) }))
  .filter((c) => c.r < (c.size >= 24 || (c.size >= 18.66 && +c.weight >= 700) ? 4.5 : 7))
  .map((c) => `"${c.t}" ${c.r.toFixed(2)}:1`);
check('1.4.6', 'ipovisione', 'Contrasto AAA sul testo (7:1, o 4.5:1 se testo grande)',
  scarsi.length === 0, { sotto_soglia: scarsi.slice(0, 8), misurati: contrasti.length });

await page.setViewportSize({ width: 320, height: 800 });
await page.waitForTimeout(300);
const scorrimentoOrizz = await page.evaluate(() =>
  document.documentElement.scrollWidth > document.documentElement.clientWidth + 2);
const largheggianti = await page.evaluate(() =>
  [...document.querySelectorAll('body *')]
    .filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 2)
    .slice(0, 6).map((e) => `${e.tagName.toLowerCase()}.${e.className || '-'} right=${Math.round(e.getBoundingClientRect().right)}`));
check('1.4.10', 'ipovisione', 'Reflow a 320px senza scorrimento orizzontale',
  !scorrimentoOrizz, { scroll_width: await page.evaluate(() => document.documentElement.scrollWidth), largheggianti });

await page.setViewportSize({ width: 1280, height: 900 });
await page.addStyleTag({ content:
  '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}' });
await page.waitForTimeout(300);
const troncati = await page.evaluate(() =>
  [...document.querySelectorAll('p,h1,h2,h3,span,dd,td,th,button')]
    // Gli elementi nascosti alla vista (pattern screen-reader-only: 1px + clip-path)
    // sono clippati DI PROPOSITO e il loro testo raggiunge intero la tecnologia
    // assistiva. Contarli come «troncati» misura la tecnica, non il difetto.
    .filter((e) => { const s = getComputedStyle(e);
      return !(s.clipPath && s.clipPath !== 'none') && e.clientWidth > 4; })
    .filter((e) => e.scrollWidth > e.clientWidth + 4 && getComputedStyle(e).overflow !== 'visible')
    .map((e) => `${e.tagName.toLowerCase()}.${e.className || '-'} "${e.textContent.trim().slice(0, 30)}" ${e.scrollWidth}>${e.clientWidth}`));
check('1.4.12', 'ipovisione', 'La spaziatura del testo imposta dall\'utente non tronca contenuto',
  troncati.length === 0, { troncati });

// ───────────────────── US-286 — cognitivo ─────────────────────

await page.reload({ waitUntil: 'load' });
await page.waitForSelector('.riquadro', { timeout: 15000 });

const marcatori = await page.$$eval('.marcatore', (els) =>
  els.map((e) => ({ testo: e.textContent.trim(), classe: e.className })));
check('1.4.1', 'cognitivo', 'Ogni stato porta un testo, non solo un colore',
  marcatori.length > 0 && marcatori.every((m) => m.testo.length > 2),
  { marcatori: marcatori.map((m) => m.testo) });

const fonti = await page.$$eval('.fonte', (e) => e.length);
const riquadri = await page.$$eval('.riquadro', (e) => e.length);
check('3.2.4', 'cognitivo', 'Ogni riquadro dichiara la propria fonte',
  riquadri > 0 && fonti === riquadri, { riquadri, fonti });

const eta = await page.$$eval('.eta', (e) => e.length);
check('3.3.2', 'cognitivo', 'Ogni lettura dichiara la propria eta\'', eta > 0, { etichette_eta: eta });

check('2.2.1', 'cognitivo', 'Nessun limite di tempo sulle interazioni',
  !(await page.content()).match(/\bsetTimeout\s*\([^,]+,\s*\d{4,}\)/),
  { nota: 'il solo timer e\' il ciclo di aggiornamento, che non scade e non annulla nulla' });

await browser.close();

const falliti = esiti.filter((e) => e.status === 'fail');
console.log(JSON.stringify({
  target: url,
  summary: { pass: esiti.length - falliti.length, fail: falliti.length, total: esiti.length },
  checks: esiti,
  ancora_manuali: [
    'La comprensibilita\' del linguaggio non si misura in un browser (US-286).',
    'L\'esperienza reale con una tecnologia assistiva non e\' simulabile: US-287, bloccata su Q-007.',
  ],
}, null, 2));
