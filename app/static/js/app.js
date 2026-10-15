/* Funções comuns de todas as telas (Verificador de EPIs de Solda).
   Sem bibliotecas além do Bootstrap. Os dados da API entram na página sempre como TEXTO (textContent), nunca como
   HTML, para que nenhum conteúdo vindo de fora vire script. */
"use strict";

window.EPI = (() => {
  const meta = document.querySelector('meta[name="csrf-token"]');
  const csrf = () => (meta ? meta.content : "");

  class ErroApi extends Error {
    constructor(mensagem, status) { super(mensagem); this.status = status; }
  }

  /** Chama a API. Rotas que alteram algo levam o token CSRF; sessão expirada leva de volta ao login. */
  async function api(url, opcoes = {}) {
    const metodo = (opcoes.method || "GET").toUpperCase();
    const cabecalhos = new Headers(opcoes.headers || {});
    let corpo = opcoes.body;
    if (metodo !== "GET") cabecalhos.set("X-CSRF-Token", csrf());
    if (opcoes.json !== undefined) {
      cabecalhos.set("Content-Type", "application/json");
      corpo = JSON.stringify(opcoes.json);
    }
    const resposta = await fetch(url, { method: metodo, headers: cabecalhos, body: corpo, credentials: "same-origin" });
    if (resposta.status === 401 && !opcoes.semRedirecionar) {
      location.href = "/login?expirou=1&proximo=" + encodeURIComponent(location.pathname + location.search);
      throw new ErroApi("Sessão encerrada.", 401);
    }
    let dados = null;
    try { dados = await resposta.json(); } catch (_) { dados = null; }
    if (!resposta.ok) {
      const detalhe = dados && dados.detail;
      throw new ErroApi(typeof detalhe === "string" ? detalhe : `Erro ${resposta.status} no sistema.`, resposta.status);
    }
    return dados;
  }

  /** Cria um elemento: el("a", {href: "/x", classe: "btn", texto: "Ir"}, filho1, "texto"...). */
  function el(tag, atributos = {}, ...filhos) {
    const elemento = document.createElement(tag);
    for (const [chave, valor] of Object.entries(atributos)) {
      if (valor === null || valor === undefined || valor === false) continue;
      if (chave === "classe") elemento.className = valor;
      else if (chave === "texto") elemento.textContent = valor;
      else if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
      else elemento.setAttribute(chave, valor === true ? "" : valor);
    }
    for (const filho of filhos.flat()) {
      if (filho === null || filho === undefined || filho === false) continue;
      elemento.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
    }
    return elemento;
  }

  const icone = (nome) => el("i", { classe: "bi " + nome, "aria-hidden": "true" });

  function iconeMascara(classe = "icone-epi") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", classe);
    svg.setAttribute("aria-hidden", "true");
    const uso = document.createElementNS("http://www.w3.org/2000/svg", "use");
    uso.setAttribute("href", "#icone-mascara");
    svg.append(uso);
    return svg;
  }

  // Estado = cor + forma + texto: círculo (conforme), octógono (não conforme, placa "PARE"), losango (atenção)
  const ESTADOS = {
    CONFORME: { classe: "estado-c", icone: "bi-check-circle-fill", texto: "Conforme" },
    NAO_CONFORME: { classe: "estado-n", icone: "bi-x-octagon-fill", texto: "Não conforme" },
    INDETERMINADO: { classe: "estado-i", icone: "bi-question-diamond-fill", texto: "Indeterminado" },
  };
  const ESTADO_DA_COR = { verde: "CONFORME", vermelho: "NAO_CONFORME", amarelo: "INDETERMINADO" };

  function selo(estado, { claro = false, texto } = {}) {
    const info = ESTADOS[estado] || ESTADOS.INDETERMINADO;
    return el("span", { classe: `estado ${info.classe}${claro ? " estado-claro" : ""}` }, icone(info.icone), texto || info.texto);
  }

  // Validação de uma ocorrência: estilos neutros (as cores de estado ficam só para os EPIs)
  const VALIDACOES = {
    PENDENTE: { classe: "validacao-pendente", icone: "bi-hourglass-split", texto: "Pendente" },
    CONFIRMADA: { classe: "validacao-confirmada", icone: "bi-check2", texto: "Confirmada" },
    FALSO_POSITIVO: { classe: "validacao-falso", icone: "bi-x-lg", texto: "Falso positivo" },
  };
  function seloValidacao(validacao) {
    const info = VALIDACOES[validacao] || VALIDACOES.PENDENTE;
    return el("span", { classe: "validacao " + info.classe }, icone(info.icone), info.texto);
  }

  // O sistema verifica só a máscara de solda (decisão de 15/10/2026: os outros EPIs foram descartados)
  const NOMES_EPI = { mascara: "Máscara de solda" };
  const nomeEpi = (epi) => NOMES_EPI[epi] || epi;
  const iconeEpi = (epi) => (epi === "mascara" ? iconeMascara() : icone("bi-shield"));

  /** "Sem máscara", "Máscara levantada"... */
  function faltaTexto(epis, levantada = false) {
    const partes = (epis || []).map((epi) => (epi === "mascara" ? (levantada ? "Máscara levantada" : "Sem máscara")
      : "Sem " + nomeEpi(epi).toLowerCase()));
    return partes.join(" · ") || "Falta de EPI";
  }

  /** RD03: a pessoa estava soldando (arco aceso perto das mãos) – prioridade alta. */
  const marcaArco = () => el("span", { classe: "marca-arco", title: "Arco aceso perto das mãos: a pessoa estava soldando" },
    icone("bi-lightning-charge-fill"), "Arco aceso");

  const numero = (n, casas = 0) => Number(n).toLocaleString("pt-BR",
    { minimumFractionDigits: casas, maximumFractionDigits: casas });
  const pct = (fracao) => numero(fracao * 100) + "%";

  /** Aviso rápido no canto da tela (lido pelos leitores de tela). */
  function aviso(texto, tipo = "sucesso") {
    const caixa = document.getElementById("avisos");
    if (!caixa || !window.bootstrap) return;
    const erro = tipo === "erro";
    const toast = el("div", { classe: `toast align-items-center aviso-${tipo}`, role: erro ? "alert" : "status", "aria-atomic": "true" },
      el("div", { classe: "d-flex" },
        el("div", { classe: "toast-body" }, icone(erro ? "bi-x-octagon-fill text-danger me-2" : "bi-check-circle-fill text-success me-2"), texto),
        el("button", { type: "button", classe: "btn-close me-2 m-auto", "data-bs-dismiss": "toast", "aria-label": "Fechar" })));
    caixa.append(toast);
    toast.addEventListener("hidden.bs.toast", () => toast.remove());
    new bootstrap.Toast(toast, { delay: erro ? 8000 : 4000 }).show();
  }

  // ---------------------------------------------------------------- topo: posto e status da câmera
  const seletor = document.getElementById("seletor-posto");
  const statusCamera = document.getElementById("status-camera");
  const naTelaAoVivo = location.pathname === "/ao-vivo";

  function postoSelecionado() { return seletor ? Number(seletor.value) : null; }

  function mostrarStatusCamera(info) {
    if (!statusCamera || !info) return;
    let classe = "estado-n", nomeIcone = "bi-x-octagon-fill", texto = "Offline";
    if (info.pausada) { classe = "estado-off"; nomeIcone = "bi-pause-fill"; texto = "Pausada"; }
    else if (info.online) { classe = "estado-c"; nomeIcone = "bi-broadcast"; texto = `Online · ${numero(info.fps, 1)} FPS`; }
    statusCamera.className = "estado " + classe;
    statusCamera.replaceChildren(icone(nomeIcone), el("span", { texto }));
  }

  async function atualizarTopo() {
    try {
      const cameras = await api("/api/cameras");
      mostrarStatusCamera(cameras.find((c) => c.id === postoSelecionado()));
    } catch (_) { /* a próxima tentativa resolve */ }
  }

  function guardarPosto() { try { localStorage.setItem("postoSelecionado", seletor.value); } catch (_) { /* sem armazenamento */ } }

  if (seletor) {
    if (!naTelaAoVivo) {
      try {
        const salvo = localStorage.getItem("postoSelecionado");
        if (salvo && [...seletor.options].some((o) => o.value === salvo)) seletor.value = salvo;
      } catch (_) { /* sem armazenamento */ }
      atualizarTopo();
      setInterval(atualizarTopo, 5000);
    } else {
      guardarPosto();
    }
    seletor.addEventListener("change", () => {
      guardarPosto();
      if (naTelaAoVivo) location.href = "/ao-vivo?camera_id=" + encodeURIComponent(seletor.value);
      else atualizarTopo();
    });
  }

  // ---------------------------------------------------------------- barra lateral: ocorrências pendentes
  const contador = document.getElementById("contador-pendentes");
  async function atualizarPendentes() {
    if (!contador) return;
    try {
      const resumo = await api("/api/ocorrencias/resumo");
      contador.firstChild.textContent = String(resumo.pendentes);
      contador.classList.toggle("zero", resumo.pendentes === 0);
    } catch (_) { /* a próxima tentativa resolve */ }
  }
  if (contador) setInterval(atualizarPendentes, 30000);

  // ---------------------------------------------------------------- sair
  document.querySelectorAll('[data-acao="sair"]').forEach((botao) => botao.addEventListener("click", async () => {
    try { await api("/logout", { method: "POST" }); } catch (_) { /* sai mesmo assim */ }
    location.href = "/login";
  }));

  const movimentoReduzido = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return { api, ErroApi, el, icone, iconeMascara, iconeEpi, nomeEpi, faltaTexto, selo, seloValidacao, marcaArco, ESTADOS,
    ESTADO_DA_COR, numero, pct, aviso, mostrarStatusCamera, atualizarPendentes, postoSelecionado, movimentoReduzido };
})();
