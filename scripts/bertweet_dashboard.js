"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");

function readDashboard(root) {
  const target = path.join(root, "output/2026/bertweet_validacao/painel.json");
  if (!fs.existsSync(target)) {
    const error = new Error("Prepare os dados com .venv\\Scripts\\python.exe scripts\\validar_bertweet.py");
    error.status = 404; throw error;
  }
  const data = JSON.parse(fs.readFileSync(target, "utf8"));
  if (!data.audit.inputs || !Object.keys(data.audit.inputs).length) {
    const error = new Error("Auditoria sem manifesto de entrada. Execute scripts/validar_bertweet.py novamente.");
    error.status = 409; throw error;
  }
  for (const [relative, expected] of Object.entries(data.audit.inputs)) {
    const full = path.resolve(root, relative);
    if (!full.startsWith(path.resolve(root) + path.sep)) throw new Error("Caminho de auditoria inválido");
    const found = fs.existsSync(full) ? createHash("sha256").update(fs.readFileSync(full)).digest("hex") : null;
    if (found !== expected) {
      const error = new Error("Os arquivos mudaram desde a auditoria. Execute scripts/validar_bertweet.py novamente.");
      error.status = 409; throw error;
    }
  }
  return data;
}

module.exports = { readDashboard };
