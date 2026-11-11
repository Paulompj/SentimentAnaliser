"use strict";

const $ = id => document.getElementById(id);
const dateTime = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo",
  dateStyle: "short", timeStyle: "medium" });
let rows = [];
let index = 0;
let saving = false;
const drafts = new Map();

function completed(row) {
  return Boolean(row.sentimento_lula && row.sentimento_flavio);
}

function pendingFrom(start) {
  for (let offset = 0; offset < rows.length; offset++) {
    const candidate = (start + offset) % rows.length;
    if (!completed(rows[candidate])) return candidate;
  }
  return -1;
}

function feedback(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").classList.toggle("error", error);
}

function render() {
  const done = rows.filter(completed).length;
  $("progressText").textContent = `${done} de ${rows.length} mensagens rotuladas`;
  $("progressBar").max = rows.length || 1;
  $("progressBar").value = done;
  $("annotationCard").hidden = rows.length === 0;
  if (!rows.length) return;
  const row = rows[index];
  const draft = drafts.get(row.message_id);
  $("positionText").textContent = `Mensagem ${index + 1} de ${rows.length}`;
  $("blockName").textContent = row.bloco;
  $("publishedAt").textContent = dateTime.format(new Date(row.published_at));
  $("messageText").textContent = row.text;
  $("messageId").textContent = `ID: ${row.message_id}`;
  $("labelLula").value = draft?.lula ?? row.sentimento_lula;
  $("labelFlavio").value = draft?.flavio ?? row.sentimento_flavio;
  $("previous").disabled = index === 0 || saving;
  $("next").disabled = index === rows.length - 1 || saving;
  $("nextPending").disabled = done === rows.length || saving;
  $("save").disabled = saving;
}

function navigate(nextIndex) {
  if (nextIndex < 0 || nextIndex >= rows.length) return;
  index = nextIndex;
  render();
  feedback(drafts.size ? "Há escolhas ainda não salvas nesta página." : "");
}

for (const id of ["labelLula", "labelFlavio"]) {
  $(id).addEventListener("change", () => {
    if (!rows.length) return;
    drafts.set(rows[index].message_id, {
      lula: $("labelLula").value, flavio: $("labelFlavio").value,
    });
    feedback("Clique em “Salvar e continuar” para gravar os rótulos no CSV.");
  });
}

$("previous").addEventListener("click", () => navigate(index - 1));
$("next").addEventListener("click", () => navigate(index + 1));
$("nextPending").addEventListener("click", () => {
  const next = pendingFrom(index + 1);
  if (next >= 0) navigate(next);
});

$("annotationForm").addEventListener("submit", async event => {
  event.preventDefault();
  if (!rows.length || saving) return;
  const row = rows[index];
  const selected = { message_id: row.message_id, lula: $("labelLula").value,
    flavio: $("labelFlavio").value, expected_updated_at: row.rotulado_em_utc };
  if (!selected.lula || !selected.flavio) {
    feedback("Escolha um rótulo para cada candidato.", true); return;
  }
  saving = true;
  render();
  try {
    const response = await fetch("/api/rotulacao", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(selected) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    rows[index] = data.row;
    drafts.delete(row.message_id);
    const next = pendingFrom(index + 1);
    if (next >= 0) index = next;
    render();
    feedback(next >= 0 ? "Rótulos salvos. Próxima mensagem pendente." :
      "Rótulos salvos. Todas as mensagens da amostra foram concluídas.");
  } catch (error) {
    feedback(`Não foi possível salvar: ${error.message}`, true);
  } finally {
    saving = false;
    render();
  }
});

async function load() {
  try {
    const response = await fetch("/api/rotulacao", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    rows = data.rows;
    index = Math.max(0, pendingFrom(0));
    render();
  } catch (error) {
    $("progressText").textContent = `Não foi possível abrir a amostra: ${error.message}`;
  }
}

load();
