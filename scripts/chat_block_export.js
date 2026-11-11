"use strict";

const fs = require("node:fs");
const path = require("node:path");

function blockFilename(block) {
  const slug = String(block.name).normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 48) || "bloco";
  return `${slug}_${String(block.id).slice(0, 8)}.csv`;
}

function* csvRecords(content) {
  let quoted = false;
  let start = 0;
  for (let index = 0; index < content.length; index++) {
    const char = content[index];
    if (char === '"') {
      if (quoted && content[index + 1] === '"') index++;
      else quoted = !quoted;
    } else if (char === "\n" && !quoted) {
      let record = content.slice(start, index);
      if (record.endsWith("\r")) record = record.slice(0, -1);
      if (record) yield record;
      start = index + 1;
    }
  }
  // Ignora uma linha ainda incompleta enquanto o coletor escreve no CSV.
}

function csvFields(record) {
  const fields = [];
  let field = "", quoted = false;
  for (let index = 0; index < record.length; index++) {
    const char = record[index];
    if (char === '"') {
      if (quoted && record[index + 1] === '"') { field += '"'; index++; }
      else quoted = !quoted;
    } else if (char === "," && !quoted) {
      fields.push(field); field = "";
    } else field += char;
  }
  fields.push(field);
  return fields;
}

function exportChatBlock(output, block) {
  if (!block.ended_at_utc) throw new Error("Encerre o bloco antes de exportar");
  const start = Date.parse(block.started_at_utc);
  const end = Date.parse(block.ended_at_utc);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) {
    throw new Error("Horários inválidos para o bloco");
  }
  const source = fs.readFileSync(path.join(output, "chat_ao_vivo.csv"), "utf8");
  const records = csvRecords(source);
  const header = records.next().value;
  if (!header) throw new Error("CSV do chat está vazio");
  const names = csvFields(header.replace(/^\ufeff/, ""));
  const videoIndex = names.indexOf("video_id");
  const publishedIndex = names.indexOf("published_at");
  if (videoIndex < 0 || publishedIndex < 0) throw new Error("Colunas esperadas não encontradas no CSV do chat");
  const selected = [header.replace(/^\ufeff/, "")];
  for (const record of records) {
    const fields = csvFields(record);
    const published = Date.parse(fields[publishedIndex]);
    if (fields[videoIndex] === block.video_id && published >= start && published < end) selected.push(record);
  }
  const destination = path.join(output, "blocos");
  fs.mkdirSync(destination, { recursive: true });
  const filename = blockFilename(block);
  const target = path.join(destination, filename);
  const temporary = target + ".tmp";
  fs.writeFileSync(temporary, "\ufeff" + selected.join("\r\n") + "\r\n", "utf8");
  fs.renameSync(temporary, target);
  return { filename, path: target, messages: selected.length - 1 };
}

module.exports = { blockFilename, csvRecords, csvFields, exportChatBlock };
