(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.BertweetMetrics = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  function select(records, options) {
    return records.filter(row =>
      row.block !== "1 parte" &&
      (options.block === "all" || options.block === "main" || row.block === options.block) &&
      (options.paid || !row.paid) && (!options.emoji || row.emojis.length > 0));
  }
  function candidateLabel(row, name) {
    return row[name];
  }
  function candidate(rows, name) {
    const counts = { positivo: 0, negativo: 0, neutro: 0, incerto: 0, sem_referencia: 0 };
    for (const row of rows) counts[candidateLabel(row, name)]++;
    const polarized = counts.positivo + counts.negativo;
    return { ...counts, mentions: rows.length - counts.sem_referencia, polarized,
      score: polarized ? 100 * (counts.positivo - counts.negativo) / polarized : null };
  }
  function summarize(rows) {
    const general = { positivo: 0, negativo: 0, neutro: 0 };
    for (const row of rows) general[row.label]++;
    return { rows: rows.length, general, lula: candidate(rows, "lula"),
      flavio: candidate(rows, "flavio"), emoji: rows.filter(r => r.emojis.length).length,
      cues: rows.filter(r => r.irony_cues.length).length,
      unique: new Set(rows.map(r => r.text)).size };
  }
  return { select, candidateLabel, candidate, summarize };
});
