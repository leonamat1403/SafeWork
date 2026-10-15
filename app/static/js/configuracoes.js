/* T06 – Configurações (só ADMIN): postos e câmeras, máscara por posto (RD05), zona de interesse (RD06) e sistema.
   Cada aba salva sozinha; o servidor religa a câmera afetada e registra tudo na auditoria. */
"use strict";

(() => {
  const { api, el, icone, aviso, numero } = EPI;
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const PROCESSOS = { MIG_MAG: "MIG/MAG", TIG: "TIG", ELETRODO: "Eletrodo", CORTE: "Corte", OUTRO: "Outro" };
  const TIPOS = { webcam: "Webcam", rtsp: "Câmera IP", arquivo: "Arquivo de vídeo" };
  let postos = [];

  // ---------------------------------------------------------------- abas (lembradas no endereço: ?aba=)
  const ABAS = { postos: "aba-postos", epis: "aba-mascara", zona: "aba-zona", sistema: "aba-sistema" };
  document.querySelectorAll('[data-bs-toggle="tab"]').forEach((botao) => botao.addEventListener("shown.bs.tab", () => {
    const novos = new URLSearchParams(location.search);
    novos.set("aba", botao.dataset.aba);
    history.replaceState(null, "", "?" + novos.toString());
    if (botao.dataset.aba === "zona") carregarZona();
  }));

  function postoEscolhido(seletor) { return postos.find((p) => p.id === Number($(seletor).value)); }

  function preencherSeletor(id, preferido) {
    const seletor = $(id);
    const atual = seletor.value || preferido;
    seletor.replaceChildren(...postos.map((p) => el("option", { value: String(p.id),
      texto: p.nome_posto + (p.ativa ? "" : " (desativado)") })));
    if (atual && postos.some((p) => String(p.id) === String(atual))) seletor.value = String(atual);
  }

  // ================================================================ Postos e câmeras
  function linhaPosto(p) {
    const editar = el("button", { type: "button", classe: "btn btn-sm btn-outline-secondary" }, icone("bi-pencil me-1"), "Editar");
    editar.addEventListener("click", () => abrirPosto(p));
    const remover = el("button", { type: "button", classe: "btn btn-sm btn-outline-danger" }, icone("bi-trash me-1"), "Remover");
    if (p.ocorrencias > 0) {
      remover.disabled = true;
      remover.title = "Tem ocorrências: desative o posto para manter o histórico.";
    }
    remover.addEventListener("click", () => removerPosto(p));
    const calibrar = p.ativa ? el("a", { classe: "btn btn-sm btn-outline-primary", href: "/calibracao?camera_id=" + p.id },
      icone("bi-bounding-box me-1"), "Calibrar") : null;
    return el("tr", { classe: p.ativa ? "" : "text-secondary" },
      el("td", {}, el("strong", { texto: p.nome_posto })),
      el("td", { texto: PROCESSOS[p.processo_solda] || p.processo_solda }),
      el("td", { texto: TIPOS[p.tipo] || p.tipo }),
      el("td", {}, el("code", { classe: "text-break", texto: p.origem })),
      el("td", {}, icone(p.ativa ? "bi-broadcast me-1" : "bi-pause-circle me-1"), p.ativa ? "Ativo" : "Desativado",
        p.zona ? el("div", { classe: "small text-secondary", texto: "com zona de interesse" }) : null),
      el("td", { classe: "text-end numero", texto: numero(p.ocorrencias) }),
      el("td", { classe: "text-end" }, el("div", { classe: "d-inline-flex flex-wrap gap-2 justify-content-end" },
        editar, calibrar, remover)));
  }

  async function carregarPostos() {
    try {
      postos = await api("/api/config/cameras");
    } catch (falha) { aviso(falha.message, "erro"); return; }
    $("linhas-postos").replaceChildren(...postos.map(linhaPosto));
    preencherSeletor("m-posto", params.get("camera_id"));
    preencherSeletor("z-posto", params.get("camera_id"));
  }

  // ---- modal novo/editar
  const modalPosto = bootstrap.Modal.getOrCreateInstance($("modal-posto"));
  const AJUDA_ORIGEM = {
    webcam: ["0", "Número da webcam neste computador: 0 para a primeira, 1 para a segunda."],
    rtsp: ["rtsp://10.0.3.21:554/stream1", "Endereço RTSP da câmera, SEM usuário e senha (eles ficam no .env)."],
    arquivo: ["testes_campo/videos/teste.mp4", "Caminho de um vídeo na pasta do projeto (o vídeo repete sem parar)."],
  };
  let editando = null;

  const tipoEscolhido = () => document.querySelector('input[name="p-tipo"]:checked').value;
  function ajudaOrigem() {
    const [exemplo, ajuda] = AJUDA_ORIGEM[tipoEscolhido()];
    $("p-origem").placeholder = exemplo;
    $("p-origem-ajuda").textContent = ajuda;
  }
  document.querySelectorAll('input[name="p-tipo"]').forEach((r) => r.addEventListener("change", ajudaOrigem));

  function erroPosto(texto) {
    $("erro-posto").querySelector("span").textContent = texto || "";
    $("erro-posto").hidden = !texto;
  }

  function abrirPosto(p) {
    editando = p;
    erroPosto("");
    $("posto-titulo").textContent = p ? `Editar posto · ${p.nome_posto}` : "Novo posto";
    $("p-nome").value = p ? p.nome_posto : "";
    $("p-processo").value = p ? p.processo_solda : "MIG_MAG";
    $(`p-tipo-${p ? p.tipo : "webcam"}`).checked = true;
    $("p-origem").value = p ? p.origem : "0";
    $("p-ativa").checked = p ? p.ativa : true;
    ajudaOrigem();
    modalPosto.show();
  }
  $("novo-posto").addEventListener("click", () => abrirPosto(null));
  $("modal-posto").addEventListener("shown.bs.modal", () => $("p-nome").focus());

  $("form-posto").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    erroPosto("");
    const corpo = { nome_posto: $("p-nome").value.trim(), processo_solda: $("p-processo").value, tipo: tipoEscolhido(),
      origem: $("p-origem").value.trim(), ativa: $("p-ativa").checked };
    if (corpo.nome_posto.length < 2) { erroPosto("Informe o nome do posto."); $("p-nome").focus(); return; }
    if (!corpo.origem) { erroPosto("Informe o endereço da câmera."); $("p-origem").focus(); return; }
    $("salvar-posto").disabled = true;
    try {
      if (editando) await api(`/api/cameras/${editando.id}`, { method: "PUT", json: corpo });
      else await api("/api/cameras", { method: "POST", json: corpo });
      modalPosto.hide();
      aviso(`Posto ${corpo.nome_posto} salvo.` + (corpo.ativa ? " A câmera liga em alguns segundos." : ""));
      await carregarPostos();
    } catch (falha) {
      erroPosto(falha.message);
    } finally {
      $("salvar-posto").disabled = false;
    }
  });

  async function removerPosto(p) {
    if (!confirm(`Remover o posto ${p.nome_posto}? Esta ação não pode ser desfeita.`)) return;
    try {
      await api(`/api/cameras/${p.id}`, { method: "DELETE" });
      aviso(`Posto ${p.nome_posto} removido.`);
      await carregarPostos();
    } catch (falha) { aviso(falha.message, "erro"); }
  }

  // ================================================================ Máscara por posto
  const formatos = {
    "m-conf": (v) => numero(v, 2), "m-tempo": (v) => numero(v, 1) + " s", "m-fracao": (v) => numero(v * 100) + "%",
    "m-cobertura": (v) => numero(v, 2), "s-brilho": (v) => numero(v), "s-saturada": (v) => numero(v * 100) + "%",
    "s-maos": (v) => numero(v * 100, 1) + "%",
  };
  function mostrarValor(id) { $(id + "-valor").textContent = formatos[id](Number($(id).value)); }
  Object.keys(formatos).forEach((id) => $(id).addEventListener("input", () => mostrarValor(id)));

  async function carregarMascara() {
    const p = postoEscolhido("m-posto");
    if (!p) return;
    $("m-calibrar").href = "/calibracao?camera_id=" + p.id;
    $("m-calibrar").hidden = !p.ativa;
    try {
      const { mascara } = await api(`/api/cameras/${p.id}/epis`);
      $("m-exigido").checked = mascara.exigido;
      $("m-conf").value = mascara.conf_min;
      $("m-tempo").value = mascara.persistencia_s;
      $("m-fracao").value = mascara.fracao_minima;
      $("m-cobertura").value = mascara.cobertura_min;
      $("m-levantada").checked = mascara.levantada_nao_conforme;
      ["m-conf", "m-tempo", "m-fracao", "m-cobertura"].forEach(mostrarValor);
    } catch (falha) { aviso(falha.message, "erro"); }
  }
  $("m-posto").addEventListener("change", carregarMascara);

  $("form-mascara").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const p = postoEscolhido("m-posto");
    if (!p) return;
    try {
      await api(`/api/cameras/${p.id}/epis`, { method: "PUT", json: {
        exigido: $("m-exigido").checked, conf_min: Number($("m-conf").value), persistencia_s: Number($("m-tempo").value),
        fracao_minima: Number($("m-fracao").value), cobertura_min: Number($("m-cobertura").value),
        levantada_nao_conforme: $("m-levantada").checked } });
      aviso(`Configurações do posto ${p.nome_posto} salvas.`);
    } catch (falha) { aviso(falha.message, "erro"); }
  });

  // ================================================================ Zona de interesse (RD06)
  const foto = $("z-foto"), tela = $("z-desenho");
  let pontos = [];

  function desenharZona() {
    const escala = window.devicePixelRatio || 1;
    tela.width = Math.max(1, Math.round(tela.clientWidth * escala));
    tela.height = Math.max(1, Math.round(tela.clientHeight * escala));
    const ctx = tela.getContext("2d");
    ctx.clearRect(0, 0, tela.width, tela.height);
    if (!pontos.length) return;
    const xy = pontos.map(([x, y]) => [x * tela.width, y * tela.height]);
    ctx.beginPath();
    xy.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    if (xy.length >= 3) {
      ctx.closePath();
      ctx.fillStyle = "rgba(13, 110, 253, .18)";
      ctx.fill();
    }
    ctx.lineWidth = 2 * escala;
    ctx.strokeStyle = "#0D6EFD";
    ctx.stroke();
    xy.forEach(([x, y], i) => {
      ctx.beginPath();
      ctx.arc(x, y, (i === 0 ? 7 : 5) * escala, 0, Math.PI * 2);
      ctx.fillStyle = "#FFFFFF";
      ctx.fill();
      ctx.lineWidth = 2 * escala;
      ctx.stroke();
    });
  }

  function situacaoZona() {
    $("z-situacao").textContent = pontos.length === 0 ? "Sem zona: a imagem toda vale."
      : pontos.length < 3 ? `${pontos.length} ponto(s): marque pelo menos 3.` : `Zona com ${pontos.length} pontos.`;
  }

  function carregarZona() {
    const p = postoEscolhido("z-posto");
    if (!p) return;
    pontos = (p.zona || []).map(([x, y]) => [x, y]);
    situacaoZona();
    if (!p.ativa) {
      foto.removeAttribute("src");
      $("z-situacao").textContent = "Posto desativado: ative-o para tirar a foto e desenhar a zona.";
      desenharZona();
      return;
    }
    foto.src = `/api/cameras/${p.id}/snapshot.jpg?t=${Date.now()}`;
  }
  foto.addEventListener("load", desenharZona);
  foto.addEventListener("error", () => {
    if (foto.getAttribute("src")) $("z-situacao").textContent = "A câmera ainda não tem imagem (ligando ou fora do ar). Tente \"Foto nova\" em instantes.";
  });
  new ResizeObserver(desenharZona).observe($("z-quadro"));
  $("z-posto").addEventListener("change", carregarZona);
  $("z-foto-nova").addEventListener("click", carregarZona);

  tela.addEventListener("click", (evento) => {
    if (pontos.length >= 30) { aviso("A zona aceita até 30 pontos.", "erro"); return; }
    const caixa = tela.getBoundingClientRect();
    pontos.push([(evento.clientX - caixa.left) / caixa.width, (evento.clientY - caixa.top) / caixa.height]
      .map((v) => Math.round(Math.min(1, Math.max(0, v)) * 10000) / 10000));
    situacaoZona();
    desenharZona();
  });
  $("z-desfazer").addEventListener("click", () => { pontos.pop(); situacaoZona(); desenharZona(); });
  $("z-limpar").addEventListener("click", () => { pontos = []; situacaoZona(); desenharZona(); });

  $("z-salvar").addEventListener("click", async () => {
    const p = postoEscolhido("z-posto");
    if (!p) return;
    if (pontos.length > 0 && pontos.length < 3) { aviso("Marque pelo menos 3 pontos, ou limpe para usar a imagem toda.", "erro"); return; }
    try {
      const resposta = await api(`/api/cameras/${p.id}/roi`, { method: "PUT", json: { pontos: pontos.length ? pontos : null } });
      p.zona = resposta.zona;
      aviso(resposta.zona ? `Zona do posto ${p.nome_posto} salva.` : `Posto ${p.nome_posto} sem zona: a imagem toda vale.`);
      $("linhas-postos").replaceChildren(...postos.map(linhaPosto));
    } catch (falha) { aviso(falha.message, "erro"); }
  });

  // ================================================================ Sistema
  let padrao = {};

  function linhaTurno(nome = "", inicio = "06:00", fim = "14:00") {
    const remover = el("button", { type: "button", classe: "btn btn-sm btn-outline-secondary", "aria-label": "Remover turno" },
      icone("bi-x-lg"));
    const linha = el("div", { classe: "turno-linha" },
      el("label", {}, el("span", { classe: "form-label d-block small", texto: "Turno" }),
        el("input", { type: "text", classe: "form-control form-control-sm", value: nome, maxlength: "10", "data-campo": "nome" })),
      el("label", {}, el("span", { classe: "form-label d-block small", texto: "Início" }),
        el("input", { type: "time", classe: "form-control form-control-sm", value: inicio, "data-campo": "inicio" })),
      el("label", {}, el("span", { classe: "form-label d-block small", texto: "Fim" }),
        el("input", { type: "time", classe: "form-control form-control-sm", value: fim, "data-campo": "fim" })),
      remover);
    remover.addEventListener("click", () => linha.remove());
    return linha;
  }
  $("s-mais-turno").addEventListener("click", () => {
    if ($("s-turnos").children.length >= 6) { aviso("Até 6 turnos.", "erro"); return; }
    $("s-turnos").append(linhaTurno(String($("s-turnos").children.length + 1)));
  });

  function textoPadrao(chave, valor) {
    const campo = document.querySelector(`[data-padrao="${chave}"]`);
    if (campo) campo.textContent = `No config.yaml: ${valor}`;
  }

  function mostrarDisco(d) {
    const usado = d.usado_bytes, total = d.total_bytes, livre = d.livre_bytes;
    const gb = (b) => numero(b / 1024 ** 3, 1) + " GB";
    const medidor = $("s-disco");
    medidor.querySelector(".medidor-valor").style.width = Math.min(100, ((total - livre) / total) * 100) + "%";
    medidor.classList.toggle("acima", livre < d.minimo_mb * 1024 ** 2 * 2);
    $("s-disco-texto").textContent = `A pasta de dados usa ${gb(usado)}. Livre no disco: ${gb(livre)} de ${gb(total)}. `
      + `Abaixo de ${numero(d.minimo_mb)} MB livres, as ocorrências passam a ser registradas sem imagem.`;
  }

  async function carregarSistema() {
    try {
      const d = await api("/api/config/sistema");
      const v = d.valores;
      padrao = d.padrao;
      $("s-cooldown").value = v.cooldown_s;
      $("s-retencao").value = v.retencao_dias;
      if (![...$("s-imgsz").options].some((o) => Number(o.value) === v.imgsz)) {
        $("s-imgsz").append(el("option", { value: String(v.imgsz), texto: String(v.imgsz) }));
      }
      $("s-imgsz").value = String(v.imgsz);
      $("s-brilho").value = v.limiar_brilho;
      $("s-saturada").value = v.fracao_max_saturada;
      $("s-maos").value = v.fracao_min_maos;
      ["s-brilho", "s-saturada", "s-maos"].forEach(mostrarValor);
      $("s-detectar").checked = v.detectar_solda_ativa;
      $("s-somente-arco").checked = v.exigir_mascara_somente_com_arco;
      $("s-turnos").replaceChildren(...Object.entries(v.turnos).map(([nome, faixa]) => linhaTurno(nome, ...faixa.split("-"))));
      textoPadrao("cooldown_s", `${numero(padrao.cooldown_s)} s`);
      textoPadrao("retencao_dias", `${numero(padrao.retencao_dias)} dias`);
      textoPadrao("imgsz", String(padrao.imgsz));
      textoPadrao("limiar_brilho", numero(padrao.limiar_brilho));
      textoPadrao("fracao_max_saturada", numero(padrao.fracao_max_saturada * 100) + "%");
      textoPadrao("fracao_min_maos", numero(padrao.fracao_min_maos * 100, 1) + "%");
      const t = d.telegram;
      $("s-telegram").textContent = t.configurado
        ? `Configurado no .env (token ${t.token}, conversa ${t.chat_id}).`
        : "Não configurado: coloque TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no arquivo .env e reinicie o sistema.";
      $("s-telegram-ativo").checked = t.configurado && v.telegram_ativo;
      $("s-telegram-ativo").disabled = !t.configurado;
      mostrarDisco(d.disco);
    } catch (falha) { aviso(falha.message, "erro"); }
  }

  $("form-sistema").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const turnos = {};
    for (const linha of $("s-turnos").children) {
      const nome = linha.querySelector('[data-campo="nome"]').value.trim();
      if (!nome) { aviso("Dê um nome para cada turno.", "erro"); return; }
      turnos[nome] = `${linha.querySelector('[data-campo="inicio"]').value}-${linha.querySelector('[data-campo="fim"]').value}`;
    }
    const corpo = {
      cooldown_s: Number($("s-cooldown").value), retencao_dias: Number($("s-retencao").value),
      imgsz: Number($("s-imgsz").value), limiar_brilho: Number($("s-brilho").value),
      fracao_max_saturada: Number($("s-saturada").value), fracao_min_maos: Number($("s-maos").value),
      detectar_solda_ativa: $("s-detectar").checked, exigir_mascara_somente_com_arco: $("s-somente-arco").checked,
      turnos,
    };
    if (!$("s-telegram-ativo").disabled) corpo.telegram_ativo = $("s-telegram-ativo").checked;
    try {
      const resposta = await api("/api/config/sistema", { method: "PUT", json: corpo });
      aviso(resposta.alterados.length ? "Configurações do sistema salvas. As câmeras foram religadas."
        : "Nada mudou.");
    } catch (falha) { aviso(falha.message, "erro"); }
  });

  // ---------------------------------------------------------------- início
  (async () => {
    await carregarPostos();
    await Promise.all([carregarMascara(), carregarSistema()]);
    const aba = ABAS[params.get("aba")];
    if (aba) bootstrap.Tab.getOrCreateInstance($(aba)).show();
  })();
})();
