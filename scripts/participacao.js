"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");
const { csvRecords, csvFields } = require("./chat_block_export");

function readCsv(filename) {
  let content = fs.readFileSync(filename, "utf8");
  if (!content.endsWith("\n")) content += "\n";
  const records = csvRecords(content);
  const header = csvFields((records.next().value || "").replace(/^\ufeff/, ""));
  const rows = [];
  for (const record of records) {
    const values = csvFields(record);
    if (values.length !== header.length) throw new Error(`CSV inválido: ${path.basename(filename)}`);
    rows.push(Object.fromEntries(header.map((name, index) => [name, values[index]])));
  }
  return rows;
}

function normalize(text) { return text.normalize("NFKC").toLocaleLowerCase("pt-BR").replace(/\s+/g, " ").trim(); }
function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
function overlap(start, end, gap) { return start < gap.end && end > gap.start; }
function makeCounters() { return { total: 0, positivo: 0, negativo: 0, neutro: 0 }; }
function addLabel(counter, value) {
  if (["positivo", "negativo", "neutro"].includes(value)) { counter.total++; counter[value]++; }
}

function analyzeParticipation(events, predictions, blocks, gaps = []) {
  const orderedBlocks = blocks.filter(b => b.name !== "1 parte").map(b => ({ ...b,
    start: Date.parse(b.started_at_utc), end: Date.parse(b.ended_at_utc) })).sort((a, b) => a.start - b.start);
  if (!orderedBlocks.length || orderedBlocks.some(b => !Number.isFinite(b.start) || !Number.isFinite(b.end) || b.end <= b.start)) throw new Error("Blocos inválidos");
  let elapsed = 0;
  for (const block of orderedBlocks) { block.offset = elapsed; elapsed += block.end - block.start; }
  const accounts = new Map();
  const seen = new Set();
  const textCounts = new Map();
  const types = { text: 0, superchat: 0, sticker: 0, other: 0 };
  const cooccurrence = { lula: 0, flavio: 0, both: 0, none: 0 };
  const blockStats = orderedBlocks.map(b => ({ name: b.name, start: b.start, end: b.end, text: 0,
    paid: 0, accounts: new Set(), counts: makeCounters() }));
  const timeline = [];
  for (const [index, block] of orderedBlocks.entries()) {
    for (let start = block.start; start < block.end; start += 300000) {
      const end = Math.min(start + 300000, block.end);
      timeline.push({ block: index, start, end, partial: gaps.some(g => overlap(start, end, g)),
        general: makeCounters(), lula: makeCounters(), flavio: makeCounters() });
    }
  }
  let classified = 0;
  let questionMessages = 0;
  for (const event of [...events].sort((a, b) => Date.parse(a.published_at) - Date.parse(b.published_at))) {
    const time = Date.parse(event.published_at);
    if (!Number.isFinite(time)) throw new Error("Evento sem horário válido");
    const blockIndex = orderedBlocks.findIndex(b => time >= b.start && time < b.end && (!b.video_id || b.video_id === event.video_id));
    if (blockIndex < 0) continue;
    if (!event.message_id || seen.has(event.message_id)) throw new Error("ID de mensagem vazio ou duplicado");
    if (!event.author_channel_id || !Number.isFinite(time)) throw new Error("Evento sem autor ou horário válido");
    seen.add(event.message_id);
    const block = orderedBlocks[blockIndex];
    if (!accounts.has(event.author_channel_id)) accounts.set(event.author_channel_id, {
      key: event.author_channel_id, text: 0, paid: 0, questions: 0, unique: new Set(), words: new Set(),
      wordCount: 0, blocks: orderedBlocks.map(() => 0), periods: [0, 0, 0], messages: [],
    });
    const account = accounts.get(event.author_channel_id);
    const stats = blockStats[blockIndex];
    stats.accounts.add(event.author_channel_id);
    const type = event.message_type;
    if (type === "superChatEvent" || type === "superStickerEvent") {
      account.paid++; stats.paid++; types[type === "superChatEvent" ? "superchat" : "sticker"]++;
    } else if (type !== "textMessageEvent") types.other++;
    if (type !== "textMessageEvent") continue;
    types.text++; account.text++; stats.text++; account.blocks[blockIndex]++;
    const period = Math.min(2, Math.floor((block.offset + time - block.start) / elapsed * 3));
    account.periods[period]++;
    const text = normalize(event.text);
    account.unique.add(text);
    textCounts.set(text, (textCounts.get(text) || 0) + 1);
    const question = event.text.includes("?");
    account.questions += Number(question); questionMessages += Number(question);
    const words = text.match(/[\p{L}\p{N}]+/gu) || [];
    account.wordCount += words.length;
    for (const word of words) account.words.add(word);
    const predicted = predictions.get(event.message_id);
    if (!predicted) throw new Error("Mensagem comum sem previsão BERTweet");
    classified++;
    const record = { time, block: blockIndex, text: event.text, label: predicted.sentimento_geral_automatico,
      lula: predicted.sentimento_lula_automatico, flavio: predicted.sentimento_flavio_automatico };
    account.messages.push(record);
    addLabel(stats.counts, record.label);
    const bucket = timeline.find(b => b.block === blockIndex && time >= b.start && time < b.end);
    addLabel(bucket.general, record.label); addLabel(bucket.lula, record.lula); addLabel(bucket.flavio, record.flavio);
    const lula = record.lula !== "sem_referencia";
    const flavio = record.flavio !== "sem_referencia";
    cooccurrence[lula && flavio ? "both" : lula ? "lula" : flavio ? "flavio" : "none"]++;
  }
  const sortedAccounts = [...accounts.values()].sort((a, b) =>
    createHash("sha256").update(a.key).digest("hex").localeCompare(createHash("sha256").update(b.key).digest("hex")));
  const allIntervals = [];
  const participants = sortedAccounts.map((account, index) => {
    const intervals = [];
    for (let i = 1; i < account.messages.length; i++) {
      const previous = account.messages[i - 1], current = account.messages[i];
      if (previous.block === current.block && !gaps.some(g => overlap(previous.time, current.time, g))) intervals.push((current.time - previous.time) / 1000);
    }
    allIntervals.push(...intervals);
    const labels = new Set(account.messages.map(m => m.label));
    return { code: `Conta ${String(index + 1).padStart(5, "0")}`, text: account.text, paid: account.paid,
      distinct: account.unique.size, repetitions: account.text - account.unique.size, questions: account.questions,
      lexicalDiversity: account.wordCount ? account.words.size / account.wordCount : null,
      medianInterval: median(intervals), blocks: account.blocks, periods: account.periods,
      labelChanges: labels.size > 1, messages: account.text >= 3 ? account.messages : [] };
  });
  const textAccounts = participants.filter(a => a.text > 0);
  const histogram = [
    { label: "1 mensagem", accounts: textAccounts.filter(a => a.text === 1).length },
    { label: "2 a 5", accounts: textAccounts.filter(a => a.text >= 2 && a.text <= 5).length },
    { label: "6 a 20", accounts: textAccounts.filter(a => a.text >= 6 && a.text <= 20).length },
    { label: "21 ou mais", accounts: textAccounts.filter(a => a.text >= 21).length },
  ];
  const repeated = participants.reduce((sum, a) => sum + a.repetitions, 0);
  const words = [...textCounts].filter(([text, count]) => text.length >= 4 && count >= 3)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "pt-BR"))
    .slice(0, 15).map(([text, count]) => ({ text, count }));
  return { meta: {
    scope: "Quatro blocos principais do chat da Band de 2026; bloco experimental excluído.",
    definition: "As contagens se referem a mensagens capturadas. Uma ocorrência no recorte não comprova uma única publicação no chat inteiro.",
    periods: "Início, meio e fim são três partes iguais da duração dos blocos registrados, somadas sem os intervalos entre blocos.",
    repetitions: "Repetição: ocorrência adicional do mesmo texto na própria conta após normalizar caixa, espaços e Unicode. Não implica automação ou coordenação.",
    intervals: "Intervalos entre mensagens comuns consecutivas da mesma conta e do mesmo bloco; pares que atravessam interrupção conhecida não entram.",
    timeline: "Janelas de até cinco minutos por bloco. Percentuais usam mensagens com classe definida no alvo selecionado. Janelas parciais ou com menos de cinco classificações não são conectadas.",
    identity: "Os códigos representam contas, não pessoas únicas, identidades políticas ou robôs.",
  }, summary: { events: seen.size, text: types.text, accounts: participants.length, textAccounts: textAccounts.length,
    singleAccounts: histogram[0].accounts, recurrentAccounts: textAccounts.filter(a => a.text >= 2).length,
    trajectoryAccounts: textAccounts.filter(a => a.text >= 3).length,
    varyingAccounts: textAccounts.filter(a => a.text >= 3 && a.labelChanges).length,
    repetitions: repeated, distinctGlobalTexts: textCounts.size, questionMessages,
    medianInterval: median(allIntervals), intervalPairs: allIntervals.length, classified },
    types, histogram, blocks: blockStats.map(b => ({ ...b, accounts: b.accounts.size })),
    timeline, cooccurrence, expressions: words, accounts: participants };
}

function loadParticipation(root) {
  const source = path.join(root, "output/2026");
  const blocks = JSON.parse(fs.readFileSync(path.join(source, "blocos.json"), "utf8"));
  const inventory = JSON.parse(fs.readFileSync(path.join(source, "blocos/resumo_blocos.json"), "utf8"));
  const events = inventory.filter(b => b.name !== "1 parte").flatMap(b => {
    if (path.basename(b.file) !== b.file) throw new Error("Nome de bloco inválido");
    const rows = readCsv(path.join(source, "blocos", b.file));
    if (rows.length !== b.messages) throw new Error(`Contagem de bloco divergente: ${b.name}`);
    return rows;
  });
  const predictions = new Map(readCsv(path.join(source, "bertweet_band/classificacao.csv")).map(r => [r.message_id, r]));
  const coverage = JSON.parse(fs.readFileSync(path.join(source, "lacunas_coleta.json"), "utf8"));
  const gaps = (coverage.gaps || []).map(g => ({ start: Date.parse(g.last_message_before_utc), end: Date.parse(g.first_message_after_utc) }));
  return analyzeParticipation(events, predictions, blocks, gaps);
}

module.exports = { analyzeParticipation, loadParticipation, readCsv, normalize, median };
