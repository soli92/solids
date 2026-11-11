/**
 * Fixture per la story «Lista membri» (/worst-case, kowalski-worst-case-data).
 * Stessa forma per ogni dataset; il caso peggiore e' una fixture accanto alla demo.
 * Solo nomi inventati, domini .example/.test (catalogo.md).
 */
export type StatoMembro = "attivo" | "invitato" | "scaduto" | "sospeso";

export type Membro = {
  id: string;
  nome?: string;
  email: string;
  ruolo?: string;
  stato: StatoMembro;
  avatarUrl?: string;
  /** Giorni dall'ultimo accesso (null = mai). */
  ultimoAccessoGiorni: number | null;
};

export type DatiModalita = "demo" | "peggiore" | "vuoto" | "uno" | "mille";
export const MODALITA: DatiModalita[] = ["demo", "peggiore", "vuoto", "uno", "mille"];

/** Panorama 4000x200 come data URI: prova object-fit senza rete. */
const PANORAMA =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="4000" height="200" viewBox="0 0 4000 200"><rect width="4000" height="200" fill="#c4b5fd"/><circle cx="200" cy="100" r="80" fill="#4c1d95"/><rect x="3700" y="20" width="200" height="160" fill="#be123c"/></svg>`
  );

export const demo: Membro[] = [
  { id: "d1", nome: "Anna Rossi", email: "anna.rossi@acme.example", ruolo: "Designer", stato: "attivo", ultimoAccessoGiorni: 0 },
  { id: "d2", nome: "Luca Bianchi", email: "luca.bianchi@acme.example", ruolo: "Sviluppatore", stato: "attivo", ultimoAccessoGiorni: 2 },
  { id: "d3", nome: "Sara Verdi", email: "sara.verdi@acme.example", ruolo: "Product manager", stato: "invitato", ultimoAccessoGiorni: null },
  { id: "d4", nome: "Marco Neri", email: "marco.neri@acme.example", ruolo: "QA", stato: "attivo", ultimoAccessoGiorni: 5 },
];

/** Righe distribuite sulle prime posizioni (regola 3). */
export const peggiore: Membro[] = [
  { id: "p1", nome: "Maria Grazia D'Alessandro-Wiśniewska", email: "bartolomeo.fitzgerald@industrie-meccaniche-riunite-holding.example", ruolo: "Responsabile Senior Sviluppo Prodotto, Infrastrutture di Piattaforma", stato: "invitato", avatarUrl: PANORAMA, ultimoAccessoGiorni: 12 },
  { id: "p2", nome: "Giovanni Battista Montefalcone di San Severino", email: "amministrazione.contabilita@studio-associato-rossi-bianchi-e-verdi.pec.example", stato: "scaduto", avatarUrl: "https://avatar.example/404.png", ultimoAccessoGiorni: 1284 },
  { id: "p3", nome: "A", email: "a@b.test", ruolo: "QA", stato: "attivo", ultimoAccessoGiorni: 0 },
  { id: "p4", email: "nome.cognome+fatture-notifiche@example.org", stato: "sospeso", ultimoAccessoGiorni: null },
  { id: "p5", nome: "🦊 Volpe", email: "ops@sub.reparto.regione.example.co.uk", ruolo: "Benachrichtigungseinstellungen", stato: "attivo", ultimoAccessoGiorni: 3 },
  { id: "p6", nome: "王秀英", email: "wang.xiuying@example.test", ruolo: "设计师", stato: "attivo", ultimoAccessoGiorni: 7 },
  { id: "p7", nome: "نور الهدى عبد الرحمن", email: "nour@example.test", ruolo: "مهندسة برمجيات", stato: "attivo", ultimoAccessoGiorni: 1 },
  { id: "p8", nome: "Đặng Thị Ngọc Hân", email: "dang.han@example.test", ruolo: "Designer", stato: "attivo", ultimoAccessoGiorni: 400 },
  { id: "p9", nome: "  Sam   Lee ", email: "sam@example.test", ruolo: "Senza titolo", stato: "attivo", ultimoAccessoGiorni: 1 },
  { id: "p10", nome: "<script>alert(1)</script> & **grassetto**", email: "escape@example.test", ruolo: "&amp;", stato: "attivo", ultimoAccessoGiorni: 1 },
  { id: "p11", nome: "Anna Rossi", email: "anna.rossi@acme.example", ruolo: "Designer", stato: "attivo", ultimoAccessoGiorni: 0 },
  { id: "p12", nome: "Anna Rossi", email: "anna.rossi@acme.example", ruolo: "Designer", stato: "attivo", ultimoAccessoGiorni: 0 },
];

export const uno: Membro[] = [demo[0]];

export const vuoto: Membro[] = [];

/** 1.284 righe non paginate: ciclo del caso peggiore con id e conteggio unici. */
export const mille: Membro[] = Array.from({ length: 1284 }, (_, i) => ({
  ...peggiore[i % peggiore.length],
  id: `m${i}`,
}));

export function dati(modalita: DatiModalita): Membro[] {
  switch (modalita) {
    case "peggiore": return peggiore;
    case "vuoto": return vuoto;
    case "uno": return uno;
    case "mille": return mille;
    default: return demo;
  }
}
