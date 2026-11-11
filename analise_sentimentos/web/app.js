"use strict";

const fields = [
  { key: "comment_id", label: "ID" },
  { key: "published_at", label: "Publicado (Brasília)" },
  { key: "periodo", label: "Período" },
  { key: "text", label: "Comentário" },
  { key: "sentiment", label: "Sentimento" },
  { key: "positive_score", label: "Score positivo" },
  { key: "negative_score", label: "Score negativo" },
  { key: "term_count", label: "Termos" },
  { key: "synset_count", label: "Synsets" },
];
const sentimentLabels = {
  positive: "Positivo", negative: "Negativo", neutral: "Neutro",
  insufficient_evidence: "Sem evidência",
};
const periodLabels = {
  durante_debate: "Durante o debate",
  entre_debate_e_publicacao: "Entre debate e publicação",
  apos_publicacao: "Após a publicação",
};
const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric",
  hour: "2-digit", minute: "2-digit", hour12: false,
});
const dateKeyFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit",
});
const numberFormatter = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 6 });
const integerFormatter = new Intl.NumberFormat("pt-BR");
const state = {
  records: [], filtered: [], visible: new Set(fields.map(field => field.key)),
  page: 1, pageSize: 25, sortKey: "published_at", sortDirection: "asc",
  generation: 0,
};
const $ = id => document.getElementById(id);
const filterForm = $("filtersForm");

function element(tag, className = "", value = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== "") node.textContent = String(value);
  return node;
}

function fold(value) {
  return String(value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function brDateKey(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = Object.fromEntries(dateKeyFormatter.formatToParts(date).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function displayDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value ?? "") : dateTimeFormatter.format(date);
}

function recordValue(record, key) {
  if (key === "term_count") return record.detalhes.length;
  if (key === "synset_count") return record.detalhes.reduce((sum, token) => sum + (token.synsets?.length || 0), 0);
  return record[key];
}

function displayValue(record, key) {
  const value = recordValue(record, key);
  if (key === "published_at") return displayDate(value);
  if (key === "periodo") return periodLabels[value] || value || "—";
  if (key === "sentiment") return sentimentLabels[value] || value || "—";
  if (key.endsWith("_score")) return numberFormatter.format(Number(value) || 0);
  return value ?? "";
}

function numericPass(value, minimum, maximum) {
  const score = Number(value);
  if (minimum !== "" && score < Number(minimum)) return false;
  if (maximum !== "" && score > Number(maximum)) return false;
  return true;
}

function nestedPass(record, values) {
  const needed = ["token", "pos", "negated", "token_positive_min", "token_negative_min",
    "synset", "synset_positive_min", "synset_negative_min"].some(name => values[name] !== "");
  if (!needed) return true;
  const synsetNeeded = ["synset", "synset_positive_min", "synset_negative_min"]
    .some(name => values[name] !== "");
  return record.detalhes.some(token => {
    if (values.token && !fold(`${token.palavra} ${token.lema}`).includes(fold(values.token))) return false;
    if (values.pos && token.classe_gramatical !== values.pos) return false;
    if (values.negated && String(Boolean(token.negado)) !== values.negated) return false;
    if (!numericPass(token.pos_score, values.token_positive_min, "")) return false;
    if (!numericPass(token.neg_score, values.token_negative_min, "")) return false;
    if (!synsetNeeded) return true;
    return (token.synsets || []).some(synset =>
      (!values.synset || fold(synset.synset).includes(fold(values.synset))) &&
      numericPass(synset.pos, values.synset_positive_min, "") &&
      numericPass(synset.neg, values.synset_negative_min, ""));
  });
}

function matches(record, values) {
  if (values.comment_id && !fold(record.comment_id).includes(fold(values.comment_id))) return false;
  if (values.text && !fold(record.text).includes(fold(values.text))) return false;
  if (values.sentiment && record.sentiment !== values.sentiment) return false;
  if (values.periodo && record.periodo !== values.periodo) return false;
  if ((values.date_from || values.date_to) && !record._brDate) return false;
  if (values.date_from && record._brDate < values.date_from) return false;
  if (values.date_to && record._brDate > values.date_to) return false;
  if (!numericPass(record.positive_score, values.positive_min, values.positive_max)) return false;
  if (!numericPass(record.negative_score, values.negative_min, values.negative_max)) return false;
  return nestedPass(record, values);
}

function sortRecords(records) {
  const multiplier = state.sortDirection === "asc" ? 1 : -1;
  const numeric = new Set(["positive_score", "negative_score", "term_count", "synset_count"]);
  records.sort((a, b) => {
    const left = recordValue(a, state.sortKey);
    const right = recordValue(b, state.sortKey);
    const comparison = numeric.has(state.sortKey)
      ? Number(left) - Number(right)
      : String(left ?? "").localeCompare(String(right ?? ""), "pt-BR", { sensitivity: "base" });
    return comparison * multiplier;
  });
}

function applyFilters() {
  const values = Object.fromEntries(new FormData(filterForm));
  state.filtered = state.records.filter(record => matches(record, values));
  sortRecords(state.filtered);
  state.page = 1;
  render();
}

function addCell(row, text, className = "") {
  const cell = element("td", className, text);
  row.append(cell);
  return cell;
}

function renderDetail(record) {
  const container = element("div", "detail-panel");
  container.append(element("p", "detail-label", "Comentário completo"));
  container.append(element("p", "full-comment", record.text || "(sem texto)"));
  container.append(element("p", "detail-label", `${record.detalhes.length} termos · ${recordValue(record, "synset_count")} synsets`));
  if (!record.detalhes.length) {
    container.append(element("p", "hint", "Nenhum termo com detalhe lexical neste comentário."));
    return container;
  }
  const tableWrap = element("div", "token-scroll");
  const table = element("table", "token-table");
  const header = element("thead");
  const headerRow = element("tr");
  for (const title of ["#", "Palavra", "Lema", "Classe", "Negado", "Pos. termo", "Neg. termo", "Synsets"]) {
    headerRow.append(element("th", "", title));
  }
  header.append(headerRow);
  table.append(header);
  const body = element("tbody");
  for (const token of record.detalhes) {
    const row = element("tr");
    addCell(row, token.indice_token ?? "");
    addCell(row, token.palavra ?? "");
    addCell(row, token.lema ?? "");
    addCell(row, token.classe_gramatical ?? "");
    addCell(row, token.negado ? "Sim" : "Não");
    addCell(row, numberFormatter.format(Number(token.pos_score) || 0), "number-cell");
    addCell(row, numberFormatter.format(Number(token.neg_score) || 0), "number-cell");
    const synsetCell = addCell(row, "");
    const synsets = token.synsets || [];
    if (synsets.length) {
      const details = element("details", "synset-details");
      details.append(element("summary", "", `${synsets.length} synset${synsets.length === 1 ? "" : "s"}`));
      const synsetTable = element("table", "synset-table");
      const headRow = element("tr");
      for (const title of ["Synset", "Pos.", "Neg.", "Obj."]) headRow.append(element("th", "", title));
      const head = element("thead"); head.append(headRow); synsetTable.append(head);
      const tbody = element("tbody");
      for (const synset of synsets) {
        const sr = element("tr");
        addCell(sr, synset.synset ?? "");
        for (const key of ["pos", "neg", "obj"]) addCell(sr, numberFormatter.format(Number(synset[key]) || 0), "number-cell");
        tbody.append(sr);
      }
      synsetTable.append(tbody);
      details.append(synsetTable);
      synsetCell.append(details);
    } else synsetCell.textContent = "—";
    body.append(row);
  }
  table.append(body);
  tableWrap.append(table);
  container.append(tableWrap);
  return container;
}

function renderHeader(visible) {
  const head = $("tableHead");
  head.replaceChildren();
  const row = element("tr");
  row.append(element("th", "expand-heading", "Detalhes"));
  for (const field of visible) {
    const cell = element("th");
    const button = element("button", "sort-button", field.label);
    button.type = "button";
    if (state.sortKey === field.key) {
      cell.setAttribute("aria-sort", state.sortDirection === "asc" ? "ascending" : "descending");
      button.append(element("span", "sort-arrow", state.sortDirection === "asc" ? " ↑" : " ↓"));
    }
    button.addEventListener("click", () => {
      if (state.sortKey === field.key) state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
      else { state.sortKey = field.key; state.sortDirection = "asc"; }
      sortRecords(state.filtered);
      state.page = 1;
      render();
    });
    cell.append(button);
    row.append(cell);
  }
  head.append(row);
}

function render() {
  const visible = fields.filter(field => state.visible.has(field.key));
  renderHeader(visible);
  const body = $("tableBody");
  body.replaceChildren();
  const start = (state.page - 1) * state.pageSize;
  for (const record of state.filtered.slice(start, start + state.pageSize)) {
    const row = element("tr", "data-row");
    const expand = addCell(row, "", "expand-cell");
    const button = element("button", "expand-button", "+");
    button.type = "button";
    button.setAttribute("aria-label", `Ver detalhes do comentário ${record.comment_id}`);
    button.setAttribute("aria-expanded", "false");
    expand.append(button);
    for (const field of visible) {
      const cell = addCell(row, "");
      if (field.key === "text") cell.append(element("div", "comment-preview", displayValue(record, field.key)));
      else if (field.key === "sentiment") cell.append(element("span", `sentiment sentiment-${record.sentiment}`, displayValue(record, field.key)));
      else {
        cell.textContent = displayValue(record, field.key);
        if (field.key.endsWith("_score") || field.key.endsWith("_count")) cell.classList.add("number-cell");
        if (field.key === "comment_id") cell.classList.add("id-cell");
      }
    }
    const detailRow = element("tr", "detail-row");
    const detailCell = element("td");
    detailCell.colSpan = visible.length + 1;
    detailRow.append(detailCell);
    detailRow.hidden = true;
    button.addEventListener("click", () => {
      detailRow.hidden = !detailRow.hidden;
      button.textContent = detailRow.hidden ? "+" : "−";
      button.setAttribute("aria-expanded", String(!detailRow.hidden));
      if (!detailRow.hidden && !detailCell.childNodes.length) detailCell.append(renderDetail(record));
    });
    body.append(row, detailRow);
  }
  const count = state.filtered.length;
  const pages = Math.max(1, Math.ceil(count / state.pageSize));
  $("totalCount").textContent = integerFormatter.format(state.records.length);
  $("filteredCount").textContent = integerFormatter.format(count);
  $("positiveCount").textContent = integerFormatter.format(state.filtered.filter(row => row.sentiment === "positive").length);
  $("negativeCount").textContent = integerFormatter.format(state.filtered.filter(row => row.sentiment === "negative").length);
  $("pageInfo").textContent = `Página ${state.page} de ${pages}`;
  $("prevPage").disabled = state.page <= 1;
  $("nextPage").disabled = state.page >= pages;
  $("exportCsv").disabled = !count || !visible.length;
  $("emptyState").hidden = count > 0 || state.records.length === 0;
}

function populatePosOptions() {
  const select = filterForm.elements.pos;
  select.replaceChildren(new Option("Todas", ""));
  const values = new Set(state.records.flatMap(row => row.detalhes.map(token => token.classe_gramatical)).filter(Boolean));
  for (const value of [...values].sort()) select.add(new Option(value, value));
}

function setStatus(message, kind = "") {
  const status = $("status");
  status.textContent = message;
  status.className = `status ${kind}`.trim();
}

async function loadStream(stream, size, label) {
  const generation = ++state.generation;
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "", bytes = 0, lines = 0, invalid = 0;
  const records = [];
  setStatus(`Lendo ${label}…`);
  function parseLine(line) {
    if (!line.trim()) return;
    lines++;
    try {
      const record = JSON.parse(line);
      if (!record || typeof record !== "object" || !Array.isArray(record.detalhes) ||
          record.comment_id == null || record.text == null) throw new Error("registro incompleto");
      record._brDate = brDateKey(record.published_at);
      records.push(record);
    } catch { invalid++; }
  }
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (generation !== state.generation) { await reader.cancel(); return; }
      if (done) break;
      bytes += value.byteLength;
      buffer += decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf("\n")) !== -1) {
        parseLine(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
      }
      if (bytes % (1024 * 1024) < value.byteLength) {
        setStatus(`Lendo ${label}: ${size ? Math.min(100, Math.round(bytes / size * 100)) + "% · " : ""}${integerFormatter.format(records.length)} comentários…`);
        await new Promise(resolve => setTimeout(resolve, 0));
      }
    }
    buffer += decoder.decode();
    parseLine(buffer);
    if (!records.length) throw new Error("Nenhum registro válido encontrado no JSONL.");
    state.records = records;
    state.page = 1;
    filterForm.reset();
    populatePosOptions();
    $("sourceName").textContent = label;
    applyFilters();
    setStatus(`${integerFormatter.format(records.length)} comentários carregados${invalid ? ` · ${integerFormatter.format(invalid)} linhas inválidas ignoradas` : ""}.`, invalid ? "warning" : "success");
  } catch (error) {
    if (generation === state.generation) setStatus(`Não foi possível abrir ${label}: ${error.message}`, "error");
  } finally {
    reader.releaseLock();
  }
}

async function loadDefault() {
  if (!location.protocol.startsWith("http")) {
    setStatus("Abra output/analise_detalhada.jsonl pelo botão acima para começar.");
    return;
  }
  try {
    const response = await fetch("/dados", { cache: "no-store" });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
    await loadStream(response.body, Number(response.headers.get("content-length")) || 0, "output/analise_detalhada.jsonl");
  } catch (error) {
    setStatus(`Arquivo padrão indisponível (${error.message}). Use “Abrir outro JSONL”.`, "error");
  }
}

function csvCell(value) {
  const raw = String(value ?? "");
  const safe = /^[=+@\-\t\r]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replace(/"/g, '""')}"`;
}

function exportFiltered() {
  const visible = fields.filter(field => state.visible.has(field.key));
  const rows = [visible.map(field => csvCell(field.label)).join(";")];
  for (const record of state.filtered) rows.push(visible.map(field => csvCell(displayValue(record, field.key))).join(";"));
  const blob = new Blob(["\ufeff", rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = "analise_filtrada.csv";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

for (const field of fields) {
  const label = element("label", "column-option");
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = true;
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) state.visible.add(field.key);
    else state.visible.delete(field.key);
    render();
  });
  label.append(checkbox, document.createTextNode(field.label));
  $("columnOptions").append(label);
}
let filterTimer;
filterForm.addEventListener("input", () => { clearTimeout(filterTimer); filterTimer = setTimeout(applyFilters, 180); });
filterForm.addEventListener("change", () => { clearTimeout(filterTimer); applyFilters(); });
filterForm.addEventListener("submit", event => event.preventDefault());
$("resetFilters").addEventListener("click", () => { filterForm.reset(); applyFilters(); });
$("pageSize").addEventListener("change", event => { state.pageSize = Number(event.target.value); state.page = 1; render(); });
$("prevPage").addEventListener("click", () => { if (state.page > 1) { state.page--; render(); } });
$("nextPage").addEventListener("click", () => { if (state.page * state.pageSize < state.filtered.length) { state.page++; render(); } });
$("exportCsv").addEventListener("click", exportFiltered);
$("fileInput").addEventListener("change", event => {
  const file = event.target.files[0];
  if (file) loadStream(file.stream(), file.size, file.name);
});
render();
loadDefault();
