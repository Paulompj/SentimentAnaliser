"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const net = require("node:net");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

async function freePort() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test("o painel serve os arquivos movidos para o pacote", async t => {
  const port = await freePort();
  const child = spawn(process.execPath, ["scripts/servir_painel.js", String(port)],
    { cwd: root, stdio: ["ignore", "pipe", "pipe"] });
  t.after(() => child.kill());

  let timeout;
  await Promise.race([
    new Promise((resolve, reject) => {
      child.stdout.on("data", chunk => {
        if (chunk.toString().includes("Painel:")) resolve();
      });
      child.once("exit", code => reject(new Error(`Servidor encerrou: ${code}`)));
    }),
    new Promise((_, reject) => {
      timeout = setTimeout(() => reject(new Error("Servidor não iniciou")), 5000);
    }),
  ]).finally(() => clearTimeout(timeout));

  for (const route of ["/", "/coleta", "/resultados", "/resultados.css", "/termometro.css", "/participacao.css", "/participacao.js", "/resultados.js", "/bertweet_metrics.js"]) {
    const response = await fetch(`http://127.0.0.1:${port}${route}`);
    assert.equal(response.status, 200, route);
    assert.ok((await response.text()).length > 0, route);
  }
  const home = await fetch(`http://127.0.0.1:${port}/`, { redirect: "manual" });
  assert.equal(home.status, 302);
  assert.equal(home.headers.get("location"), "/resultados");
  for (const route of ["/rotulacao", "/rotulacao.js", "/rotulacao.css", "/api/rotulacao", "/api/rotulacao.csv", "/app.js", "/dados"]) {
    const response = await fetch(`http://127.0.0.1:${port}${route}`);
    assert.equal(response.status, 404, route);
  }
  const writeLabels = await fetch(`http://127.0.0.1:${port}/api/rotulacao`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
  });
  assert.equal(writeLabels.status, 404);
  for (const route of ["/assets/lula.jpg", "/assets/flavio.jpg"]) {
    const response = await fetch(`http://127.0.0.1:${port}${route}`);
    assert.equal(response.status, 200, route);
    assert.equal(response.headers.get("content-type"), "image/jpeg");
    const bytes = new Uint8Array(await response.arrayBuffer());
    assert.deepEqual([...bytes.slice(0, 2)], [0xff, 0xd8], "JPEG esperado");
  }
});
