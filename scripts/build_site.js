"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { readDashboard } = require("./bertweet_dashboard");
const { loadParticipation } = require("./participacao");

const publicFiles = ["resultados.css", "termometro.css", "participacao.css", "bertweet_metrics.js", "resultados.js", "participacao.js"];

function publicDashboard(data) {
  const fields = ["id", "block", "paid", "text", "prepared", "label", "p", "confidence", "lula", "flavio", "rule", "truncated", "emojis", "irony_cues"];
  return { audit: { status: data.audit.status, created_at_utc: data.audit.created_at_utc },
    records: data.records.filter(row => row.block !== "1 parte").map(row => Object.fromEntries(fields.filter(key => row[key] !== undefined).map(key => [key, row[key]]))),
    blocks: data.blocks.filter(name => name !== "1 parte"),
    experiments: { cases: data.experiments.cases } };
}

function buildSite(root = path.resolve(__dirname, "..")) {
  const data = readDashboard(root);
  if (data.audit.status !== "passed") throw new Error("Não é possível publicar uma auditoria reprovada");
  const participation = loadParticipation(root);
  const directory = path.join(root, "dist");
  if (fs.existsSync(directory) && fs.lstatSync(directory).isSymbolicLink()) throw new Error("Pasta de saída não pode ser um link");
  const allowed = new Set(["index.html", ...publicFiles, "assets/lula.jpg", "assets/flavio.jpg", "data/bertweet.json", "data/participacao.json"]);
  // Não publica arquivos inesperados que tenham sido deixados em dist/.
  function inspect(folder) {
    if (!fs.existsSync(folder)) return;
    for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
      const full = path.join(folder, entry.name);
      if (entry.isSymbolicLink()) throw new Error("Link inesperado na saída estática");
      if (entry.isDirectory()) inspect(full);
      else if (!allowed.has(path.relative(directory, full).split(path.sep).join("/"))) throw new Error(`Arquivo inesperado na saída: ${entry.name}`);
    }
  }
  inspect(directory);
  for (const name of [directory, path.join(directory, "assets"), path.join(directory, "data")]) fs.mkdirSync(name, { recursive: true });
  const web = path.join(root, "analise_sentimentos/web");
  fs.copyFileSync(path.join(web, "resultados.html"), path.join(directory, "index.html"));
  for (const name of publicFiles) fs.copyFileSync(path.join(web, name), path.join(directory, name));
  fs.copyFileSync(path.join(root, "Assets/Lula foto Oficial.jpg"), path.join(directory, "assets/lula.jpg"));
  fs.copyFileSync(path.join(root, "Assets/Flavio foto oficial.jpg"), path.join(directory, "assets/flavio.jpg"));
  fs.writeFileSync(path.join(directory, "data/bertweet.json"), JSON.stringify(publicDashboard(data)));
  fs.writeFileSync(path.join(directory, "data/participacao.json"), JSON.stringify(participation));
  console.log(`EleiSent pronto em dist/: ${participation.summary.text} mensagens comuns, ${participation.summary.textAccounts} contas e ${allowed.size} arquivos públicos.`);
  return { directory, files: [...allowed], summary: participation.summary };
}

if (require.main === module) buildSite();
module.exports = { buildSite, publicDashboard };
