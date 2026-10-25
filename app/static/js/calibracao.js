/* T07 – Calibração (RD02): vídeo com o desenho técnico e os números de cada pessoa, ao lado dos limites do posto. */
"use strict";

(() => {
  const { api, el, icone, selo, numero } = EPI;
  const cameraId = document.getElementById("conteudo").dataset.cameraId;
  if (!cameraId) return;
  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------- vídeo (reconecta sozinho; fecha com a aba escondida)
  const video = $("video");
  let ligado = true, religar = null;
  /** (Re)abre o stream MJPEG de calibração; ?t= com a hora evita reaproveitar conexão antiga. */
  function conectar() {
    clearTimeout(religar);
    video.src = `/api/cameras/${cameraId}/calibracao.mjpg?t=${Date.now()}`;
  }
  video.addEventListener("error", () => { if (ligado) religar = setTimeout(conectar, 3000); });
  document.addEventListener("visibilitychange", () => {
    ligado = !document.hidden;
    if (ligado) conectar();
    else { clearTimeout(religar); video.removeAttribute("src"); }
  });
  conectar();

  // ---------------------------------------------------------------- formatação
  const pct = (fracao, casas = 0) => numero(fracao * 100, casas) + "%";
  const dec = (valor) => numero(valor, 2);

  /** Valor e limite lado a lado, com um sinal neutro de "passou"/"não passou" (as cores de estado são dos EPIs). */
  function comparado(texto, passou, limite) {
    return [el("span", { classe: "numero", texto }),
      passou === null ? null : icone(passou ? "bi-check2 ms-1" : "bi-x ms-1"),
      limite ? el("span", { classe: "limite", texto: ` ${limite}` }) : null];
  }

  function linha(rotulo, ...conteudo) {
    return [el("dt", { texto: rotulo }), el("dd", {}, ...conteudo)];
  }

  // ---------------------------------------------------------------- medidor do arco (RF14)
  /** Barra do arco: largura = fração de pixels estourados; marca vertical = limite do posto; fica "acima" se passar do limite. A escala é o dobro do limite. */
  function medidor(caixa, fracao, limite) {
    const escala = Math.max(limite * 2, fracao, 0.01);
    caixa.querySelector(".medidor-valor").style.width = Math.min(100, (fracao / escala) * 100) + "%";
    caixa.querySelector(".medidor-limite").style.left = (limite / escala) * 100 + "%";
    caixa.classList.toggle("acima", fracao > limite);
  }

  // ---------------------------------------------------------------- uma pessoa
  /** Cartão com os números que o sistema mediu de uma pessoa, cada um ao lado do limite configurado do posto. */
  function cartaoPessoa(p, limites) {
    const estado = p.estado || "INDETERMINADO";
    const dados = el("dl", {},
      ...linha("Altura", el("span", { classe: "numero", texto: `${numero(p.altura_px)} px` })),
      ...linha("Cabeça", p.cabeca_visivel ? (p.sem_pose ? "estimada pela caixa (sem pose)" : "encontrada pelos pontos")
        : "não visível"),
      ...linha("Orientação", { frente: "de frente", costas: "de costas", indefinida: "indefinida" }[p.orientacao]
        || p.orientacao),
      ...linha("Cobertura da máscara", ...(p.cobertura === null ? ["sem máscara associada"]
        : comparado(dec(p.cobertura), p.cobertura >= limites.cobertura_min, `(mín. ${dec(limites.cobertura_min)})`))),
      ...linha("Confiança da máscara", ...(p.conf_mascara === null ? ["—"]
        : comparado(dec(p.conf_mascara), p.conf_mascara >= limites.conf_mascara, `(mín. ${dec(limites.conf_mascara)})`))),
      ...linha("Rosto descoberto", ...(p.rosto_visivel
        ? comparado(p.conf_rosto === null ? "sim" : `sim, ${dec(p.conf_rosto)}`, null, `(mín. ${dec(limites.conf_rosto)})`)
        : ["não"])),
      ...linha("Máscara levantada", p.mascara_levantada ? "sim" : "não"),
      ...linha("Brilho perto das mãos", ...(p.brilho_maos === null ? ["punhos não visíveis"]
        : comparado(pct(p.brilho_maos, 1), null, `(arco a partir de ${pct(limites.fracao_min_maos, 1)})`))),
      ...linha("Arco aceso", p.arco_ativo ? EPI.marcaArco() : "não"));
    return el("article", { classe: "calibra-pessoa" },
      el("div", { classe: "pessoa-cabecalho" },
        el("span", { classe: "pessoa-id", texto: p.track_id == null ? "#?" : "#" + p.track_id }), selo(estado)),
      p.motivo ? el("p", { classe: "pessoa-motivo mb-0 mt-1", texto: p.motivo }) : null,
      dados);
  }

  // ---------------------------------------------------------------- ciclo de 1 s
  let chave = "";
  /** Mostra os dados de /api/calibracao; só redesenha os cartões se as pessoas mudaram. */
  function mostrar(d) {
    EPI.mostrarStatusCamera(d);
    if (d.pausada || !d.online || d.aguardando) {
      const texto = d.pausada ? "Posto pausado." : (!d.online ? "Câmera offline." : "Preparando a calibração…");
      $("texto-quadro").textContent = texto;
      $("valores").replaceChildren(el("p", { classe: "text-secondary mb-0", texto }));
      chave = "";
      return;
    }
    const lim = d.limites;
    medidor($("medidor-quadro"), d.fracao_saturada, lim.fracao_max_saturada);
    $("texto-quadro").textContent = `${pct(d.fracao_saturada, 1)} dos pixels acima do brilho ${lim.limiar_brilho} `
      + `(limite ${pct(lim.fracao_max_saturada)}) · ` + (d.quadro_valido ? "quadro válido" : "quadro ignorado: arco estourou a imagem")
      + ` · ${numero(d.fps, 1)} FPS`;
    const nova = JSON.stringify(d.pessoas);
    if (nova === chave) return;
    chave = nova;
    $("valores").replaceChildren(...(d.pessoas.length ? d.pessoas.map((p) => cartaoPessoa(p, lim))
      : [el("p", { classe: "text-secondary mb-0", texto: "Ninguém no quadro agora." })]));
  }

  /** Ciclo de atualização: 1 s com a aba visível, 5 s escondida. */
  async function atualizar() {
    try {
      mostrar(await api("/api/calibracao/" + encodeURIComponent(cameraId)));
    } catch (falha) {
      $("texto-quadro").textContent = falha.message;
    } finally {
      setTimeout(atualizar, document.hidden ? 5000 : 1000);
    }
  }
  atualizar();
})();
