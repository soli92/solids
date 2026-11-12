/**
 * Iniziali di un nome per l'AvatarFallback.
 *
 * Lavora sui grafemi (Intl.Segmenter), non sui code unit: un'emoji, una sequenza
 * ZWJ o una lettera con segni combinati contano come un solo carattere.
 * Senza Intl.Segmenter ricade su Array.from (code point).
 * Restituisce "" se il nome e' vuoto: il fallback ("?", icona) lo sceglie il chiamante.
 */
const segmenter =
  typeof Intl !== "undefined" && "Segmenter" in Intl
    ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
    : null

function graphemes(text: string): string[] {
  return segmenter
    ? Array.from(segmenter.segment(text), (s) => s.segment)
    : Array.from(text)
}

function isLetterLike(g: string): boolean {
  return /[\p{L}\p{N}\p{Extended_Pictographic}]/u.test(g)
}

export function getInitials(nome: string, max = 2): string {
  const parole = (nome ?? "").trim().split(/\s+/).filter(Boolean)
  const iniziali: string[] = []
  for (const parola of parole) {
    const primo = graphemes(parola).find(isLetterLike)
    if (primo) iniziali.push(primo)
  }
  let out = iniziali
  // Una sola parola senza spazi (es. CJK): le prime lettere stesse.
  if (out.length === 1 && max > 1) {
    out = graphemes(parole.find((p) => graphemes(p).some(isLetterLike)) ?? "")
      .filter(isLetterLike)
      .slice(0, max)
  }
  return out.slice(0, max).join("").toLocaleUpperCase()
}
