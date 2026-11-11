"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { analyzeParticipation } = require("../scripts/participacao");
const start = Date.parse("2026-10-18T23:00:00Z");
const blocks = [
  { name: "Bloco 1", video_id: "v", started_at_utc: new Date(start).toISOString(), ended_at_utc: new Date(start + 600000).toISOString() },
  { name: "1 parte", video_id: "v", started_at_utc: new Date(start - 10000).toISOString(), ended_at_utc: new Date(start - 5000).toISOString() },
];
function event(id, author, text, offset, type = "textMessageEvent") {
  return { message_id: id, video_id: "v", author_channel_id: author, text, published_at: new Date(start + offset).toISOString(), message_type: type };
}
function predicted(events) {
  return new Map(events.filter(e => e.message_type === "textMessageEvent").map((e, i) => [e.message_id, {
    sentimento_geral_automatico: i % 2 ? "negativo" : "positivo",
    sentimento_lula_automatico: "incerto", sentimento_flavio_automatico: "incerto",
  }]));
}
test("participação separa repetição na mesma conta, coocorrência e eventos pagos", () => {
  const events = [event("1", "autor-a", "Bora Lula", 0), event("2", "autor-a", " bora   LULA ", 2000),
    event("3", "autor-a", "Outra frase?", 20000), event("4", "autor-b", "Bora Lula", 30000),
    event("5", "autor-pago", "Pago", 40000, "superChatEvent"), event("x", "autor-experimental", "Teste", -8000)];
  const result = analyzeParticipation(events, predicted(events), blocks);
  assert.equal(result.summary.text, 4);
  assert.equal(result.summary.accounts, 3);
  assert.equal(result.summary.textAccounts, 2);
  assert.equal(result.summary.singleAccounts, 1);
  assert.equal(result.summary.trajectoryAccounts, 1);
  assert.equal(result.summary.repetitions, 1);
  assert.equal(result.types.superchat, 1);
  assert.equal(result.cooccurrence.both, 4);
  assert.equal(result.accounts.reduce((sum, a) => sum + a.periods.reduce((s, c) => s + c, 0), 0), 4);
  assert.equal(result.accounts.find(a => a.text === 3).messages.length, 3);
  assert.ok(!JSON.stringify(result).includes('"autor-a"'));
  assert.ok(!JSON.stringify(result).includes('"author_channel_id"'));
});
test("intervalos não atravessam interrupções e janelas parciais ficam marcadas", () => {
  const events = [event("1", "a", "Um", 0), event("2", "a", "Dois", 2000), event("3", "a", "Três", 20000), event("4", "a", "Quatro", 25000)];
  const result = analyzeParticipation(events, predicted(events), blocks, [{ start: start + 3000, end: start + 15000 }]);
  assert.equal(result.summary.intervalPairs, 2);
  assert.equal(result.summary.medianInterval, 3.5);
  assert.equal(result.timeline[0].partial, true);
  assert.equal(result.accounts[0].medianInterval, 3.5);
});
test("IDs duplicados ou mensagens sem previsão impedem indicadores inconsistentes", () => {
  const e = event("1", "a", "Texto", 0);
  assert.throws(() => analyzeParticipation([e, e], predicted([e]), blocks), /duplicado/);
  assert.throws(() => analyzeParticipation([e], new Map(), blocks), /sem previsão/);
  assert.throws(() => analyzeParticipation([{ ...e, author_channel_id: "" }], predicted([e]), blocks), /sem autor/);
});
