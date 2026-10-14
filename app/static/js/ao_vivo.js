/* T02 – Ao vivo: vídeo MJPEG, painel "Pessoas agora" (a cada 1 s), últimas ocorrências e o cordão do turno. */
"use strict";

(() => {
  const { api, el, icone, iconeEpi, nomeEpi, faltaTexto, selo, ESTADO_DA_COR, numero, aviso } = EPI;
  const principal = document.getElementById("conteudo");
  const cameraId = principal.dataset.cameraId;
  if (!cameraId) return;
  const $ = (id) => document.getElementById(id);

  // ---------------------------------------------------------------- vídeo (reconecta sozinho se cair)
  const video = $("video");
  let videoLigado = true, religar = null;
  function conectarVideo() {
    clearTimeout(religar);
    video.src = `/api/cameras/${cameraId}/stream.mjpg?t=${Date.now()}`;
  }
  video.addEventListener("error", () => {
    if (videoLigado) religar = setTimeout(conectarVideo, 3000);
  });
  // Aba escondida: fecha o stream (economiza a rede e o servidor) e reabre ao voltar
  document.addEventListener("visibilitychange", () => {
    videoLigado = !document.hidden;
    if (videoLigado) conectarVideo();
    else { clearTimeout(religar); video.removeAttribute("src"); }
  });
  conectarVideo();

  // ---------------------------------------------------------------- avisos e faixa de alerta
  function avisoErro(texto) {
    $("aviso-erro").querySelector("span").textContent = texto || "";
    $("aviso-erro").hidden = !texto;
  }

  function faixa(dados) {
    const caixa = $("faixa");
    if (!dados.online && !dados.pausada) {
      caixa.classList.add("cobrir");
      caixa.querySelector("span").textContent = "Câmera offline · tentando reconectar…";
      caixa.hidden = false;
    } else if (dados.online && !dados.pausada && dados.saturado) {
      caixa.classList.remove("cobrir");
      caixa.querySelector("span").textContent =
        `Arco detectado – quadro ignorado (${numero(dados.fracao_saturada * 100)}% estourado)`;
      caixa.hidden = false;
    } else {
      caixa.hidden = true;
    }
  }

  // ---------------------------------------------------------------- pessoas agora
  const CLASSE_PESSOA = { CONFORME: "pessoa-c", NAO_CONFORME: "pessoa-n", INDETERMINADO: "pessoa-i" };
  let chavePessoas = "", resumoPessoas = "";

  function cartaoPessoa(pessoa) {
    const estado = ESTADO_DA_COR[pessoa.cor] || "INDETERMINADO";
    const cartao = el("article", { classe: "pessoa " + CLASSE_PESSOA[estado] },
      el("div", { classe: "pessoa-cabecalho" },
        el("span", { classe: "pessoa-id", texto: pessoa.track_id == null ? "#?" : "#" + pessoa.track_id }),
        selo(estado)));
    for (const [epi, info] of Object.entries(pessoa.epis)) {
      cartao.append(el("div", { classe: "pessoa-epi" }, iconeEpi(epi),
        el("div", {},
          el("strong", { texto: nomeEpi(epi) + ": " }), selo(info.estado, { claro: true }),
          info.motivo ? el("div", { classe: "pessoa-motivo", texto: info.motivo }) : null)));
    }
    if (pessoa.mascara_levantada) cartao.append(el("span", { classe: "marca-levantada", texto: "Máscara levantada" }));
    return cartao;
  }

  function mostrarPessoas(dados) {
    const pessoas = dados.pessoas || [];
    $("qtd-pessoas").textContent = dados.online && !dados.pausada ? String(pessoas.length) : "";
    // Só refaz quando algo visível mudou (a confiança muda a cada quadro e não aparece aqui)
    const chave = JSON.stringify([dados.online, dados.pausada, dados.saturado, pessoas.map((p) =>
      [p.track_id, p.cor, p.mascara_levantada, Object.entries(p.epis).map(([n, e]) => [n, e.estado, e.motivo])])]);
    if (chave === chavePessoas) return;
    chavePessoas = chave;

    const lista = $("pessoas");
    let resumo;
    if (dados.pausada) {
      lista.replaceChildren(el("p", { classe: "text-secondary mb-0", texto: "Posto pausado: ninguém está sendo avaliado." }));
      resumo = "Posto pausado.";
    } else if (!dados.online) {
      lista.replaceChildren(el("p", { classe: "text-secondary mb-0", texto: "Sem imagem da câmera." }));
      resumo = "Câmera offline.";
    } else if (dados.saturado && !pessoas.length) {
      lista.replaceChildren(el("p", { classe: "text-secondary mb-0", texto: "Arco aberto: quadro ignorado na avaliação." }));
      resumo = "";
    } else if (!pessoas.length) {
      lista.replaceChildren(el("p", { classe: "text-secondary mb-0", texto: "Ninguém no quadro agora." }));
      resumo = "Ninguém no quadro.";
    } else {
      lista.replaceChildren(...pessoas.map(cartaoPessoa));
      const conta = { CONFORME: 0, NAO_CONFORME: 0, INDETERMINADO: 0 };
      pessoas.forEach((p) => { conta[ESTADO_DA_COR[p.cor] || "INDETERMINADO"] += 1; });
      resumo = `${pessoas.length} ${pessoas.length === 1 ? "pessoa" : "pessoas"}: ` + [
        conta.NAO_CONFORME && `${conta.NAO_CONFORME} não conforme`,
        conta.INDETERMINADO && `${conta.INDETERMINADO} indeterminado`,
        conta.CONFORME && `${conta.CONFORME} conforme`].filter(Boolean).join(", ") + ".";
    }
    // O leitor de tela ouve só o resumo, e só quando ele muda
    if (resumo && resumo !== resumoPessoas) $("pessoas-resumo").textContent = resumo;
    resumoPessoas = resumo || resumoPessoas;
  }

  // ---------------------------------------------------------------- últimas ocorrências
  let chaveUltimas = null;

  function miniatura(url) {
    const img = el("img", { src: url, alt: "", loading: "lazy" });
    img.addEventListener("error", () => img.replaceWith(el("span", { classe: "miniatura d-inline-flex align-items-center justify-content-center" },
      icone("bi-image text-secondary"))), { once: true });
    return img;
  }

  function mostrarUltimas(lista) {
    const chave = lista.map((o) => o.uuid).join();
    if (chave === chaveUltimas) return;
    if (chaveUltimas !== null) EPI.atualizarPendentes();   // ocorrência nova: atualiza o número da barra lateral
    chaveUltimas = chave;
    $("sem-ultimas").hidden = lista.length > 0;
    $("ultimas").replaceChildren(...lista.map((oc) => el("li", {},
      el("a", { href: "/ocorrencias?abrir=" + encodeURIComponent(oc.uuid) },
        miniatura(oc.thumb_url),
        el("div", {},
          el("div", { classe: "hora numero", texto: oc.hora_local }),
          selo("NAO_CONFORME", { claro: true, texto: faltaTexto(oc.epis_faltantes, oc.mascara_levantada) }))))));
  }

  // ---------------------------------------------------------------- cordão do turno (assinatura da T02)
  const canvas = $("cordao");
  const trilho = $("cordao-trilho");
  const CORES = { C: "#198754", I: "#FFC107", N: "#DC3545", V: "#B8C2CC", "-": "#E1E6EB" };
  const GRAVIDADE = { "-": 0, V: 1, C: 2, I: 3, N: 4 };
  let ultimoCordao = null, chavePinos = null;

  function desenharCordao(cordao) {
    const escala = window.devicePixelRatio || 1;
    const largura = Math.max(1, Math.round(trilho.clientWidth * escala));
    const altura = Math.round(24 * escala);
    if (canvas.width !== largura || canvas.height !== altura) { canvas.width = largura; canvas.height = altura; }
    const ctx = canvas.getContext("2d");
    const raio = 5 * escala;
    ctx.clearRect(0, 0, largura, altura);

    // A chapa: o turno inteiro, ainda sem solda
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(0.5 * escala, 0.5 * escala, largura - escala, altura - escala, raio);
    ctx.fillStyle = "#FFFFFF";
    ctx.fill();
    ctx.lineWidth = escala;
    ctx.strokeStyle = "#D5DBE1";
    ctx.stroke();
    ctx.clip();

    const inicio = Date.parse(cordao.inicio), fim = Date.parse(cordao.fim);
    const total = Math.max(1, Math.ceil((fim - inicio) / 1000 / cordao.passo_s));
    const trechos = cordao.trechos;
    const feito = Math.min(largura, Math.round((trechos.length / total) * largura));

    // O cordão: cada coluna de pixels mostra o PIOR estado dos trechos de 10 s que caem nela
    const colunas = new Array(feito);
    for (let x = 0; x < feito; x += 1) {
      const de = Math.floor((x * total) / largura);
      const ate = Math.min(trechos.length, Math.max(de + 1, Math.floor(((x + 1) * total) / largura)));
      let pior = "-";
      for (let i = de; i < ate; i += 1) if (GRAVIDADE[trechos[i]] > GRAVIDADE[pior]) pior = trechos[i];
      colunas[x] = pior;
    }
    let x0 = 0;
    for (let x = 1; x <= feito; x += 1) {
      if (x === feito || colunas[x] !== colunas[x0]) {
        ctx.fillStyle = CORES[colunas[x0]];
        ctx.fillRect(x0, 0, x - x0, altura);
        x0 = x;
      }
    }

    // As escamas do cordão de solda: ondinhas claras, só onde houve gente sendo avaliada
    ctx.strokeStyle = "rgba(255, 255, 255, .28)";
    ctx.lineWidth = escala;
    const passoEscama = 6 * escala;
    for (let x = passoEscama; x < feito; x += passoEscama) {
      const codigo = colunas[Math.floor(x)];
      if (codigo !== "C" && codigo !== "I" && codigo !== "N") continue;
      ctx.beginPath();
      ctx.ellipse(x, altura / 2, 3 * escala, altura / 2 - 3 * escala, 0, -Math.PI / 2, Math.PI / 2);
      ctx.stroke();
    }

    // Agora: a ponta do arame
    if (feito > 0 && feito < largura) {
      ctx.fillStyle = "#1E2933";
      ctx.fillRect(Math.max(0, feito - escala), 0, 2 * escala, altura);
    }
    ctx.restore();
    return { total, duracao: (fim - inicio) / 1000 };
  }

  function mostrarPinos(cordao, duracao) {
    const chave = cordao.inicio + cordao.pinos.map((p) => p.uuid).join();
    if (chave === chavePinos) return;
    chavePinos = chave;
    trilho.querySelectorAll(".cordao-pino").forEach((pino) => pino.remove());
    for (const pino of cordao.pinos) {
      const texto = `Ocorrência às ${pino.hora_local}: ${faltaTexto(pino.epis_faltantes)}`;
      const botao = el("a", { classe: "cordao-pino", href: "/ocorrencias?abrir=" + encodeURIComponent(pino.uuid),
        title: texto, "aria-label": texto }, icone("bi-caret-down-fill"));
      botao.style.left = Math.min(100, Math.max(0, (pino.segundos / duracao) * 100)) + "%";
      trilho.append(botao);
    }
  }

  function resumoCordao(cordao) {
    const conta = { C: 0, I: 0, N: 0 };
    for (const codigo of cordao.trechos) if (codigo in conta) conta[codigo] += 1;
    const avaliados = conta.C + conta.I + conta.N;
    const partes = [cordao.turno ? `Turno ${cordao.turno} (${cordao.inicio_local}–${cordao.fim_local})`
      : `Últimas horas (${cordao.inicio_local}–${cordao.fim_local})`];
    if (avaliados) {
      const fracao = (n) => numero((n / avaliados) * 100) + "%";
      partes.push(`${fracao(conta.C)} conforme, ${fracao(conta.N)} não conforme, ${fracao(conta.I)} indeterminado`);
    } else {
      partes.push("ninguém avaliado ainda");
    }
    const n = cordao.pinos.length;
    partes.push(n === 1 ? "1 ocorrência" : `${n} ocorrências`);
    return partes.join(" · ");
  }

  function mostrarCordao(cordao) {
    ultimoCordao = cordao;
    const { duracao } = desenharCordao(cordao);
    mostrarPinos(cordao, duracao);
    $("cordao-inicio").textContent = cordao.inicio_local;
    $("cordao-fim").textContent = cordao.fim_local;
    $("cordao-resumo").textContent = resumoCordao(cordao);
  }

  new ResizeObserver(() => { if (ultimoCordao) desenharCordao(ultimoCordao); }).observe(trilho);

  // ---------------------------------------------------------------- pausar / retomar (só ADMIN)
  const botaoPausar = $("botao-pausar");
  let pausada = false;
  function mostrarPausa(valor) {
    pausada = valor;
    if (!botaoPausar) return;
    botaoPausar.querySelector("i").className = "bi " + (valor ? "bi-play-fill" : "bi-pause-fill");
    botaoPausar.querySelector("span").textContent = valor ? "Retomar posto" : "Pausar posto";
  }
  if (botaoPausar) botaoPausar.addEventListener("click", async () => {
    if (!pausada && !confirm("Pausar este posto? Enquanto estiver pausado, nenhuma ocorrência é registrada.")) return;
    botaoPausar.disabled = true;
    try {
      const resposta = await api(`/api/cameras/${cameraId}/${pausada ? "retomar" : "pausar"}`, { method: "POST" });
      mostrarPausa(resposta.pausada);
      aviso(resposta.pausada ? "Posto pausado." : "Posto retomado.");
    } catch (falha) {
      aviso(falha.message, "erro");
    } finally {
      botaoPausar.disabled = false;
    }
  });

  // ---------------------------------------------------------------- ciclo de 1 s
  let falhas = 0;
  async function atualizar() {
    try {
      const dados = await api("/api/status?camera_id=" + encodeURIComponent(cameraId));
      falhas = 0;
      $("relogio").textContent = dados.agora_local;
      EPI.mostrarStatusCamera(dados);
      avisoErro(dados.erro ? `Problema na câmera: ${dados.erro}. Fale com o administrador.` : "");
      $("aviso-disco").hidden = !dados.sem_espaco;
      faixa(dados);
      mostrarPausa(dados.pausada);
      mostrarPessoas(dados);
      mostrarUltimas(dados.ultimas_ocorrencias || []);
      mostrarCordao(dados.cordao);
    } catch (falha) {
      falhas += 1;
      if (falhas >= 3) avisoErro("Sem resposta do sistema. Confira se o servidor está ligado; a tela tenta de novo sozinha.");
    } finally {
      setTimeout(atualizar, document.hidden ? 5000 : 1000);
    }
  }
  atualizar();
})();
