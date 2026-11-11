"use strict";

// Servidor local sem dependências externas. Expõe apenas os painéis e dados esperados.
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const { blockFilename, exportChatBlock } = require("./chat_block_export");
const { readDashboard } = require("./bertweet_dashboard");
const { loadParticipation } = require("./participacao");

const root = path.resolve(__dirname, "..");
const blocksPath = path.join(root, "output/2026/blocos.json");
const routes = new Map([
  ["/resultados", ["analise_sentimentos/web/resultados.html", "text/html; charset=utf-8"]],
  ["/resultados.css", ["analise_sentimentos/web/resultados.css", "text/css; charset=utf-8"]],
  ["/termometro.css", ["analise_sentimentos/web/termometro.css", "text/css; charset=utf-8"]],
  ["/participacao.css", ["analise_sentimentos/web/participacao.css", "text/css; charset=utf-8"]],
  ["/participacao.js", ["analise_sentimentos/web/participacao.js", "text/javascript; charset=utf-8"]],
  ["/assets/lula.jpg", ["Assets/Lula foto Oficial.jpg", "image/jpeg"]],
  ["/assets/flavio.jpg", ["Assets/Flavio foto oficial.jpg", "image/jpeg"]],
  ["/resultados.js", ["analise_sentimentos/web/resultados.js", "text/javascript; charset=utf-8"]],
  ["/bertweet_metrics.js", ["analise_sentimentos/web/bertweet_metrics.js", "text/javascript; charset=utf-8"]],
  ["/coleta", ["analise_sentimentos/web/coleta.html", "text/html; charset=utf-8"]],
  ["/style.css", ["analise_sentimentos/web/style.css", "text/css; charset=utf-8"]],
  ["/coleta.css", ["analise_sentimentos/web/coleta.css", "text/css; charset=utf-8"]],
  ["/coleta.js", ["analise_sentimentos/web/coleta.js", "text/javascript; charset=utf-8"]],
  ["/chat-csv", ["output/2026/chat_ao_vivo.csv", "text/csv; charset=utf-8"]],
  ["/rotulacao-automatica.csv", ["output/2026/rotulacao_automatica_chat_2026.csv", "text/csv; charset=utf-8"]],
]);
const port = Number(process.argv[2] || 8765);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error("Porta inválida. Use, por exemplo: node scripts/servir_painel.js 8765");
  process.exit(1);
}

function sendJson(response, status, value) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
  response.end(JSON.stringify(value));
}

function readBlocks() {
  try {
    const data = JSON.parse(fs.readFileSync(blocksPath, "utf8"));
    if (!Array.isArray(data)) throw new Error("Formato inválido em blocos.json");
    return data;
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function saveBlocks(blocks) {
  fs.mkdirSync(path.dirname(blocksPath), { recursive: true });
  const temporary = blocksPath + ".tmp";
  fs.writeFileSync(temporary, JSON.stringify(blocks, null, 2), "utf8");
  fs.renameSync(temporary, blocksPath);
}

function publicBlocks(blocks) {
  return blocks.map(block => block.ended_at_utc
    ? { ...block, csv_file: blockFilename(block) } : block);
}

function readSmallJson(request) {
  return new Promise((resolve, reject) => {
    if (!request.headers["content-type"]?.startsWith("application/json")) {
      reject(new Error("Envie JSON")); return;
    }
    let body = "";
    let tooLarge = false;
    request.on("data", chunk => {
      if (tooLarge) return;
      body += chunk;
      if (body.length > 2048) { tooLarge = true; reject(new Error("JSON muito grande")); }
    });
    request.on("end", () => {
      if (tooLarge) return;
      try { resolve(JSON.parse(body)); } catch { reject(new Error("JSON inválido")); }
    });
    request.on("error", reject);
  });
}

http.createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  if (pathname === "/" && ["GET", "HEAD"].includes(request.method)) {
    response.writeHead(302, { "Location": "/resultados", "Cache-Control": "no-store" });
    response.end();
    return;
  }
  if (["/api/bertweet", "/bertweet-auditoria.json"].includes(pathname)) {
    if (request.method !== "GET") { sendJson(response, 405, { error: "Método inválido" }); return; }
    try {
      const data = readDashboard(root);
      sendJson(response, 200, pathname === "/api/bertweet" ? data : data.audit);
    } catch (error) { sendJson(response, error.status || 500, { error: error.message }); }
    return;
  }
  if (pathname === "/api/participacao") {
    if (request.method !== "GET") { sendJson(response, 405, { error: "Método inválido" }); return; }
    try { sendJson(response, 200, loadParticipation(root)); }
    catch (error) { sendJson(response, 500, { error: error.message }); }
    return;
  }
  if (pathname === "/api/blocks") {
    if (request.method !== "GET") { sendJson(response, 405, { error: "Método inválido" }); return; }
    try { sendJson(response, 200, { blocks: publicBlocks(readBlocks()) }); }
    catch { sendJson(response, 500, { error: "Não foi possível ler os blocos" }); }
    return;
  }
  const blockDownload = pathname.match(/^\/api\/blocks\/([a-f0-9-]+)\.csv$/);
  if (blockDownload && request.method === "GET") {
    try {
      const block = readBlocks().find(item => item.id === blockDownload[1]);
      if (!block || !block.ended_at_utc) { sendJson(response, 404, { error: "Bloco não encontrado ou aberto" }); return; }
      const result = exportChatBlock(path.join(root, "output/2026"), block);
      const stat = fs.statSync(result.path);
      response.writeHead(200, { "Content-Type": "text/csv; charset=utf-8",
        "Content-Length": stat.size, "Cache-Control": "no-store",
        "Content-Disposition": `attachment; filename="${result.filename}"`,
        "X-Content-Type-Options": "nosniff" });
      fs.createReadStream(result.path).pipe(response);
    } catch (error) { sendJson(response, 500, { error: error.message }); }
    return;
  }
  if (["/api/blocks/start", "/api/blocks/end"].includes(pathname)) {
    if (request.method !== "POST") { sendJson(response, 405, { error: "Método inválido" }); return; }
    const origin = request.headers.origin;
    if (origin && origin !== `http://127.0.0.1:${port}`) {
      sendJson(response, 403, { error: "Origem inválida" }); return;
    }
    try {
      const input = await readSmallJson(request);
      const blocks = readBlocks();
      const open = blocks.find(block => !block.ended_at_utc);
      if (pathname.endsWith("/start")) {
        const name = String(input.name || "").trim();
        if (!name || name.length > 80) { sendJson(response, 400, { error: "Nome do bloco: 1 a 80 caracteres" }); return; }
        if (open) { sendJson(response, 409, { error: `Encerre primeiro o bloco “${open.name}”` }); return; }
        let state;
        try { state = JSON.parse(fs.readFileSync(path.join(root, "output/2026/chat_estado.json"), "utf8")); }
        catch { state = {}; }
        if (state.phase !== "collecting") {
          sendJson(response, 409, { error: "Inicie a marcação quando o chat estiver em coleta" }); return;
        }
        if (Date.now() - Date.parse(state.status_updated_at_utc || "") > 60000 ||
            !Number.isFinite(Date.parse(state.status_updated_at_utc || ""))) {
          sendJson(response, 409, { error: "Coleta sem atualização recente; verifique o terminal" }); return;
        }
        blocks.push({ id: randomUUID(), name, started_at_utc: new Date().toISOString(),
          video_id: state.video_id });
      } else {
        if (!open) { sendJson(response, 409, { error: "Não há bloco aberto" }); return; }
        open.ended_at_utc = new Date().toISOString();
      }
      saveBlocks(blocks);
      let exportError = "";
      if (pathname.endsWith("/end")) {
        try { exportChatBlock(path.join(root, "output/2026"), open); }
        catch (error) { exportError = error.message; }
      }
      sendJson(response, 200, { blocks: publicBlocks(blocks), export_error: exportError });
    } catch (error) {
      sendJson(response, 400, { error: error.message || "Não foi possível salvar o bloco" });
    }
    return;
  }
  if (pathname === "/api/chat-status" && request.method === "GET") {
    const statePath = path.join(root, "output/2026/chat_estado.json");
    fs.readFile(statePath, "utf8", (error, content) => {
      let state;
      try {
        state = error ? { phase: "idle" } : JSON.parse(content);
      } catch {
        state = { phase: "unavailable", status_message: "Estado temporariamente indisponível" };
      }
      const allowed = ["phase", "video_id", "video_title", "status_message",
        "status_updated_at_utc", "last_check_at_utc", "started_at_utc",
        "first_response_at_utc", "last_response_at_utc", "last_message_at_utc",
        "ended_at_utc", "total_messages", "pages", "last_batch_messages",
        "recent_batches", "end_reason", "complete", "coverage_verified"];
      const publicState = Object.fromEntries(allowed.filter(key => state[key] !== undefined)
        .map(key => [key, state[key]]));
      const updated = Date.parse(publicState.status_updated_at_utc || "");
      publicState.stale = ["starting", "waiting_for_live", "collecting"].includes(publicState.phase)
        && (!Number.isFinite(updated) || Date.now() - updated > 60000);
      try {
        const coverage = JSON.parse(fs.readFileSync(path.join(root, "output/2026/lacunas_coleta.json"), "utf8"));
        publicState.gaps = coverage.video_id === publicState.video_id ? coverage.gaps || [] : [];
      } catch { publicState.gaps = []; }
      fs.stat(path.join(root, "output/2026/chat_ao_vivo.csv"), (csvError, stat) => {
        publicState.csv_exists = !csvError && stat.isFile();
        publicState.csv_bytes = publicState.csv_exists ? stat.size : 0;
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
        response.end(JSON.stringify(publicState));
      });
    });
    return;
  }
  const route = routes.get(pathname);
  if (!route || !["GET", "HEAD"].includes(request.method)) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Página não encontrada");
    return;
  }
  const [relativePath, contentType] = route;
  const filePath = path.join(root, relativePath);
  fs.stat(filePath, (error, stat) => {
    if (error || !stat.isFile()) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Arquivo não encontrado");
      return;
    }
    response.writeHead(200, {
      "Content-Type": contentType,
      "Content-Length": stat.size,
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    if (request.method === "HEAD") response.end();
    else fs.createReadStream(filePath).pipe(response);
  });
}).listen(port, "127.0.0.1", () => {
  console.log(`Painel: http://127.0.0.1:${port}`);
  console.log("Pressione Ctrl+C para encerrar.");
});
