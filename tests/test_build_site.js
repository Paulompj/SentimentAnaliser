"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { publicDashboard } = require("../scripts/build_site");
test("pacote público exclui identificadores de autores, caminhos locais e bloco experimental", () => {
  const result = publicDashboard({
    audit: { status: "passed", created_at_utc: "2026-11-11", inputs: { "segredo.env": "hash" } },
    records: [{ id: "1", block: "Bloco 1", text: "Frase", author_channel_id: "UC-original", author_name: "nome", privateField: "não publicar" }, { id: "2", block: "1 parte" }],
    blocks: ["1 parte", "Bloco 1"], experiments: { cases: [], emoji_ablation: ["interno"] },
  });
  assert.equal(result.records.length, 1);
  assert.deepEqual(result.blocks, ["Bloco 1"]);
  assert.equal(result.records[0].text, "Frase");
  assert.equal(result.records[0].author_channel_id, undefined);
  assert.equal(result.audit.inputs, undefined);
  assert.equal(result.experiments.emoji_ablation, undefined);
});
