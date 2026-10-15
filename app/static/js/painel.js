/* T05 – Painel (RD04): números do período e gráficos (Chart.js local). Os filtros valem para tudo, e cada gráfico
   tem a tabela "Ver dados" (acessibilidade). Clique num dia, turno ou posto -> Ocorrências já filtrada. */
"use strict";

(() => {
  const { api, el, numero, aviso } = EPI;
  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------- cores (validadas para daltonismo)
  const COR_SERIE = "#2a78d6";                       // uma série só (dia, posto)
  const COR_SEM_MASCARA = "#2a78d6", COR_LEVANTADA = "#eb6834";
  const COR_ESTADO = { conforme: "#198754", nao_conforme: "#DC3545", indeterminado: "#FFC107" };   // cores de estado
  const SUPERFICIE = "#FFFFFF";

  Chart.defaults.font.family = '"Atkinson Hyperlegible", "Segoe UI", Arial, sans-serif';
  Chart.defaults.font.size = 13;
  Chart.defaults.color = "#4A5661";
  Chart.defaults.borderColor = "#E1E6EB";
  Chart.defaults.locale = "pt-BR";
  if (EPI.movimentoReduzido()) Chart.defaults.animation = false;

  // ---------------------------------------------------------------- datas e filtros
  const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  const isoLocal = (d) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
  const deIso = (texto) => { const [a, m, d] = texto.split("-").map(Number); return new Date(a, m - 1, d); };
  const curta = (texto) => texto.slice(8, 10) + "/" + texto.slice(5, 7);
  const longa = (texto) => `${curta(texto)}/${texto.slice(0, 4)} (${SEMANA[deIso(texto).getDay()]})`;
  const pct = (fracao) => (fracao === null || fracao === undefined ? "—" : numero(fracao * 100) + "%");

  function hoje(deslocamento = 0) { const d = new Date(); d.setDate(d.getDate() + deslocamento); return isoLocal(d); }

  function filtros() {
    const params = new URLSearchParams();
    if ($("f-inicio").value) params.set("inicio", $("f-inicio").value);
    if ($("f-fim").value) params.set("fim", $("f-fim").value);
    if ($("f-posto").value) params.set("camera_id", $("f-posto").value);
    return params;
  }

  /** Endereço de Ocorrências com o posto do painel e os filtros pedidos. */
  function linkOcorrencias(extra) {
    const params = new URLSearchParams(extra);
    if ($("f-posto").value && !params.has("camera_id")) params.set("camera_id", $("f-posto").value);
    return "/ocorrencias?" + params.toString();
  }

  // ---------------------------------------------------------------- gráficos
  const graficos = {};

  /** Linha vertical no ponto em foco (o leitor mira o dia, não a linha de 2 px). */
  const miraVertical = {
    id: "miraVertical",
    afterDatasetsDraw(chart) {
      const ativo = chart.tooltip && chart.tooltip.getActiveElements()[0];
      if (!ativo) return;
      const { ctx, chartArea } = chart;
      ctx.save();
      ctx.strokeStyle = "#4A5661";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ativo.element.x, chartArea.top);
      ctx.lineTo(ativo.element.x, chartArea.bottom);
      ctx.stroke();
      ctx.restore();
    },
  };

  const eixoContagem = { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#E1E6EB" }, border: { display: false } };

  function aoClicar(destino) {
    return {
      onClick: (_evento, elementos) => { if (elementos.length) location.href = destino(elementos[0].index); },
      onHover: (evento, elementos) => { evento.native.target.style.cursor = elementos.length ? "pointer" : "default"; },
    };
  }

  function criarOuAtualizar(nome, canvas, criar, dados) {
    if (graficos[nome]) {
      graficos[nome].data = dados;
      graficos[nome].update();
    } else {
      graficos[nome] = new Chart(canvas, criar(dados));
    }
  }

  function grafico(nome, vazio, criar, dados) {
    const secao = $("g-" + nome).closest(".grafico");
    secao.querySelector(".grafico-area").hidden = vazio;
    secao.querySelector(".grafico-vazio").hidden = !vazio;
    criarOuAtualizar(nome, $("g-" + nome), criar, dados);
  }

  function porDia(d) {
    const dias = d.por_dia;
    grafico("dia", dias.every((x) => x.total === 0), (dados) => ({
      type: "line", data: dados, plugins: [miraVertical],
      options: {
        maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false },
          tooltip: { callbacks: { title: (itens) => longa(dias[itens[0].dataIndex].dia),
            label: (item) => ` ${numero(item.parsed.y)} ocorrência(s)` } } },
        scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkipPadding: 12 } }, y: eixoContagem },
        ...aoClicar((i) => linkOcorrencias({ inicio: dias[i].dia, fim: dias[i].dia })),
      },
    }), {
      labels: dias.map((x) => curta(x.dia)),
      datasets: [{ data: dias.map((x) => x.total), borderColor: COR_SERIE, backgroundColor: "rgba(42, 120, 214, .10)",
        fill: true, borderWidth: 2, tension: 0, pointRadius: dias.length > 45 ? 0 : 4, pointHoverRadius: 6,
        pointBackgroundColor: COR_SERIE, pointBorderColor: SUPERFICIE, pointBorderWidth: 2, pointHitRadius: 12 }],
    });
    $("d-dia").replaceChildren(...dias.map((x) => el("tr", {},
      el("td", {}, el("a", { href: linkOcorrencias({ inicio: x.dia, fim: x.dia }), texto: longa(x.dia) })),
      el("td", { classe: "text-end numero", texto: numero(x.total) }))));
  }

  function estados(d) {
    const e = d.estados;
    const total = e.conforme + e.nao_conforme + e.indeterminado;
    const nomes = { conforme: "Conforme", nao_conforme: "Não conforme", indeterminado: "Indeterminado" };
    const chaves = ["conforme", "nao_conforme", "indeterminado"];
    grafico("estados", total === 0, (dados) => ({
      type: "doughnut", data: dados,
      options: {
        maintainAspectRatio: false, cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, boxHeight: 12, padding: 14,
            generateLabels: (chart) => chart.data.labels.map((rotulo, i) => ({
              text: `${rotulo} ${pct(total ? chart.data.datasets[0].data[i] / total : null)}`,
              fillStyle: chart.data.datasets[0].backgroundColor[i], strokeStyle: SUPERFICIE, lineWidth: 0, index: i })) } },
          tooltip: { callbacks: { label: (item) => ` ${item.label}: ${pct(total ? item.parsed / total : null)} (${numero(item.parsed)})` } },
        },
      },
    }), {
      labels: chaves.map((k) => nomes[k]),
      datasets: [{ data: chaves.map((k) => e[k]), backgroundColor: chaves.map((k) => COR_ESTADO[k]),
        borderColor: SUPERFICIE, borderWidth: 2, hoverOffset: 4 }],
    });
    $("d-estados").replaceChildren(...chaves.map((k) => el("tr", {}, el("td", { texto: nomes[k] }),
      el("td", { classe: "text-end numero", texto: numero(e[k]) }),
      el("td", { classe: "text-end numero", texto: pct(total ? e[k] / total : null) }))));
  }

  function porTurno(d) {
    const turnos = d.por_turno;
    const nomeTurno = (t) => (t === "sem turno" ? "Sem turno" : `Turno ${t}`);
    const serie = (rotulo, cor, chave) => ({ label: rotulo, data: turnos.map((x) => x[chave]), backgroundColor: cor,
      borderColor: SUPERFICIE, borderWidth: { top: 2 }, borderSkipped: false, maxBarThickness: 24 });
    grafico("turno", turnos.every((x) => x.sem_mascara + x.levantada === 0), (dados) => ({
      type: "bar", data: dados,
      options: {
        maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12, boxHeight: 12, padding: 14 } } },
        scales: { x: { stacked: true, grid: { display: false } }, y: { ...eixoContagem, stacked: true } },
        ...aoClicar((i) => linkOcorrencias({ inicio: d.periodo.inicio, fim: d.periodo.fim,
          ...(turnos[i].turno === "sem turno" ? {} : { turno: turnos[i].turno }) })),
      },
    }), {
      labels: turnos.map((x) => nomeTurno(x.turno)),
      datasets: [serie("Sem máscara", COR_SEM_MASCARA, "sem_mascara"), serie("Máscara levantada", COR_LEVANTADA, "levantada")],
    });
    $("d-turno").replaceChildren(...turnos.map((x) => el("tr", {}, el("td", { texto: nomeTurno(x.turno) }),
      el("td", { classe: "text-end numero", texto: numero(x.sem_mascara) }),
      el("td", { classe: "text-end numero", texto: numero(x.levantada) }))));
  }

  function porPosto(d) {
    const postos = d.por_posto;
    grafico("posto", postos.length === 0, (dados) => ({
      type: "bar", data: dados,
      options: {
        indexAxis: "y", maintainAspectRatio: false,
        plugins: { legend: { display: false },
          tooltip: { callbacks: { label: (item) => ` ${numero(item.parsed.x)} ocorrência(s)` } } },
        scales: { x: eixoContagem, y: { grid: { display: false } } },
        ...aoClicar((i) => linkOcorrencias({ inicio: d.periodo.inicio, fim: d.periodo.fim, camera_id: postos[i].camera_id })),
      },
    }), {
      labels: postos.map((x) => x.posto),
      datasets: [{ data: postos.map((x) => x.total), backgroundColor: COR_SERIE, borderRadius: 4, borderSkipped: "start",
        maxBarThickness: 24 }],
    });
    $("d-posto").replaceChildren(...postos.map((x) => el("tr", {},
      el("td", {}, el("a", { href: linkOcorrencias({ inicio: d.periodo.inicio, fim: d.periodo.fim, camera_id: x.camera_id }),
        texto: x.posto })),
      el("td", { classe: "text-end numero", texto: numero(x.total) }))));
  }

  // ---------------------------------------------------------------- números principais
  function cartao(id, valor, nota) {
    $(id).querySelector(".numero-valor").textContent = valor;
    if (nota !== undefined) $(id).querySelector(".numero-nota").textContent = nota;
  }

  function numeros(d) {
    const c = d.cartoes;
    cartao("c-hoje", numero(c.hoje), c.hoje === 1 ? "ocorrência registrada" : "ocorrências registradas");
    $("c-hoje").href = linkOcorrencias({ inicio: hoje(), fim: hoje() });
    cartao("c-mes", numero(c.mes), c.mes === 1 ? "ocorrência registrada" : "ocorrências registradas");
    cartao("c-conformidade", pct(c.conformidade), c.conformidade === null ? "nenhuma pessoa avaliada no período"
      : `conformes ÷ (conformes + não conformes) · ${pct(c.indeterminado)} indeterminado à parte`);
    cartao("c-falsos", pct(c.falsos_positivos), c.validadas === 0 ? "nenhuma ocorrência validada no período"
      : `de ${numero(c.validadas)} validadas · ${numero(c.pendentes)} pendentes`);
    $("nota-arco").textContent = c.periodo
      ? `${numero(c.com_arco)} de ${numero(c.periodo)} ocorrências do período aconteceram com o arco aceso (solda em andamento).`
      : "";
  }

  // ---------------------------------------------------------------- relatório mensal em PDF (RD10)
  function linkPdf() {
    const pdf = new URLSearchParams();
    if ($("pdf-mes").value) pdf.set("mes", $("pdf-mes").value);
    if ($("f-posto").value) pdf.set("camera_id", $("f-posto").value);
    $("baixar-pdf").href = "/api/relatorios/mensal.pdf?" + pdf.toString();
  }
  $("pdf-mes").value = $("pdf-mes").max = hoje().slice(0, 7);
  $("pdf-mes").addEventListener("change", linkPdf);
  $("f-posto").addEventListener("change", linkPdf);

  // ---------------------------------------------------------------- carregar
  async function carregar() {
    const painel = $("painel");
    painel.setAttribute("aria-busy", "true");
    try {
      const d = await api("/api/dashboard?" + filtros().toString());
      $("f-inicio").value = d.periodo.inicio;
      $("f-fim").value = d.periodo.fim;
      history.replaceState(null, "", "/dashboard?" + filtros().toString());
      linkPdf();
      numeros(d);
      porDia(d);
      estados(d);
      porTurno(d);
      porPosto(d);
    } catch (falha) {
      aviso(falha.message, "erro");
    } finally {
      painel.setAttribute("aria-busy", "false");
    }
  }

  async function carregarPostos() {
    const valor = new URLSearchParams(location.search).get("camera_id") || "";
    try {
      const cameras = await api("/api/cameras");
      $("f-posto").replaceChildren(el("option", { value: "", texto: "Todos" }),
        ...cameras.map((c) => el("option", { value: String(c.id), texto: c.nome_posto + (c.ativa ? "" : " (desativado)") })));
    } catch (_) { /* fica só "Todos" */ }
    $("f-posto").value = valor;
  }

  $("filtros").addEventListener("submit", (evento) => {
    evento.preventDefault();
    if ($("f-inicio").value && $("f-fim").value && $("f-inicio").value > $("f-fim").value) {
      aviso("A data inicial está depois da data final.", "erro");
      return;
    }
    carregar();
  });

  document.querySelectorAll("[data-periodo]").forEach((botao) => botao.addEventListener("click", () => {
    const tipo = botao.dataset.periodo;
    $("f-fim").value = hoje();
    if (tipo === "hoje") $("f-inicio").value = hoje();
    else if (tipo === "mes") $("f-inicio").value = hoje().slice(0, 8) + "01";
    else $("f-inicio").value = hoje(1 - Number(tipo));
    carregar();
  }));

  (async () => {
    const params = new URLSearchParams(location.search);
    $("f-inicio").value = params.get("inicio") || "";
    $("f-fim").value = params.get("fim") || "";
    await carregarPostos();
    carregar();
  })();
})();
