"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { createHash } = require("node:crypto");
const M = require("../analise_sentimentos/web/bertweet_metrics");
const { readDashboard } = require("../scripts/bertweet_dashboard");

function row(lula, flavio, extra = {}) {
  return { text: "exemplo", label: "positivo", confidence: 0.9, lula, flavio,
    block: "Bloco 1", paid: false, emojis: [], irony_cues: [], ...extra };
}

test("termômetro exclui neutras, incertas e sem referência do denominador", () => {
  const rows = [row("positivo", "sem_referencia"), row("negativo", "sem_referencia"),
    row("positivo", "sem_referencia"), row("neutro", "sem_referencia"),
    row("incerto", "incerto"), row("sem_referencia", "incerto")];
  const lula = M.candidate(rows, "lula");
  assert.equal(lula.mentions, 5);
  assert.equal(lula.polarized, 3);
  assert.ok(Math.abs(lula.score - 100 / 3) < 1e-9);
  assert.equal(M.candidate(rows, "flavio").score, null);
});

test("painel preserva os rótulos publicados sem novo corte de probabilidade", () => {
  const rows = [row("positivo", "sem_referencia", { confidence: 0.65 }), row("incerto", "incerto")];
  const before = structuredClone(rows);
  assert.equal(M.candidate(rows, "lula").positivo, 1);
  assert.equal(M.candidate(rows, "lula").incerto, 1);
  assert.equal(M.candidate(rows, "flavio").sem_referencia, 1);
  assert.deepEqual(rows, before);
});

test("experimental nunca entra no painel; filtros mantêm mensagens com pistas de ironia", () => {
  const rows = [row("positivo", "sem_referencia"), row("positivo", "sem_referencia", { block: "1 parte" }),
    row("positivo", "sem_referencia", { paid: true }), row("incerto", "incerto", { emojis: ["🙄"], irony_cues: ["🙄"] })];
  assert.equal(M.select(rows, { block: "main", paid: false }).length, 2);
  assert.equal(M.select(rows, { block: "all", paid: true }).length, 3);
  assert.equal(M.select(rows, { block: "1 parte", paid: true }).length, 0);
  assert.equal(M.select(rows, { block: "main", emoji: true }).length, 1);
  assert.equal(M.candidate([], "lula").score, null);
});

test("servidor recusa auditoria desatualizada sem alterar arquivos", t => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "bertweet-dashboard-"));
  t.after(() => {
    assert.ok(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(temp, { recursive: true, force: true });
  });
  assert.throws(() => readDashboard(temp), error => error.status === 404);
  fs.mkdirSync(path.join(temp, "output/2026/bertweet_validacao"), { recursive: true });
  const original = "original";
  fs.writeFileSync(path.join(temp, "source.csv"), original);
  const dashboard = { audit: { inputs: { "source.csv": createHash("sha256").update(original).digest("hex") } }, records: [] };
  fs.writeFileSync(path.join(temp, "output/2026/bertweet_validacao/painel.json"), JSON.stringify(dashboard));
  assert.deepEqual(readDashboard(temp).records, []);
  fs.writeFileSync(path.join(temp, "source.csv"), "changed");
  assert.throws(() => readDashboard(temp), error => error.status === 409);
  assert.equal(fs.readFileSync(path.join(temp, "source.csv"), "utf8"), "changed");
});
