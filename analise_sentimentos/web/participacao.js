(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const n = new Intl.NumberFormat("pt-BR");
  const d = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const clock = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" });
  const pct = (a, b) => b ? `${d.format(a / b * 100)}%` : "—";
  const seconds = value => value === null ? "—" : `${Math.floor(value / 60)}min ${Math.round(value % 60)}s`;
  const labels = { positivo: "Positivo", negativo: "Negativo", neutro: "Neutro", incerto: "Incerto", sem_referencia: "Sem referência" };
  let data;
  let loading;
  let page = 1;
  let filteredAccounts = [];
  const perPage = 12;

  function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "") node.textContent = String(text);
    return node;
  }
  function card(title, eyebrow = "") {
    const node = el("section", "card participation-card");
    if (eyebrow) node.append(el("p", "eyebrow dark", eyebrow));
    node.append(el("h3", "", title)); return node;
  }
  function metric(value, title, note) {
    const node = el("article", "card participation-metric");
    node.append(el("span", "participation-metric-label", title), el("strong", "participation-metric-number", value), el("p", "footnote", note));
    return node;
  }
  function bar(label, value, max, note = "", color = "") {
    const row = el("div", "participation-bar-row");
    const head = el("div", "participation-bar-head");
    head.append(el("span", "", label), el("strong", "", n.format(value)));
    const track = el("div", "participation-bar-track"); const fill = el("span");
    fill.style.width = `${max ? value / max * 100 : 0}%`; if (color) fill.style.background = color;
    track.append(fill); row.append(head, track); if (note) row.append(el("small", "", note)); return row;
  }
  function legend(text, color) { const node = el("span"); const dot = el("i"); dot.style.background = color; node.append(dot, document.createTextNode(text)); return node; }
  function table(headers) {
    const wrap = el("div", "table-wrap"); const node = el("table"); const head = el("thead"); const tr = el("tr");
    for (const title of headers) tr.append(el("th", "", title)); head.append(tr); const body = el("tbody"); node.append(head, body); wrap.append(node);
    return { wrap, body };
  }

  function render() {
    const container = $("participationContent"); container.replaceChildren(); const s = data.summary;
    const metrics = el("div", "participation-metrics");
    metrics.append(metric(n.format(s.text), "Mensagens comuns capturadas", `${n.format(s.events)} eventos no total dos quatro blocos.`),
      metric(n.format(s.textAccounts), "Contas com mensagens comuns", `${n.format(s.accounts)} contas considerando também eventos pagos.`),
      metric(pct(s.singleAccounts, s.textAccounts), "Uma ocorrência no recorte", `${n.format(s.singleAccounts)} contas com uma mensagem comum registrada.`),
      metric(n.format(s.trajectoryAccounts), "Contas com sequência analisável", "Pelo menos três mensagens comuns capturadas."));
    container.append(metrics);
    const row = el("div", "participation-grid");
    const frequency = card("Quantas vezes cada conta apareceu?", "INTENSIDADE");
    for (const item of data.histogram) frequency.append(bar(item.label, item.accounts, s.textAccounts, `${pct(item.accounts, s.textAccounts)} das contas com mensagens comuns`));
    frequency.append(el("p", "footnote", `${n.format(s.recurrentAccounts)} contas têm duas ou mais mensagens capturadas. Isso descreve a base disponível, sem garantir o histórico completo de publicação.`));
    const format = card("Texto comum e eventos pagos", "FORMATO DA PARTICIPAÇÃO");
    format.append(bar("Mensagens comuns", data.types.text, s.events, pct(data.types.text, s.events)),
      bar("Super Chats", data.types.superchat, s.events, pct(data.types.superchat, s.events), "#b38547"),
      bar("Stickers pagos", data.types.sticker, s.events, pct(data.types.sticker, s.events), "#9d7c9e"),
      el("p", "footnote", "As quantidades incluem eventos pagos sem texto classificável. Não representam receita: os valores monetários não foram preservados em campos estruturados."));
    row.append(frequency, format); container.append(row);

    const blockCard = card("A participação ao longo dos blocos", "DISTRIBUIÇÃO TEMPORAL");
    const blocks = el("div", "participation-block-grid");
    for (const block of data.blocks) {
      const node = el("article", "participation-block");
      node.append(el("h4", "", block.name), el("p", "block-clock", `${clock.format(block.start)} – ${clock.format(block.end)}`),
        el("strong", "", n.format(block.text)), el("span", "", "mensagens comuns"),
        el("p", "footnote", `${n.format(block.accounts)} contas · ${n.format(block.paid)} eventos pagos`)); blocks.append(node);
    }
    blockCard.append(blocks);
    const periods = el("div", "participation-periods");
    for (const [index, name] of ["Início", "Meio", "Fim"].entries()) {
      const count = data.accounts.reduce((sum, a) => sum + a.periods[index], 0);
      const authors = data.accounts.filter(a => a.periods[index] > 0).length;
      periods.append(bar(name, count, s.text, `${n.format(authors)} contas observadas`));
    }
    blockCard.append(periods, el("p", "footnote", data.meta.periods)); container.append(blockCard);

    const patterns = el("div", "participation-grid");
    const repetition = card("Textos diferentes e repetições", "COMPORTAMENTO OBSERVÁVEL");
    repetition.append(bar("Textos distintos na própria conta", s.text - s.repetitions, s.text, pct(s.text - s.repetitions, s.text)),
      bar("Repetições adicionais na própria conta", s.repetitions, s.text, pct(s.repetitions, s.text), "#b38547"),
      el("p", "footnote", data.meta.repetitions));
    const facts = el("div", "participation-facts");
    facts.append(metric(n.format(s.questionMessages), "Mensagens com ?", `${pct(s.questionMessages, s.text)} dos textos; o sinal não comprova uma pergunta real.`),
      metric(seconds(s.medianInterval), "Intervalo mediano observado", `${n.format(s.intervalPairs)} pares consecutivos válidos.`));
    repetition.append(facts, el("p", "footnote", data.meta.intervals));
    const mentions = card("Referências que aparecem juntas", "COOCORRÊNCIA");
    for (const [key, title] of [["lula", "Somente Lula"], ["flavio", "Somente Flávio"], ["both", "Ambos na mesma mensagem"], ["none", "Sem referência detectada"]]) {
      mentions.append(bar(title, data.cooccurrence[key], s.text, pct(data.cooccurrence[key], s.text)));
    }
    mentions.append(el("p", "footnote", "Referências identificadas pelas regras existentes, incluindo casos ambíguos. Coocorrência não indica apoio ou oposição."));
    patterns.append(repetition, mentions); container.append(patterns);

    const timeline = card("Como o tom das mensagens varia no tempo", "TRAJETÓRIA DE SENTIMENTO");
    const controls = el("div", "participation-chart-controls");
    const label = el("label", "inline-label", "Leitura do sentimento"); const select = el("select"); select.id = "participationTimelineTarget";
    for (const [value, text] of [["general", "Frase inteira"], ["lula", "Associado a Lula"], ["flavio", "Associado a Flávio"]]) { const option = el("option", "", text); option.value = value; select.append(option); }
    label.append(select); const keys = el("div", "participation-legend"); keys.append(legend("Positivas", "#16846b"), legend("Negativas", "#be4c50")); controls.append(label, keys);
    const chart = el("div", "participation-chart"); chart.id = "participationTimeline";
    timeline.append(controls, chart, el("p", "footnote", data.meta.timeline),
      el("p", "footnote", "Os rótulos descrevem textos. Alterações nas proporções não comprovam mudança real de opinião dos participantes."));
    const details = el("details", "participation-details"); details.append(el("summary", "", "Consultar os números das janelas"));
    const timeTable = table(["Bloco / horário", "Classificadas", "Positivas", "Negativas", "Exibição"]); timeTable.body.id = "participationWindowRows"; details.append(timeTable.wrap); timeline.append(details);
    container.append(timeline);
    select.addEventListener("change", renderTimeline); renderTimeline();

    const accounts = card("Sequências e características das contas", "EXPLORAÇÃO DESCRITIVA");
    accounts.append(el("p", "footnote", `${n.format(s.trajectoryAccounts)} contas têm ao menos três mensagens; ${n.format(s.varyingAccounts)} delas receberam mais de uma classe de sentimento geral. Códigos representam contas, não identidades políticas. A diversidade lexical é a razão entre palavras diferentes e total de palavras; poucos textos tornam essa medida instável.`));
    const filters = el("div", "explorer-filters");
    const searchLabel = el("label", "", "Buscar código da conta"); const search = el("input"); search.id = "participationAccountSearch"; search.type = "search"; search.placeholder = "Ex.: Conta 00001"; searchLabel.append(search);
    const groupLabel = el("label", "", "Recorte de contas"); const group = el("select"); group.id = "participationAccountGroup";
    for (const [value, title] of [["all", "Todas"], ["trajectory", "Com três ou mais mensagens"], ["repeated", "Com repetição de texto"], ["paid", "Com eventos pagos"]]) { const option = el("option", "", title); option.value = value; group.append(option); } groupLabel.append(group);
    const orderLabel = el("label", "", "Ordenar por"); const order = el("select"); order.id = "participationAccountOrder";
    for (const [value, title] of [["text", "Mais mensagens comuns"], ["repetitions", "Mais repetições"], ["paid", "Mais eventos pagos"]]) { const option = el("option", "", title); option.value = value; order.append(option); } orderLabel.append(order);
    filters.append(searchLabel, groupLabel, orderLabel); accounts.append(filters);
    const note = el("p", "footnote"); note.id = "participationAccountNote"; accounts.append(note);
    const accountTable = table(["Conta", "Textos", "Pagos", "Repetições", "Com ?", "Diversidade", "Sequência"]); accountTable.body.id = "participationAccountRows"; accounts.append(accountTable.wrap);
    const pagination = el("div", "pagination"); const pageLabel = el("span"); pageLabel.id = "participationAccountPage";
    const buttons = el("div"); const prev = el("button", "button subtle", "Anterior"); const next = el("button", "button subtle", "Próxima"); const csv = el("button", "button", "Exportar contas");
    prev.id = "participationPrev"; next.id = "participationNext";
    buttons.append(prev, next, csv); pagination.append(pageLabel, buttons); accounts.append(pagination); container.append(accounts);
    for (const input of [search, group, order]) input.addEventListener("input", () => { page = 1; renderAccounts(); });
    prev.addEventListener("click", () => { page--; renderAccounts(); }); next.addEventListener("click", () => { page++; renderAccounts(); }); csv.addEventListener("click", exportAccounts);
    renderAccounts();

    const expressions = card("Expressões mais repetidas no recorte", "TEXTOS COMPARTILHADOS");
    expressions.append(el("p", "footnote", "Textos completos iguais após normalizar caixa, espaços e Unicode, inclusive quando publicados por contas diferentes. Frequência de uma expressão não prova coordenação ou automação."));
    const expressionTable = table(["Texto normalizado", "Ocorrências"]);
    for (const item of data.expressions) { const tr = el("tr"); tr.append(el("td", "message-text", item.text), el("td", "", n.format(item.count))); expressionTable.body.append(tr); }
    expressions.append(expressionTable.wrap); container.append(expressions);
    $("closeAccountDialog").addEventListener("click", () => $("accountDialog").close());
  }

  function svg(tag, attrs = {}, text = "") {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text) node.textContent = text; return node;
  }
  function renderTimeline() {
    const target = $("participationTimelineTarget").value;
    const chart = svg("svg", { viewBox: "0 0 960 280", role: "img", "aria-label": "Proporção de mensagens positivas e negativas ao longo dos quatro blocos" });
    const first = data.blocks[0].start, last = data.blocks[data.blocks.length - 1].end;
    const x = value => 48 + (value - first) / (last - first) * 880;
    const y = value => 220 - value * 1.8;
    for (const value of [0, 25, 50, 75, 100]) { chart.append(svg("line", { x1: 48, x2: 928, y1: y(value), y2: y(value), stroke: "#e5ebe1" }), svg("text", { x: 38, y: y(value) + 4, "text-anchor": "end", class: "svg-label" }, `${value}%`)); }
    for (const [index, block] of data.blocks.entries()) {
      const bins = data.timeline.filter(b => b.block === index);
      chart.append(svg("text", { x: (x(block.start) + x(block.end)) / 2, y: 258, "text-anchor": "middle", class: "svg-label" }, block.name.replace(" - Livre", "")));
      for (const [key, color] of [["positivo", "#16846b"], ["negativo", "#be4c50"]]) {
        let points = [];
        const flush = () => { if (points.length > 1) chart.append(svg("polyline", { points: points.join(" "), fill: "none", stroke: color, "stroke-width": 2.8, "stroke-linejoin": "round" })); points = []; };
        for (const bin of bins) {
          const counts = bin[target];
          if (bin.partial || counts.total < 5) { flush(); continue; }
          const value = counts[key] / counts.total * 100;
          const px = x((bin.start + bin.end) / 2), py = y(value);
          points.push(`${px},${py}`);
          const dot = svg("circle", { cx: px, cy: py, r: 4, fill: color, stroke: "white", "stroke-width": 1.5 });
          dot.append(svg("title", {}, `${block.name} · ${clock.format(bin.start)} · ${labels[key]}: ${pct(counts[key], counts.total)} (${counts[key]}/${counts.total})`)); chart.append(dot);
        }
        flush();
      }
    }
    $("participationTimeline").replaceChildren(chart);
    const body = $("participationWindowRows"); body.replaceChildren();
    for (const bin of data.timeline) { const counts = bin[target]; const tr = el("tr");
      for (const text of [`${data.blocks[bin.block].name} · ${clock.format(bin.start)}–${clock.format(bin.end)}`, n.format(counts.total), pct(counts.positivo, counts.total), pct(counts.negativo, counts.total), bin.partial ? "Registros parciais" : counts.total < 5 ? "Base pequena" : "Exibida"]) tr.append(el("td", "", text)); body.append(tr);
    }
  }

  function renderAccounts() {
    const query = $("participationAccountSearch").value.toLowerCase().trim();
    const group = $("participationAccountGroup").value; const order = $("participationAccountOrder").value;
    filteredAccounts = data.accounts.filter(a => (!query || a.code.toLowerCase().includes(query)) &&
      (group === "all" || group === "trajectory" && a.text >= 3 || group === "repeated" && a.repetitions > 0 || group === "paid" && a.paid > 0))
      .sort((a, b) => b[order] - a[order] || a.code.localeCompare(b.code));
    const pages = Math.max(1, Math.ceil(filteredAccounts.length / perPage)); page = Math.max(1, Math.min(page, pages));
    $("participationAccountNote").textContent = `${n.format(filteredAccounts.length)} contas neste filtro. Textos e eventos pagos são contagens separadas. A sequência exige três mensagens comuns.`;
    const body = $("participationAccountRows"); body.replaceChildren();
    for (const account of filteredAccounts.slice((page - 1) * perPage, page * perPage)) {
      const tr = el("tr"); for (const value of [account.code, account.text, account.paid, account.repetitions, account.questions, account.lexicalDiversity === null ? "—" : pct(account.lexicalDiversity, 1)]) tr.append(el("td", "", value));
      const cell = el("td"); const button = el("button", "inspect-button", account.text >= 3 ? "Ver sequência" : "Menos de 3 textos"); button.disabled = account.text < 3;
      button.addEventListener("click", () => inspectAccount(account)); cell.append(button); tr.append(cell); body.append(tr);
    }
    if (!filteredAccounts.length) { const tr = el("tr"); const td = el("td", "empty", "Nenhuma conta encontrada."); td.colSpan = 7; tr.append(td); body.append(tr); }
    $("participationAccountPage").textContent = `Página ${page} de ${n.format(pages)}`;
    $("participationPrev").disabled = page <= 1; $("participationNext").disabled = page >= pages;
  }
  function inspectAccount(account) {
    $("accountDialogTitle").textContent = `${account.code} · sequência capturada`;
    const content = $("accountDialogContent"); content.replaceChildren();
    content.append(el("p", "footnote", "A sequência descreve mudanças nos textos classificados, não comprova mudança de opinião. O código da conta substitui seu identificador original."));
    const heat = el("div", "account-blocks");
    for (const [index, block] of data.blocks.entries()) { const node = el("div"); node.append(el("small", "", block.name), el("strong", "", account.blocks[index])); heat.append(node); } content.append(heat);
    for (const message of account.messages) {
      const row = el("article", "account-message"); const label = el("span", `pill ${message.label}`, labels[message.label]);
      const heading = el("div", "account-message-head"); heading.append(el("small", "", `${clock.format(message.time)} · ${data.blocks[message.block].name}`), label);
      row.append(heading, el("p", "", message.text), el("small", "", `Lula: ${labels[message.lula]} · Flávio: ${labels[message.flavio]}`)); content.append(row);
    }
    $("accountDialog").showModal();
  }
  function exportAccounts() {
    const rows = [["conta", "mensagens_comuns_capturadas", "eventos_pagos", "textos_distintos_na_conta", "repeticoes_na_conta", "mensagens_com_interrogacao", "diversidade_lexical", "intervalo_mediano_segundos"]];
    for (const a of filteredAccounts) rows.push([a.code, a.text, a.paid, a.distinct, a.repetitions, a.questions, a.lexicalDiversity ?? "", a.medianInterval ?? ""]);
    const csv = rows.map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" })); const a = el("a"); a.href = url; a.download = "eleisent_participacao_capturada.csv"; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function open() {
    if (data) return;
    if (loading) return loading;
    loading = (async () => {
      try { const response = await fetch("/api/participacao", { cache: "no-store" }); if (!response.ok) throw new Error(`HTTP ${response.status}`); data = await response.json(); render(); }
      catch (error) { loading = null; $("participationContent").replaceChildren(el("p", "notice error", `Não foi possível carregar a participação: ${error.message}`)); }
    })();
    return loading;
  }
  globalThis.EleiSentParticipation = { open };
})();
