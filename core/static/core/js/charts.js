/* Gráficos D3 do relatório do aluno. Paleta e specs seguem a skill de dataviz
   do projeto: cor por último, sequential = 1 matiz, diverging = azul/vermelho
   com meio neutro, hover em toda marca, view de tabela sempre disponível. */
(function () {
  "use strict";

  const PALETTE = {
    seqBlue: "#2a78d6",
    seqAqua: "#1baf7a",
    divPositive: "#2a78d6",
    divNegative: "#e34948",
    neutralGrid: "#e1e0d9",
    baseline: "#c3c2b7",
    textPrimary: "#0b0b0b",
    textSecondary: "#52514e",
    textMuted: "#898781",
    surface: "#fcfcfb",
  };

  function fmt(n, decimals = 1) {
    return Number(n).toLocaleString("pt-BR", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function makeTooltip(root) {
    return d3
      .select(root)
      .append("div")
      .attr("class", "viz-tooltip")
      .style("opacity", 0);
  }

  function showTooltip(tooltip, event, root, html) {
    const rootRect = root.getBoundingClientRect();
    tooltip
      .html(html)
      .style("opacity", 1)
      .style("left", event.clientX - rootRect.left + 14 + "px")
      .style("top", event.clientY - rootRect.top - 10 + "px");
  }

  function hideTooltip(tooltip) {
    tooltip.style("opacity", 0);
  }

  /* Alterna entre o SVG e uma <table> simples com os mesmos dados — a
     "relief rule" da skill (labels visíveis ou tabela) e o requisito de
     interação clicável. */
  function addTableToggle(root, svgEl, buildTable) {
    const btn = d3
      .select(root)
      .append("button")
      .attr("type", "button")
      .attr("class", "viz-toggle")
      .text("Ver como tabela");
    const tableWrap = d3.select(root).append("div").attr("class", "viz-table-wrap");
    tableWrap.style("display", "none");
    buildTable(tableWrap);

    let showingTable = false;
    btn.on("click", () => {
      showingTable = !showingTable;
      d3.select(svgEl).style("display", showingTable ? "none" : null);
      tableWrap.style("display", showingTable ? null : "none");
      btn.text(showingTable ? "Ver como gráfico" : "Ver como tabela");
    });
  }

  function buildSimpleTable(wrap, columns, rows) {
    const table = wrap.append("table");
    const thead = table.append("thead").append("tr");
    columns.forEach((c) => thead.append("th").text(c.label));
    const tbody = table.append("tbody");
    rows.forEach((row) => {
      const tr = tbody.append("tr");
      columns.forEach((c) => tr.append("td").text(c.value(row)));
    });
  }

  /* Barras horizontais, um valor por categoria. `diverging: true` colore
     positivo/negativo com o par azul/vermelho e ancora no zero; senão usa
     um hue sequencial único. Clique numa barra fixa o tooltip (mobile-friendly). */
  function renderBarChart(containerId, data, opts) {
    const root = document.getElementById(containerId);
    if (!root || !data.length) {
      if (root) root.innerHTML = '<p class="viz-empty">Sem dados ainda.</p>';
      return;
    }
    const { labelKey, valueKey, valueFormat = (v) => fmt(v), diverging = false, unit = "" } = opts;

    const barHeight = 28;
    const gap = 10;
    const width = root.clientWidth || 640;

    // mede o rótulo mais largo de verdade em vez de chutar uma margem fixa —
    // nomes de disciplina em português variam muito de comprimento.
    const measureSvg = d3.select(root).append("svg").attr("width", 0).attr("height", 0);
    const measureText = measureSvg.append("text").attr("font-size", 13);
    let maxLabelWidth = 0;
    data.forEach((d) => {
      measureText.text(d[labelKey]);
      maxLabelWidth = Math.max(maxLabelWidth, measureText.node().getComputedTextLength());
    });
    measureSvg.remove();
    const labelMargin = Math.min(Math.ceil(maxLabelWidth) + 24, width * 0.45);

    const margin = { top: 8, right: 56, bottom: 8, left: labelMargin };
    const height = data.length * (barHeight + gap) + margin.top + margin.bottom;

    const svg = d3
      .select(root)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("role", "img")
      .attr("aria-label", opts.ariaLabel || "Gráfico de barras");

    const innerWidth = width - margin.left - margin.right;

    const maxAbs = d3.max(data, (d) => Math.abs(d[valueKey])) || 1;
    const x = diverging
      ? d3.scaleLinear().domain([-maxAbs, maxAbs]).range([0, innerWidth]).nice()
      : d3.scaleLinear().domain([0, maxAbs]).range([0, innerWidth]).nice();

    const zeroX = x(0);

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    // gridline de base (zero)
    g.append("line")
      .attr("x1", zeroX)
      .attr("x2", zeroX)
      .attr("y1", 0)
      .attr("y2", data.length * (barHeight + gap) - gap)
      .attr("stroke", PALETTE.baseline)
      .attr("stroke-width", 1);

    const tooltip = makeTooltip(root);

    const rows = g
      .selectAll("g.bar-row")
      .data(data)
      .join("g")
      .attr("class", "bar-row")
      .attr("transform", (d, i) => `translate(0,${i * (barHeight + gap)})`);

    // label da categoria, à esquerda
    rows
      .append("text")
      .attr("x", -12)
      .attr("y", barHeight / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .attr("fill", PALETTE.textSecondary)
      .attr("font-size", 13)
      .text((d) => d[labelKey]);

    rows
      .append("rect")
      .attr("class", "bar-mark")
      .attr("y", 4)
      .attr("height", barHeight - 8)
      .attr("rx", 4)
      .attr("x", (d) => (diverging ? Math.min(zeroX, x(d[valueKey])) : 0))
      .attr("width", (d) =>
        diverging ? Math.abs(x(d[valueKey]) - zeroX) : Math.max(1, x(d[valueKey]))
      )
      .attr("fill", (d) =>
        diverging ? (d[valueKey] >= 0 ? PALETTE.divPositive : PALETTE.divNegative) : PALETTE.seqBlue
      )
      .attr("tabindex", 0)
      .style("cursor", "pointer")
      .on("pointerenter focus", function (event) {
        d3.select(this).attr("opacity", 0.82);
      })
      .on("pointermove click", function (event, d) {
        showTooltip(
          tooltip,
          event,
          root,
          `<strong>${valueFormat(d[valueKey])}${unit}</strong><br><span>${d[labelKey]}</span>`
        );
      })
      .on("pointerleave blur", function () {
        d3.select(this).attr("opacity", 1);
        hideTooltip(tooltip);
      });

    // valor direto ao fim da barra (sempre visível — mitiga o WARN de contraste da skill)
    rows
      .append("text")
      .attr("y", barHeight / 2)
      .attr("dy", "0.35em")
      .attr("x", (d) =>
        diverging
          ? x(d[valueKey]) + (d[valueKey] >= 0 ? 6 : -6)
          : Math.max(1, x(d[valueKey])) + 6
      )
      .attr("text-anchor", (d) => (diverging && d[valueKey] < 0 ? "end" : "start"))
      .attr("fill", PALETTE.textPrimary)
      .attr("font-size", 12.5)
      .attr("font-weight", 600)
      .text((d) => valueFormat(d[valueKey]) + unit);

    addTableToggle(root, svg.node(), (wrap) =>
      buildSimpleTable(
        wrap,
        [
          { label: opts.tableLabelHeader || "Categoria", value: (d) => d[labelKey] },
          { label: opts.tableValueHeader || "Valor", value: (d) => valueFormat(d[valueKey]) + unit },
        ],
        data
      )
    );
  }

  /* Barras agrupadas — duas séries por categoria (aluno vs. média geral). */
  function renderGroupedBarChart(containerId, data, opts) {
    const root = document.getElementById(containerId);
    if (!root || !data.length) {
      if (root) root.innerHTML = '<p class="viz-empty">Sem dados ainda.</p>';
      return;
    }
    const { labelKey, series, unit = "" } = opts; // series: [{key, name, color}]

    const margin = { top: 12, right: 16, bottom: 34, left: 44 };
    const width = root.clientWidth || 640;
    const groupHeight = 220;
    const height = groupHeight + margin.top + margin.bottom;

    const svg = d3
      .select(root)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", `0 0 ${width} ${height}`)
      .attr("role", "img")
      .attr("aria-label", opts.ariaLabel || "Gráfico de barras agrupadas");

    const innerWidth = width - margin.left - margin.right;
    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const x0 = d3.scaleBand().domain(data.map((d) => d[labelKey])).range([0, innerWidth]).padding(0.35);
    const x1 = d3.scaleBand().domain(series.map((s) => s.key)).range([0, x0.bandwidth()]).padding(0.15);
    const maxVal = d3.max(data, (d) => d3.max(series, (s) => d[s.key])) || 1;
    const y = d3.scaleLinear().domain([0, maxVal]).range([groupHeight, 0]).nice();

    g.append("g")
      .attr("transform", `translate(0,${groupHeight})`)
      .call(d3.axisBottom(x0).tickSize(0))
      .call((sel) => sel.select(".domain").attr("stroke", PALETTE.baseline))
      .selectAll("text")
      .attr("fill", PALETTE.textSecondary)
      .attr("font-size", 12);

    g.append("g")
      .call(d3.axisLeft(y).ticks(4).tickSize(-innerWidth))
      .call((sel) => sel.select(".domain").remove())
      .call((sel) => sel.selectAll("line").attr("stroke", PALETTE.neutralGrid))
      .selectAll("text")
      .attr("fill", PALETTE.textMuted)
      .attr("font-size", 11);

    const tooltip = makeTooltip(root);

    const groups = g
      .selectAll("g.group")
      .data(data)
      .join("g")
      .attr("transform", (d) => `translate(${x0(d[labelKey])},0)`);

    series.forEach((s) => {
      groups
        .append("rect")
        .attr("x", x1(s.key))
        .attr("width", x1.bandwidth())
        .attr("y", (d) => y(d[s.key]))
        .attr("height", (d) => groupHeight - y(d[s.key]))
        .attr("rx", 3)
        .attr("fill", s.color)
        .attr("tabindex", 0)
        .style("cursor", "pointer")
        .on("pointerenter focus", function () {
          d3.select(this).attr("opacity", 0.82);
        })
        .on("pointermove click", function (event, d) {
          showTooltip(
            tooltip,
            event,
            root,
            `<strong>${fmt(d[s.key])}${unit}</strong><br><span>${s.name} — ${d[labelKey]}</span>`
          );
        })
        .on("pointerleave blur", function () {
          d3.select(this).attr("opacity", 1);
          hideTooltip(tooltip);
        });
    });

    // legenda (obrigatória para 2+ séries)
    const legend = d3.select(root).append("div").attr("class", "viz-legend");
    series.forEach((s) => {
      const item = legend.append("span").attr("class", "viz-legend-item");
      item.append("span").attr("class", "viz-legend-swatch").style("background", s.color);
      item.append("span").text(s.name);
    });

    addTableToggle(root, svg.node(), (wrap) =>
      buildSimpleTable(
        wrap,
        [
          { label: "Categoria", value: (d) => d[labelKey] },
          ...series.map((s) => ({ label: s.name, value: (d) => fmt(d[s.key]) + unit })),
        ],
        data
      )
    );
  }

  window.PreparaEnemCharts = { renderBarChart, renderGroupedBarChart };
})();
