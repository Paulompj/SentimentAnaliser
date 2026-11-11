"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");
const { csvRecords, csvFields } = require("./chat_block_export");

const FILENAME = "rotulacao_chat_2026.csv";
const METADATA_FILENAME = "rotulacao_chat_2026_metadados.json";
const FIELDS = ["message_id", "video_id", "published_at", "bloco", "estrato_amostragem",
  "text", "sentimento_lula", "sentimento_flavio", "rotulado_em_utc"];
const LABELS = ["sem_referencia", "positivo", "negativo", "neutro", "misto", "incerto"];
const QUOTAS = { lula: 35, flavio: 35, ambos: 15, outros: 40 };
const SEED = "debate-2026-rotulacao-v1";

function normalizeText(value) {
  return value.normalize("NFKC").toLocaleLowerCase("pt-BR").replace(/\s+/g, " ").trim();
}

function stratum(text) {
  const normalized = text.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/\bjair(?:\s+messias)?\s+bolsonaro\b/g, " ");
  const lula = /(?<!\w)(?:lula|luiz\s+inacio|13)(?!\w)/.test(normalized);
  const flavio = /(?<!\w)(?:flavio|bolsonaro|22)(?!\w)/.test(normalized);
  return lula && flavio ? "ambos" : lula ? "lula" : flavio ? "flavio" : "outros";
}

function ranked(items) {
  return items.sort((left, right) => {
    const a = createHash("sha256").update(SEED + left.message_id).digest("hex");
    const b = createHash("sha256").update(SEED + right.message_id).digest("hex");
    return a.localeCompare(b);
  });
}

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeRows(target, rows) {
  const temporary = target + ".tmp";
  const content = "\ufeff" + [FIELDS.join(","), ...rows.map(row =>
    FIELDS.map(field => csvValue(row[field])).join(","))].join("\r\n") + "\r\n";
  fs.writeFileSync(temporary, content, "utf8");
  fs.renameSync(temporary, target);
}

function readRows(target) {
  const records = csvRecords(fs.readFileSync(target, "utf8"));
  const header = records.next().value;
  if (!header) throw new Error("CSV de rotulação vazio");
  const fields = csvFields(header.replace(/^\ufeff/, ""));
  if (fields.join(",") !== FIELDS.join(",")) throw new Error("Colunas inesperadas no CSV de rotulação");
  const rows = [];
  for (const record of records) {
    const values = csvFields(record);
    if (values.length !== FIELDS.length) throw new Error("Linha inválida no CSV de rotulação");
    rows.push(Object.fromEntries(FIELDS.map((field, index) => [field, values[index]])));
  }
  return rows;
}

function sampleFromSource(output, perBlock = 125) {
  const blocks = JSON.parse(fs.readFileSync(path.join(output, "blocos.json"), "utf8"))
    .filter(block => block.ended_at_utc &&
      Date.parse(block.ended_at_utc) - Date.parse(block.started_at_utc) >= 60000);
  if (blocks.length !== 4) throw new Error("Esperados quatro blocos substantivos encerrados");
  const source = fs.readFileSync(path.join(output, "chat_ao_vivo.csv"), "utf8");
  const records = csvRecords(source);
  const header = csvFields((records.next().value || "").replace(/^\ufeff/, ""));
  const indexes = Object.fromEntries(["message_id", "video_id", "published_at", "message_type", "text"]
    .map(field => [field, header.indexOf(field)]));
  if (Object.values(indexes).some(index => index < 0)) throw new Error("CSV do chat sem as colunas esperadas");
  const buckets = blocks.map(() => Object.fromEntries(Object.keys(QUOTAS)
    .map(group => [group, new Map()])));
  for (const record of records) {
    const values = csvFields(record);
    if (values[indexes.message_type] !== "textMessageEvent") continue;
    const text = values[indexes.text];
    const key = normalizeText(text);
    if (!key) continue;
    const published = Date.parse(values[indexes.published_at]);
    const blockIndex = blocks.findIndex(block => published >= Date.parse(block.started_at_utc) &&
      published < Date.parse(block.ended_at_utc));
    if (blockIndex < 0) continue;
    const group = stratum(text);
    if (!buckets[blockIndex][group].has(key)) {
      buckets[blockIndex][group].set(key, {
        message_id: values[indexes.message_id], video_id: values[indexes.video_id],
        published_at: values[indexes.published_at], bloco: blocks[blockIndex].name,
        estrato_amostragem: group, text, sentimento_lula: "", sentimento_flavio: "",
        rotulado_em_utc: "", normalized_key: key,
      });
    }
  }
  const selected = [], selectedTexts = new Set();
  for (let blockIndex = 0; blockIndex < blocks.length; blockIndex++) {
    const bucket = buckets[blockIndex];
    let count = 0;
    for (const [group, quota] of Object.entries(QUOTAS)) {
      let groupCount = 0;
      for (const row of ranked([...bucket[group].values()])) {
        if (groupCount >= quota || count >= perBlock) break;
        if (selectedTexts.has(row.normalized_key)) continue;
        selected.push(row); selectedTexts.add(row.normalized_key);
        groupCount++; count++;
      }
    }
    if (count < perBlock) {
      for (const row of ranked(Object.values(bucket).flatMap(group => [...group.values()]))) {
        if (count >= perBlock) break;
        if (selectedTexts.has(row.normalized_key)) continue;
        selected.push(row); selectedTexts.add(row.normalized_key); count++;
      }
    }
    if (count !== perBlock) throw new Error(`Mensagens insuficientes no bloco ${blocks[blockIndex].name}`);
  }
  return { rows: ranked(selected).map(({ normalized_key, ...row }) => row),
    metadata: { source: "chat_ao_vivo.csv", source_sha256: createHash("sha256").update(source).digest("hex"),
      selection: "Mensagens de texto distintas, quatro blocos com duração >= 1 minuto, 125 por bloco",
      strata_quotas_per_block: QUOTAS, seed: SEED, sample_size: selected.length,
      note: "A amostra equilibra blocos e menções aproximadas; não estima prevalência no chat." } };
}

function ensureAnnotations(output) {
  const target = path.join(output, FILENAME);
  if (!fs.existsSync(target)) {
    const { rows, metadata } = sampleFromSource(output);
    fs.mkdirSync(output, { recursive: true });
    writeRows(target, rows);
    fs.writeFileSync(path.join(output, METADATA_FILENAME), JSON.stringify(metadata, null, 2), "utf8");
  }
  return { path: target, rows: readRows(target) };
}

function saveAnnotation(output, input) {
  const { path: target, rows } = ensureAnnotations(output);
  const row = rows.find(item => item.message_id === input.message_id);
  if (!row) throw new Error("Mensagem não encontrada na amostra");
  if (!LABELS.includes(input.lula) || !LABELS.includes(input.flavio)) {
    throw new Error("Escolha um rótulo válido para cada candidato");
  }
  if (row.rotulado_em_utc !== String(input.expected_updated_at || "")) {
    const error = new Error("Esta mensagem mudou em outra aba. Atualize a página antes de salvar.");
    error.status = 409;
    throw error;
  }
  row.sentimento_lula = input.lula;
  row.sentimento_flavio = input.flavio;
  row.rotulado_em_utc = new Date().toISOString();
  writeRows(target, rows);
  return row;
}

module.exports = { FILENAME, FIELDS, LABELS, QUOTAS, normalizeText, stratum,
  csvValue, readRows, sampleFromSource, ensureAnnotations, saveAnnotation };
