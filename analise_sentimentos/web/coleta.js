"use strict";

const $ = id => document.getElementById(id);
const count = new Intl.NumberFormat("pt-BR");
const dateTime = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo",
  dateStyle: "short", timeStyle: "medium" });
const titles = {
  idle: "Aguardando o link e o início da coleta",
  starting: "Conectando à API do YouTube",
  waiting_for_live: "Aguardando o chat ficar ativo",
  collecting: "Coletando mensagens do chat",
  finished: "Coleta encerrada",
  paused: "Coleta pausada",
  error: "Coleta interrompida por erro",
  unavailable: "Estado indisponível",
};
let latest = null;
let currentBlocks = [];

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTime.format(date);
}

function elapsed(value) {
  if (!value) return "—";
  const start = new Date(value).getTime();
  if (!Number.isFinite(start)) return "—";
  const minutes = Math.max(0, Math.floor((Date.now() - start) / 60000));
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}min`;
}

function renderActivity(batches) {
  const box = $("activity");
  box.replaceChildren();
  if (!batches?.length) {
    $("activityNote").textContent = "Ainda sem consultas.";
    return;
  }
  const max = Math.max(1, ...batches.map(batch => Number(batch.messages) || 0));
  for (const batch of batches) {
    const bar = document.createElement("div");
    bar.className = "activity-bar";
    bar.style.height = `${Math.max(5, Math.round((Number(batch.messages) || 0) / max * 100))}%`;
    bar.title = `${batch.messages || 0} mensagens · ${formatDate(batch.at_utc)}`;
    bar.setAttribute("aria-label", bar.title);
    box.append(bar);
  }
  $("activityNote").textContent = `${batches.length} consultas mais recentes`;
}

function render(state) {
  latest = state;
  const phase = state.phase || "idle";
  $("phaseTitle").textContent = titles[phase] || phase;
  $("phaseMessage").textContent = state.status_message ||
    (phase === "idle" ? "Assim que o coletor for iniciado com o link, o status aparecerá aqui." : "");
  $("phaseDot").className = `phase-dot phase-${phase}`;
  $("staleWarning").hidden = !state.stale;
  $("lastUpdate").textContent = `Última atualização: ${formatDate(state.status_updated_at_utc)}`;
  $("messages").textContent = count.format(state.total_messages || 0);
  $("pages").textContent = count.format(state.pages || 0);
  $("lastBatch").textContent = count.format(state.last_batch_messages || 0);
  $("elapsed").textContent = elapsed(state.started_at_utc);
  $("videoTitle").textContent = state.video_title || "Aguardando link da transmissão";
  $("videoId").textContent = state.video_id || "—";
  $("firstResponse").textContent = formatDate(state.first_response_at_utc);
  $("lastResponse").textContent = formatDate(state.last_response_at_utc);
  $("lastMessage").textContent = formatDate(state.last_message_at_utc);
  $("csvSize").textContent = state.csv_exists ? ` · ${count.format(state.csv_bytes)} bytes` : " · ainda não criado";
  $("csvLink").classList.toggle("disabled-link", !state.csv_exists);
  const waitDone = ["collecting", "finished", "paused", "error"].includes(phase);
  const collectDone = phase === "finished";
  $("step-wait").className = waitDone ? "done" : phase === "waiting_for_live" || phase === "starting" ? "active" : "";
  $("step-collect").className = collectDone ? "done" : phase === "collecting" ? "active" : "";
  $("step-finish").className = collectDone ? "done" : "";
  renderActivity(state.recent_batches || []);
  updateBlockButtons();
}

function updateBlockButtons() {
  const open = currentBlocks.find(block => !block.ended_at_utc);
  $("startBlock").disabled = Boolean(open) || latest?.phase !== "collecting";
  $("endBlock").disabled = !open;
}

function renderBlocks(blocks) {
  currentBlocks = blocks;
  const list = $("blocksList");
  list.replaceChildren();
  $("blocksEmpty").hidden = blocks.length > 0;
  for (const block of blocks) {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = block.name;
    const times = document.createElement("span");
    times.textContent = `${formatDate(block.started_at_utc)} → ${block.ended_at_utc ? formatDate(block.ended_at_utc) : "em andamento"}`;
    item.append(name, times);
    if (!block.ended_at_utc) item.className = "open-block";
    if (block.ended_at_utc && block.csv_file) {
      const link = document.createElement("a");
      link.href = `/api/blocks/${encodeURIComponent(block.id)}.csv`;
      link.className = "block-download";
      link.textContent = `Baixar CSV · ${block.csv_file}`;
      item.append(link);
    }
    list.append(item);
  }
  updateBlockButtons();
}

async function refresh() {
  try {
    const [response, blocksResponse] = await Promise.all([
      fetch("/api/chat-status", { cache: "no-store" }),
      fetch("/api/blocks", { cache: "no-store" }),
    ]);
    if (!response.ok || !blocksResponse.ok) throw new Error(`HTTP ${response.status}/${blocksResponse.status}`);
    render(await response.json());
    renderBlocks((await blocksResponse.json()).blocks || []);
  } catch (error) {
    $("phaseTitle").textContent = "Painel desconectado";
    $("phaseMessage").textContent = `Não foi possível consultar o servidor local: ${error.message}`;
    $("phaseDot").className = "phase-dot phase-error";
  }
}

async function changeBlock(action, payload) {
  try {
    const response = await fetch(`/api/blocks/${action}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    renderBlocks(data.blocks);
    $("blockFeedback").classList.toggle("error", Boolean(data.export_error));
    $("blockFeedback").textContent = data.export_error
      ? `Bloco salvo, mas não foi possível gerar o CSV: ${data.export_error}`
      : action === "start" ? "Bloco iniciado; a coleta segue normalmente."
        : "Bloco encerrado e CSV gerado para download.";
    if (action === "start") $("blockForm").reset();
  } catch (error) {
    $("blockFeedback").classList.add("error");
    $("blockFeedback").textContent = error.message;
  }
}

$("refresh").addEventListener("click", refresh);
$("blockForm").addEventListener("submit", event => {
  event.preventDefault();
  changeBlock("start", { name: $("blockName").value });
});
$("endBlock").addEventListener("click", () => changeBlock("end", {}));
$("csvLink").addEventListener("click", event => {
  if (!latest?.csv_exists) event.preventDefault();
});
refresh();
setInterval(refresh, 3000);
setInterval(() => { if (latest) $("elapsed").textContent = elapsed(latest.started_at_utc); }, 30000);
