// node scripts/initials-test.mjs
import assert from "node:assert/strict"
import { getInitials } from "../src/lib/initials.ts"

const casi = [
  ["Anna Rossi", "AR"],
  ["  Sam   Lee ", "SL"],
  ["🦊 Volpe", "🦊V"],
  ["A", "A"],
  ["王秀英", "王秀"],
  ["نور الهدى عبد الرحمن", "نا"],
  ["Đặng Thị Ngọc Hân", "ĐT"],
  ["👩‍👩‍👧 Famiglia", "👩‍👩‍👧F"],
  ["", ""],
  ["   ", ""],
]
for (const [nome, atteso] of casi) assert.equal(getInitials(nome), atteso, nome)
assert.equal(getInitials("Anna Maria Rossi", 3), "AMR")
assert.equal(getInitials("Anna Rossi", 1), "A")
console.log("initials: ok")
