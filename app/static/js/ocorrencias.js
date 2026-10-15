/* T04 – Ocorrências: filtros (guardados no endereço da página), lista, resumo do período, modal com a imagem
   borrada, validação (Confirmada / Falso positivo) e exclusão pelo administrador. */
"use strict";

(() => {
  const { api, el, icone, selo, seloValidacao, nomeEpi, faltaTexto, numero, aviso } = EPI;
  const $ = (id) => document.getElementById(id);
  const admin = $("conteudo").dataset.admin === "1";
  const form = $("filtros");
  const CAMPOS = { inicio: "f-inicio", fim: "f-fim", camera_id: "f-posto", epi: "f-epi", turno: "f-turno", validacao: "f-validacao" };
  const ORIGENS = { ao_vivo: "Câmera ao vivo", upload: "Arquivo enviado" };

  let itens = [], pagina = 1, paginas = 1, atual = -1, uuidAberto = null;

  // ---------------------------------------------------------------- datas (dia local, AAAA-MM-DD)
  function dia(deslocamento = 0) {
    const d = new Date();
    d.setDate(d.getDate() + deslocamento);
    return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
  }

  // ---------------------------------------------------------------- filtros <-> endereço da página
  function lerEndereco() {
    const params = new URLSearchParams(location.search);
    const semPeriodo = !params.has("inicio") && !params.has("fim");
    for (const [nome, id] of Object.entries(CAMPOS)) $(id).value = params.get(nome) || "";
    if (semPeriodo) { $("f-inicio").value = dia(-6); $("f-fim").value = dia(0); }   // padrão: últimos 7 dias
    pagina = Math.max(1, Number(params.get("pagina")) || 1);
    return params.get("abrir");
  }

  function paramsDosFiltros() {
    const params = new URLSearchParams();
    for (const [nome, id] of Object.entries(CAMPOS)) {
      const valor = $(id).value;
      if (valor || nome === "inicio" || nome === "fim") params.set(nome, valor);   // período vazio = sem limite
    }
    if (pagina > 1) params.set("pagina", String(pagina));
    return params;
  }

  function gravarEndereco(abrir = uuidAberto) {
    const params = paramsDosFiltros();
    if (abrir) params.set("abrir", abrir);
    const novo = location.pathname + "?" + params.toString();
    if (novo !== location.pathname + location.search) history.replaceState(null, "", novo);
  }

  // ---------------------------------------------------------------- postos (inclui os desativados: o histórico fica)
  async function carregarPostos() {
    const valor = new URLSearchParams(location.search).get("camera_id") || "";
    try {
      const cameras = await api("/api/cameras");
      $("f-posto").replaceChildren(el("option", { value: "", texto: "Todos" }),
        ...cameras.map((c) => el("option", { value: String(c.id), texto: c.nome_posto + (c.ativa ? "" : " (desativado)") })));
      $("f-posto").value = valor;
    } catch (_) { /* fica só "Todos" */ }
  }

  // ---------------------------------------------------------------- lista
  function miniatura(oc) {
    if (!oc.thumb_url) return el("span", { classe: "miniatura d-inline-flex align-items-center justify-content-center",
      title: "Sem imagem" }, icone("bi-image text-secondary"));
    return el("img", { classe: "miniatura", src: oc.thumb_url, alt: "", loading: "lazy" });
  }

  const textoFalta = (oc) => faltaTexto(oc.epis_faltantes, oc.mascara_levantada);
  const textoIndeterminados = (oc) => (oc.epis_indeterminados || []).map(nomeEpi).join(", ") || "—";
  function textoConfianca(oc) {
    const valores = Object.values(oc.confianca_media || {}).filter((v) => typeof v === "number");
    return valores.length ? numero(Math.max(...valores) * 100) + "%" : "—";
  }

  function linha(oc, indice) {
    const abrirLink = el("a", { href: "?abrir=" + encodeURIComponent(oc.uuid), classe: "numero", texto: oc.data_hora_local });
    abrirLink.addEventListener("click", (evento) => { evento.preventDefault(); abrir(indice); });
    const tr = el("tr", { classe: "clicavel" },
      el("td", {}, miniatura(oc)),
      el("td", { classe: "data-hora" }, abrirLink),
      el("td", { texto: oc.posto }),
      el("td", {}, selo("NAO_CONFORME", { claro: true, texto: textoFalta(oc) }), oc.arco_ativo ? el("div", {}, EPI.marcaArco()) : null),
      el("td", { texto: textoIndeterminados(oc) }),
      el("td", { texto: oc.mascara_levantada ? "Sim" : "Não" }),
      el("td", { classe: "numero", texto: textoConfianca(oc) }),
      el("td", {}, seloValidacao(oc.validacao)));
    tr.addEventListener("click", (evento) => { if (evento.target.closest("a") === null) abrir(indice); });
    return tr;
  }

  function cartao(oc, indice) {
    const botao = el("button", { type: "button", classe: "cartao-oc" },
      miniatura(oc),
      el("span", { classe: "d-block" },
        el("span", { classe: "d-block numero", texto: oc.data_hora_local }),
        el("span", { classe: "d-block small text-secondary", texto: oc.posto }),
        selo("NAO_CONFORME", { claro: true, texto: textoFalta(oc) }),
        oc.arco_ativo ? el("span", { classe: "d-block" }, EPI.marcaArco()) : null,
        el("span", { classe: "d-block mt-1" }, seloValidacao(oc.validacao))));
    botao.addEventListener("click", () => abrir(indice));
    return el("li", {}, botao);
  }

  function mostrarResumo(resumo) {
    const r = $("resumo");
    const forte = (n) => el("strong", { texto: numero(n) });
    const partes = [
      "No período: ", forte(resumo.total), resumo.total === 1 ? " ocorrência · " : " ocorrências · ",
      forte(resumo.pendentes), resumo.pendentes === 1 ? " pendente · " : " pendentes · ",
      forte(resumo.confirmadas), resumo.confirmadas === 1 ? " confirmada · " : " confirmadas · ",
      forte(resumo.falsos_positivos), resumo.falsos_positivos === 1 ? " falso positivo" : " falsos positivos"];
    const validadas = resumo.confirmadas + resumo.falsos_positivos;
    if (validadas) partes.push(" · acerto do sistema nas validadas: ", el("strong", {
      texto: numero((resumo.confirmadas / validadas) * 100) + "%" }));
    r.replaceChildren(...partes);
  }

  async function carregar({ manterModal = false } = {}) {
    const params = paramsDosFiltros();
    try {
      const dados = await api("/api/ocorrencias?" + params.toString());
      if (dados.paginas < pagina && pagina > 1) {   // a página sumiu (ex.: depois de excluir)
        pagina = dados.paginas;
        return carregar({ manterModal });
      }
      itens = dados.itens;
      paginas = dados.paginas;
      mostrarResumo(dados.resumo);
      $("linhas").replaceChildren(...itens.map(linha));
      $("cartoes").replaceChildren(...itens.map(cartao));
      $("vazio").hidden = itens.length > 0;
      $("paginacao").hidden = paginas <= 1;
      $("pagina-atual").textContent = `Página ${pagina} de ${paginas}`;
      $("anterior").disabled = pagina <= 1;
      $("proxima").disabled = pagina >= paginas;
      if (manterModal && uuidAberto) atual = itens.findIndex((oc) => oc.uuid === uuidAberto);
      gravarEndereco();
    } catch (falha) {
      aviso(falha.message, "erro");
    }
  }

  form.addEventListener("submit", (evento) => {
    evento.preventDefault();
    if ($("f-inicio").value && $("f-fim").value && $("f-inicio").value > $("f-fim").value) {
      aviso("A data inicial está depois da data final.", "erro");
      $("f-inicio").focus();
      return;
    }
    pagina = 1;
    carregar();
  });
  $("limpar").addEventListener("click", () => {
    for (const id of Object.values(CAMPOS)) $(id).value = "";
    $("f-inicio").value = dia(-6);
    $("f-fim").value = dia(0);
    pagina = 1;
    carregar();
  });
  $("anterior").addEventListener("click", () => { if (pagina > 1) { pagina -= 1; carregar(); } });
  $("proxima").addEventListener("click", () => { if (pagina < paginas) { pagina += 1; carregar(); } });

  // ---------------------------------------------------------------- modal
  const modalEl = $("modal");
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  let focoAnterior = null;

  function par(rotulo, ...conteudo) {
    return [el("dt", { classe: "col-5 text-secondary fw-normal", texto: rotulo }), el("dd", { classe: "col-7" }, ...conteudo)];
  }

  function preencher(oc) {
    $("modal-titulo").textContent = `Ocorrência · ${oc.data_hora_local}`;
    const imagem = $("modal-imagem");
    imagem.hidden = !oc.imagem_url;
    $("modal-sem-imagem").hidden = !!oc.imagem_url;
    if (oc.imagem_url) {
      imagem.src = oc.imagem_url;
      imagem.alt = `Imagem borrada da ocorrência: ${textoFalta(oc).toLowerCase()} no posto ${oc.posto}`;
    } else {
      imagem.removeAttribute("src");
    }
    const motivos = Object.entries(oc.situacao || {}).map(([epi, motivo]) => `${nomeEpi(epi)}: ${motivo}`).join("; ");
    const fracoes = Object.entries(oc.fracao_nao_conforme || {})
      .map(([epi, f]) => `${nomeEpi(epi)} ${numero(f * 100)}%`).join("; ");
    $("modal-dados").replaceChildren(
      ...par("Falta", selo("NAO_CONFORME", { texto: textoFalta(oc) })),
      ...par("Posto", oc.posto),
      ...par("Data e hora", el("span", { classe: "numero", texto: oc.data_hora_local })),
      ...par("Turno", oc.turno || "—"),
      ...par("Origem", ORIGENS[oc.origem] || oc.origem),
      ...par("Pessoa no vídeo", el("span", { classe: "numero", texto: "#" + oc.track_id })),
      ...(motivos ? par("Motivo", motivos) : []),
      ...par("Em falta na janela de 4 s", fracoes || "—"),
      ...par("Arco aceso", oc.arco_ativo ? EPI.marcaArco() : "Não"),
      ...par("Indeterminados", textoIndeterminados(oc)),
      ...par("Confiança", el("span", { classe: "numero", texto: textoConfianca(oc) })),
      ...par("Validação", seloValidacao(oc.validacao),
        oc.validado_por ? el("div", { classe: "small text-secondary mt-1", texto: `por ${oc.validado_por} em ${oc.validado_em}` }) : null),
      ...par("Código", el("span", { classe: "numero small text-break", texto: oc.uuid })));
    modalEl.querySelectorAll("[data-validar]").forEach((botao) => {
      const ativa = botao.dataset.validar === oc.validacao;
      botao.disabled = ativa;
      botao.setAttribute("aria-pressed", String(ativa));
      botao.hidden = botao.dataset.validar === "PENDENTE" && oc.validacao === "PENDENTE";
    });
  }

  async function abrirUuid(uuid) {
    uuidAberto = uuid;
    atual = itens.findIndex((oc) => oc.uuid === uuid);
    try {
      preencher(await api("/api/ocorrencias/" + encodeURIComponent(uuid)));
      gravarEndereco();
      if (!modalEl.classList.contains("show")) {
        focoAnterior = document.activeElement;
        modal.show();
      }
    } catch (falha) {
      uuidAberto = null;
      aviso(falha.message, "erro");
    }
  }

  function abrir(indice) {
    if (indice >= 0 && indice < itens.length) abrirUuid(itens[indice].uuid);
  }

  modalEl.addEventListener("hidden.bs.modal", () => {
    uuidAberto = null;
    atual = -1;
    gravarEndereco(null);
    if (focoAnterior && document.contains(focoAnterior)) focoAnterior.focus();
  });

  modalEl.addEventListener("keydown", (evento) => {
    if (evento.target.closest("input, select, textarea")) return;
    if (evento.key === "ArrowRight" && atual >= 0 && atual < itens.length - 1) { evento.preventDefault(); abrir(atual + 1); }
    if (evento.key === "ArrowLeft" && atual > 0) { evento.preventDefault(); abrir(atual - 1); }
  });

  modalEl.querySelectorAll("[data-validar]").forEach((botao) => botao.addEventListener("click", async () => {
    if (!uuidAberto) return;
    const valor = botao.dataset.validar;
    try {
      const oc = await api(`/api/ocorrencias/${encodeURIComponent(uuidAberto)}/validacao`,
        { method: "POST", json: { validacao: valor } });
      preencher(oc);
      aviso({ CONFIRMADA: "Falta confirmada.", FALSO_POSITIVO: "Marcada como falso positivo.",
        PENDENTE: "Voltou para pendente." }[valor]);
      await carregar({ manterModal: true });
      EPI.atualizarPendentes();
    } catch (falha) {
      aviso(falha.message, "erro");
    }
  }));

  const botaoExcluir = $("botao-excluir");
  if (botaoExcluir && admin) botaoExcluir.addEventListener("click", async () => {
    if (!uuidAberto) return;
    if (!confirm("Excluir esta ocorrência? A imagem e o registro são apagados de vez (a exclusão fica na auditoria).")) return;
    try {
      await api("/api/ocorrencias/" + encodeURIComponent(uuidAberto), { method: "DELETE" });
      modal.hide();
      aviso("Ocorrência excluída.");
      await carregar();
      EPI.atualizarPendentes();
    } catch (falha) {
      aviso(falha.message, "erro");
    }
  });

  // ---------------------------------------------------------------- início
  (async () => {
    const abrirAoCarregar = lerEndereco();
    await carregarPostos();
    await carregar();
    if (abrirAoCarregar) abrirUuid(abrirAoCarregar);
  })();
})();
