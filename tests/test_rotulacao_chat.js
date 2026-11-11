"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { FILENAME, FIELDS, csvValue, readRows, sampleFromSource, saveAnnotation } =
  require("../scripts/rotulacao_chat");

function temporaryFolder(t) {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "rotulacao-chat-"));
  t.after(() => {
    if (!path.resolve(folder).startsWith(path.resolve(os.tmpdir()) + path.sep)) {
      throw new Error("Pasta temporária fora do diretório esperado");
    }
    fs.rmSync(folder, { recursive: true, force: true });
  });
  return folder;
}

test("amostra separa quatro blocos e preserva CSV com vírgulas e quebras de linha", t => {
  const folder = temporaryFolder(t);
  const blocks = [], lines = ["message_id,video_id,published_at,message_type,text"];
  for (let index = 0; index < 4; index++) {
    const base = new Date(Date.parse("2026-10-18T23:00:00Z") + index * 3600000);
    blocks.push({ name: `Bloco ${index + 1}`, started_at_utc: base.toISOString(),
      ended_at_utc: new Date(base.getTime() + 600000).toISOString() });
    for (const [kind, text] of [["lula", `Lula foi bem ${index}`],
      ["flavio", `Flávio, foi ""ótimo""\nno bloco ${index}`]]) {
      const row = [`m-${index}-${kind}`, "video", new Date(base.getTime() + 60000).toISOString(),
        "textMessageEvent", text];
      lines.push(row.map(csvValue).join(","));
    }
  }
  fs.writeFileSync(path.join(folder, "blocos.json"), JSON.stringify(blocks), "utf8");
  fs.writeFileSync(path.join(folder, "chat_ao_vivo.csv"), "\ufeff" + lines.join("\r\n") + "\r\n", "utf8");
  const result = sampleFromSource(folder, 2);
  assert.equal(result.rows.length, 8);
  assert.deepEqual(result.rows.reduce((counts, row) => {
    counts[row.bloco] = (counts[row.bloco] || 0) + 1; return counts;
  }, {}), { "Bloco 1": 2, "Bloco 2": 2, "Bloco 3": 2, "Bloco 4": 2 });
  assert.equal(new Set(result.rows.map(row => row.text)).size, 8);
  assert.ok(result.rows.some(row => row.text.includes("\n")));
});

test("salva rótulos sem alterar o texto e rejeita gravação desatualizada", t => {
  const folder = temporaryFolder(t);
  const original = { message_id: "m1", video_id: "video", published_at: "2026-10-18T23:01:00Z",
    bloco: "Bloco 1", estrato_amostragem: "ambos", text: "Lula, ótimo\nFlávio \"ruim\"",
    sentimento_lula: "", sentimento_flavio: "", rotulado_em_utc: "" };
  fs.writeFileSync(path.join(folder, FILENAME), "\ufeff" + FIELDS.join(",") + "\r\n" +
    FIELDS.map(field => csvValue(original[field])).join(",") + "\r\n", "utf8");
  const saved = saveAnnotation(folder, { message_id: "m1", lula: "positivo",
    flavio: "negativo", expected_updated_at: "" });
  assert.equal(saved.sentimento_lula, "positivo");
  assert.equal(saved.sentimento_flavio, "negativo");
  assert.equal(readRows(path.join(folder, FILENAME))[0].text, original.text);
  assert.throws(() => saveAnnotation(folder, { message_id: "m1", lula: "neutro",
    flavio: "negativo", expected_updated_at: "" }), /outra aba/);
  assert.throws(() => saveAnnotation(folder, { message_id: "m1", lula: "inventado",
    flavio: "negativo", expected_updated_at: saved.rotulado_em_utc }), /rótulo válido/);
});
