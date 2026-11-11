"use strict";

const $ = id => document.getElementById(id);
const M = BertweetMetrics;
const integer = new Intl.NumberFormat("pt-BR");
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const dateFormat = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });
const colors = { positivo: "#16846b", negativo: "#be4c50", neutro: "#a0aeb0" };
const labelNames = { positivo: "Positivo", negativo: "Negativo", neutro: "Neutro", incerto: "Incerto", sem_referencia: "Sem referência" };
let data;
let current = [];
let tableRows = [];
let page = 1;
const pageSize = 12;

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== "") node.textContent = String(text);
  return node;
}
function pill(value) { return el("span", `pill ${value}`, labelNames[value] || value); }
function options() {
  return { block: $("blockFilter").value,
    paid: $("paidFilter").checked, emoji: $("emojiFilter").checked };
}
function percentage(count, total) { return total ? `${decimal.format(count / total * 100)}%` : "—"; }
function countBox(value, label, total, sentiment) {
  const node = el("div", `sentiment-count ${sentiment}`);
  const heading = el("div", "sentiment-count-heading");
  heading.append(el("span", "sentiment-dot"), el("span", "", label), el("span", "sentiment-share", percentage(value, total)));
  node.append(heading, el("strong", "sentiment-count-value", integer.format(value)), el("small", "", "mensagens"));
  return node;
}
function renderCandidate(name, title, counts) {
  const card = el("article", "candidate-card");
  card.dataset.candidate = name;
  const top = el("div", "candidate-top");
  const identity = el("div");
  identity.append(el("h3", "", title), el("small", "", "Polaridade associada por regra nominal"));
  const photo = el("img", `candidate-photo ${name}`);
  photo.src = `/assets/${name}.jpg`;
  photo.alt = `Foto de ${title}`;
  photo.width = 84; photo.height = 84;
  top.append(photo, identity);
  const body = el("div", "sentiment-body");
  const gaugeWrap = el("div", "sentiment-meter-wrap");
  const gauge = el("div", "sentiment-meter");
  gauge.setAttribute("role", counts.score === null ? "img" : "meter");
  gauge.setAttribute("aria-label", `Termômetro de ${title}`);
  gauge.setAttribute("aria-valuemin", "-100");
  gauge.setAttribute("aria-valuemax", "100");
  if (counts.score !== null) {
    gauge.setAttribute("aria-valuenow", counts.score.toFixed(1));
    gauge.setAttribute("aria-valuetext", `${counts.positivo} positivas e ${counts.negativo} negativas`);
    const marker = el("span", "sentiment-marker");
    marker.style.left = `${(counts.score + 100) / 2}%`;
    gauge.append(marker);
  } else gauge.setAttribute("aria-valuetext", "Sem mensagens positivas ou negativas atribuídas");
  const axis = el("div", "sentiment-axis");
  axis.append(el("span", "", "−100"), el("span", "", "0"), el("span", "", "+100"));
  axis.setAttribute("aria-hidden", "true");
  const endpoints = el("div", "sentiment-endpoints");
  endpoints.append(el("span", "negative", "Negativas"), el("span", "positive", "Positivas"));
  gaugeWrap.append(gauge, axis, endpoints);
  const boxes = el("div", "sentiment-counts");
  boxes.append(countBox(counts.positivo, "Positivas", counts.polarized, "positive"), countBox(counts.negativo, "Negativas", counts.polarized, "negative"));
  body.append(gaugeWrap, boxes);
  const bottom = el("div", "sentiment-base");
  bottom.append(el("span", "base-dot"), document.createTextNode(`${integer.format(counts.polarized)} mensagens positivas e negativas neste recorte`));
  card.append(top, body, bottom);
  return card;
}
function renderOverview() {
  const opts = options();
  current = M.select(data.records, opts);
  const summary = M.summarize(current);
  const blockName = opts.block === "main" ? "Quatro blocos principais" : opts.block;
  $("scopeText").textContent = `${integer.format(summary.rows)} mensagens classificadas · ${blockName} · ${opts.paid ? "inclui Super Chats" : "somente mensagens comuns"} · auditoria de ${dateFormat.format(new Date(data.audit.created_at_utc))}`;
  $("candidateCards").replaceChildren(renderCandidate("lula", "Lula", summary.lula), renderCandidate("flavio", "Flávio Bolsonaro", summary.flavio));
  $("generalBar").replaceChildren(); $("generalLegend").replaceChildren();
  for (const label of ["positivo", "neutro", "negativo"]) {
    const segment = el("div");
    segment.style.background = colors[label]; segment.style.width = `${summary.rows ? summary.general[label] / summary.rows * 100 : 0}%`;
    segment.title = `${labelNames[label]}: ${integer.format(summary.general[label])}`;
    $("generalBar").append(segment);
    const item = el("div");
    const dot = el("span", "legend-dot"); dot.style.background = colors[label];
    item.append(dot, document.createTextNode(`${labelNames[label]} · ${percentage(summary.general[label], summary.rows)}`), el("strong", "", integer.format(summary.general[label])));
    $("generalLegend").append(item);
  }
  $("emojiCount").textContent = integer.format(summary.emoji);
  $("cueCount").textContent = integer.format(summary.cues);
  $("uniqueCount").textContent = integer.format(summary.unique);
  page = 1; renderTable();
}
function normalized(value) { return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
function renderTable() {
  const target = $("targetFilter").value;
  const label = $("labelFilter").value;
  const query = normalized($("searchText").value);
  tableRows = current.filter(row => (!query || normalized(row.text).includes(query)) &&
    (target === "all" || row[target] !== "sem_referencia") &&
    (label === "all" || (target === "all" ? row.label === label : M.candidateLabel(row, target) === label)));
  const pages = Math.max(1, Math.ceil(tableRows.length / pageSize)); page = Math.min(page, pages);
  $("tableNote").textContent = `${integer.format(tableRows.length)} mensagens. O filtro de rótulo usa ${target === "all" ? "o sentimento da frase inteira" : "a atribuição ao candidato escolhido"}. Para ver “incerto”, selecione um candidato.`;
  const fragment = document.createDocumentFragment();
  for (const row of tableRows.slice((page - 1) * pageSize, page * pageSize)) {
    const tr = el("tr");
    const textCell = el("td"); textCell.append(el("div", "message-text", row.text), el("div", "row-meta", `${row.block}${row.paid ? " · Super Chat" : ""}${row.irony_cues.length ? " · pista para revisão" : ""}`));
    const generalCell = el("td"); generalCell.append(pill(row.label), el("div", "confidence-small", `${decimal.format(row.confidence * 100)}%`));
    const lula = el("td"); lula.append(pill(M.candidateLabel(row, "lula")));
    const flavio = el("td"); flavio.append(pill(M.candidateLabel(row, "flavio")));
    const inspect = el("td"); const button = el("button", "inspect-button", "Ver entrada");
    button.addEventListener("click", () => inspectRow(row)); inspect.append(button);
    tr.append(textCell, generalCell, lula, flavio, inspect); fragment.append(tr);
  }
  if (!tableRows.length) { const tr = el("tr"); const td = el("td", "empty", "Nenhuma mensagem neste recorte. Ajuste os filtros."); td.colSpan = 5; tr.append(td); fragment.append(tr); }
  $("messageRows").replaceChildren(fragment);
  $("pageText").textContent = `Página ${page} de ${integer.format(pages)}`;
  $("prevPage").disabled = page === 1; $("nextPage").disabled = page >= pages;
  $("exportCsv").disabled = !tableRows.length;
}
function probabilityBars(probabilities) {
  const container = el("div", "probabilities");
  for (const [index, label] of ["negativo", "neutro", "positivo"].entries()) {
    const item = el("div"); const track = el("div", "prob-track"); const fill = el("span");
    fill.style.width = `${probabilities[index] * 100}%`; fill.style.background = colors[label]; track.append(fill);
    item.append(document.createTextNode(labelNames[label]), track, el("strong", "", `${decimal.format(probabilities[index] * 100)}%`)); container.append(item);
  }
  return container;
}
function inspectRow(row) {
  const container = $("inspectorContent"); container.replaceChildren();
  container.append(el("h3", "", "Texto original classificado"), el("p", "dialog-text", row.text),
    el("h3", "", "Entrada exata após o pré-processamento"), el("div", "prepared-text", row.prepared), probabilityBars(row.p));
  if (row.rule) {
    container.append(el("p", "footnote", `Regra: ${row.rule}. Lula: ${labelNames[row.lula]}. Flávio: ${labelNames[row.flavio]}.`));
    container.append(el("p", "footnote", `ID: ${row.id}. ${row.block}. ${row.truncated ? "Texto truncado em 128 tokens." : "Sem truncamento registrado."}`));
  }
  if (row.irony_cues?.length) container.append(el("div", "notice", `Possíveis pistas: ${row.irony_cues.join(", ")}. O modelo não confirmou ironia; este caso requer interpretação humana.`));
  if (row.token_pieces) {
    container.append(el("h3", "", `Subpalavras produzidas pelo tokenizer · ${row.tokens} tokens com marcadores especiais`));
    const tokens = el("div", "token-pieces"); for (const token of row.token_pieces) tokens.append(el("span", "", token));
    container.append(tokens, el("p", "footnote", "A lista mostra as peças do texto; os marcadores de início/fim são acrescentados na codificação. Até 128 peças são exibidas."));
    container.append(el("p", "footnote spaced", "O marcador @@ indica que a peça continua na próxima: bem@@ seguido de . reconstrói bem. É uma marca interna da tokenização BPE; não faz parte do comentário original."));
  } else container.append(el("p", "footnote", "Os tokens podem ser vistos nos exemplos controlados da seção Emojis & ironia. Aqui a entrada é a gravada no CSV original."));
  $("inspector").showModal();
}
function renderDiagnostics() {
  const selected = $("exampleCandidate").value;
  const cases = data.experiments.cases.filter(row => selected === "isolated" ? !row.text.startsWith("Lula ") && !row.text.startsWith("Flávio ") : row.text.startsWith(`${selected} `));
  $("diagnosticCases").replaceChildren();
  for (const row of cases) {
    const card = el("article", "diagnostic-card");
    const bottom = el("div", "diagnostic-bottom"); const button = el("button", "inspect-button", "Ver entrada e tokens");
    button.addEventListener("click", () => inspectRow(row)); bottom.append(pill(row.label), button);
    card.append(el("h4", "", row.description), el("p", "diagnostic-text", row.text), probabilityBars(row.p), bottom);
    $("diagnosticCases").append(card);
  }
}
function safeCsv(value) { const text = String(value ?? ""); return `"${(/^[=+@\-\t\r]/.test(text) ? "'" : "") + text.replace(/"/g, '""')}"`; }
function exportCsv() {
  const rows = [["message_id", "bloco", "texto", "sentimento_geral", "probabilidade_maxima", "lula", "flavio", "regra"]];
  for (const row of tableRows) rows.push([row.id, row.block, row.text, row.label, row.confidence, row.lula, row.flavio, row.rule]);
  const url = URL.createObjectURL(new Blob(["\ufeff", rows.map(row => row.map(safeCsv).join(";")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
  const a = el("a"); a.href = url; a.download = "bertweet_recorte_exploratorio.csv"; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
for (const button of document.querySelectorAll(".tab")) button.addEventListener("click", () => {
  for (const tab of document.querySelectorAll(".tab")) { const active = tab === button; tab.classList.toggle("active", active); tab.setAttribute("aria-pressed", String(active)); }
  for (const view of document.querySelectorAll(".view")) view.hidden = view.id !== button.dataset.view;
  const participation = button.dataset.view === "participation";
  document.querySelector(".filter-bar").hidden = participation;
  $("scopeText").hidden = participation;
  if (participation) EleiSentParticipation.open();
});
for (const id of ["blockFilter", "paidFilter", "emojiFilter"]) $(id).addEventListener("input", () => { if (data) renderOverview(); });
for (const id of ["targetFilter", "labelFilter", "searchText"]) $(id).addEventListener("input", () => { page = 1; renderTable(); });
$("resetFilters").addEventListener("click", () => { $("blockFilter").value = "main"; for (const id of ["paidFilter", "emojiFilter"]) $(id).checked = false; $("searchText").value = ""; $("targetFilter").value = "all"; $("labelFilter").value = "all"; renderOverview(); });
$("prevPage").addEventListener("click", () => { page--; renderTable(); });
$("nextPage").addEventListener("click", () => { page++; renderTable(); });
$("exampleCandidate").addEventListener("change", renderDiagnostics);
$("closeInspector").addEventListener("click", () => $("inspector").close());
$("exportCsv").addEventListener("click", exportCsv);

async function load() {
  try {
    const response = await fetch("/api/bertweet", { cache: "no-store" });
    if (!response.ok) { const error = await response.json(); throw new Error(error.error || `HTTP ${response.status}`); }
    data = await response.json();
    if (data.audit.status !== "passed") throw new Error("A auditoria encontrou divergências. Confira o JSON antes de interpretar o painel.");
    for (const block of data.blocks.filter(block => block !== "1 parte")) { const option = el("option", "", block); option.value = block; $("blockFilter").append(option); }
    $("loadStatus").hidden = true; $("dashboard").hidden = false;
    renderOverview(); renderDiagnostics();
  } catch (error) { $("loadStatus").textContent = `Não foi possível carregar o painel: ${error.message}`; $("loadStatus").classList.add("error"); }
}
load();
