/* T03 – Analisar arquivo: envia uma foto ou um vídeo, acompanha a análise e mostra o resultado (sempre borrado). */
"use strict";

(() => {
  const { api, el, selo, numero, aviso } = EPI;
  const $ = (id) => document.getElementById(id);
  const tamanhoMaxMb = Number($("conteudo").dataset.tamanhoMaxMb) || 200;
  // Tipos aceitos (o servidor confere o conteúdo de verdade; aqui é só resposta rápida)
  const EXTENSOES = [".jpg", ".jpeg", ".png", ".mp4"];
  const NOMES_ESTADO = { CONFORME: "conforme", NAO_CONFORME: "não conforme", INDETERMINADO: "indeterminado" };

  const area = $("area-envio");
  const entrada = $("arquivo");
  const posto = $("posto-upload");
  // Id da análise em andamento (se o usuário mandar outro arquivo, o resultado antigo é ignorado) e o temporizador da consulta
  let trabalhoAtual = null, consulta = null;

  // O posto escolhido no topo vale também aqui
  const escolhido = EPI.postoSelecionado();
  if (posto && escolhido && [...posto.options].some((o) => Number(o.value) === escolhido)) posto.value = String(escolhido);

  /** Mostra (ou esconde, se vazio) o erro de envio. */
  function erro(texto) {
    $("erro-envio").querySelector("span").textContent = texto || "";
    $("erro-envio").hidden = !texto;
  }

  /** Barra de progresso: texto null esconde; fracao entre 0 e 1 (atualiza também aria-valuenow, lido por leitor de tela). */
  function andamento(texto, fracao) {
    $("andamento").hidden = texto === null;
    if (texto === null) return;
    const pct = Math.round(Math.min(1, Math.max(0, fracao)) * 100);
    $("andamento-texto").textContent = texto;
    $("andamento-pct").textContent = pct + "%";
    $("barra").setAttribute("aria-valuenow", String(pct));
    $("barra-valor").style.width = pct + "%";
  }

  /** Esconde o resultado anterior e cancela a consulta pendente antes de um novo envio. */
  function limparResultado() {
    clearTimeout(consulta);
    trabalhoAtual = null;
    $("resultado").hidden = true;
    $("midia").replaceChildren();
    $("tabela-pessoas").replaceChildren();
    $("registrado").hidden = true;
  }

  // ---------------------------------------------------------------- escolher / arrastar
  entrada.addEventListener("change", () => { if (entrada.files.length) enviar(entrada.files[0]); });
  ["dragenter", "dragover"].forEach((nome) => area.addEventListener(nome, (evento) => {
    evento.preventDefault();
    area.classList.add("arrastando");
  }));
  ["dragleave", "drop"].forEach((nome) => area.addEventListener(nome, (evento) => {
    evento.preventDefault();
    area.classList.remove("arrastando");
  }));
  area.addEventListener("drop", (evento) => {
    const arquivos = evento.dataTransfer && evento.dataTransfer.files;
    if (arquivos && arquivos.length) enviar(arquivos[0]);
  });

  /** Confere extensão, tamanho zero e tamanho máximo. Devolve a mensagem do problema ou null se o arquivo serve. */
  function problemaNoArquivo(arquivo) {
    const nome = arquivo.name.toLowerCase();
    if (!EXTENSOES.some((ext) => nome.endsWith(ext))) return "Tipo não aceito: envie uma foto .jpg/.png ou um vídeo .mp4.";
    if (arquivo.size === 0) return "Arquivo vazio.";
    if (arquivo.size > tamanhoMaxMb * 1024 * 1024) return `Arquivo maior que ${tamanhoMaxMb} MB.`;
    return null;
  }

  // ---------------------------------------------------------------- envio (XHR para ter o progresso)
  /** Envia o arquivo para /api/uploads. Usa XMLHttpRequest (e não fetch) porque só ele informa o progresso do envio. */
  function enviar(arquivo) {
    erro("");
    limparResultado();
    const problema = problemaNoArquivo(arquivo);
    if (problema) { erro(problema); entrada.value = ""; return; }

    const dados = new FormData();
    dados.append("arquivo", arquivo);
    if (posto && posto.value) dados.append("camera_id", posto.value);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/uploads");
    // Token CSRF lido da <meta> do base.html (aqui não passa pelo EPI.api)
    xhr.setRequestHeader("X-CSRF-Token", document.querySelector('meta[name="csrf-token"]').content);
    xhr.upload.addEventListener("progress", (evento) => {
      if (evento.lengthComputable) andamento(`Enviando ${arquivo.name}…`, evento.loaded / evento.total);
    });
    xhr.addEventListener("load", () => {
      entrada.value = "";
      let resposta = null;
      try { resposta = JSON.parse(xhr.responseText); } catch (_) { resposta = null; }
      if (xhr.status === 401) {
        location.href = "/login?expirou=1&proximo=" + encodeURIComponent(location.pathname);
        return;
      }
      // 202 = aceito: a análise roda em segundo plano e é acompanhada abaixo
      if (xhr.status !== 202 || !resposta) {
        andamento(null);
        erro(resposta && typeof resposta.detail === "string" ? resposta.detail : `Erro ${xhr.status} ao enviar o arquivo.`);
        return;
      }
      trabalhoAtual = resposta.id;
      acompanhar(resposta);
    });
    xhr.addEventListener("error", () => {
      entrada.value = "";
      andamento(null);
      erro("Sem conexão com o sistema. Confira se o servidor está ligado.");
    });
    andamento(`Enviando ${arquivo.name}…`, 0);
    xhr.send(dados);
  }

  // ---------------------------------------------------------------- acompanhar a análise
  /** Consulta o andamento da análise a cada 0,7 s até ela terminar (concluído ou erro). */
  function acompanhar(resumo) {
    if (resumo.id !== trabalhoAtual) return;   // o usuário já mandou outro arquivo
    if (resumo.estado === "erro") {
      andamento(null);
      erro(resumo.erro || "Não foi possível analisar o arquivo.");
      return;
    }
    if (resumo.estado === "concluido") {
      andamento(null);
      mostrarResultado(resumo);
      return;
    }
    andamento(resumo.estado === "na_fila" ? "Na fila: outro arquivo está sendo analisado…" : "Analisando…",
      resumo.estado === "na_fila" ? 0 : resumo.progresso);
    consulta = setTimeout(async () => {
      try {
        acompanhar(await api("/api/uploads/" + encodeURIComponent(resumo.id)));
      } catch (falha) {
        andamento(null);
        erro(falha.message);
      }
    }, 700);
  }

  // ---------------------------------------------------------------- resultado
  /** Célula da máscara de uma pessoa: estado predominante e, em vídeo, a distribuição entre os estados. */
  function celulaMascara(info) {
    if (!info) return el("td", { texto: "—" });
    const partes = Object.entries(info.percentuais)
      .sort((a, b) => b[1] - a[1])
      .map(([estado, fracao]) => `${NOMES_ESTADO[estado] || estado} ${numero(fracao * 100)}%`);
    return el("td", {}, selo(info.predominante, { claro: true }),
      partes.length > 1 ? el("div", { classe: "small text-secondary", texto: partes.join(" · ") }) : null);
  }

  /** Mostra mídia resultante (cabeças já borradas pelo servidor), tabela de pessoas e as ocorrências encontradas. */
  function mostrarResultado(resumo) {
    const url = resumo.arquivo_url;
    const ehImagem = (resumo.tipo_arquivo || "").startsWith("image/");
    $("midia").replaceChildren(ehImagem
      ? el("img", { src: url, alt: "Resultado da análise, com as cabeças borradas e as caixas de cada pessoa" })
      : el("video", { src: url, controls: true, preload: "metadata", "aria-label": "Vídeo do resultado da análise, com as cabeças borradas" }));
    $("baixar-resultado").href = url;

    const pessoas = resumo.pessoas || [];
    $("tabela-pessoas").replaceChildren(...(pessoas.length ? pessoas.map((p) => el("tr", {},
      el("td", { classe: "numero", texto: p.track_id == null ? "#?" : "#" + p.track_id }),
      celulaMascara(p.epis && p.epis.mascara),
      el("td", { texto: p.mascara_levantada_frames > 0
        ? (resumo.tipo === "video" ? `Sim (${numero(p.mascara_levantada_frames)} quadros)` : "Sim") : "Não" })))
      : [el("tr", {}, el("td", { colspan: "3", classe: "text-secondary", texto: "Nenhuma pessoa encontrada no arquivo." }))]));

    const encontradas = resumo.ocorrencias_encontradas || [];
    $("bloco-ocorrencias").hidden = false;
    $("qtd-ocorrencias").textContent = encontradas.length === 0 ? "Nenhuma falta de EPI encontrada."
      : `${encontradas.length} ${encontradas.length === 1 ? "ocorrência encontrada" : "ocorrências encontradas"}: `
        + encontradas.map((oc) => `#${oc.track_id ?? "?"} ${EPI.faltaTexto(oc.epis_faltantes,
          Object.values(oc.situacao || {}).some((m) => /levantada/i.test(m))).toLowerCase()}`).join(", ") + ".";
    $("botao-registrar").hidden = encontradas.length === 0;
    if (resumo.registradas) mostrarRegistrado(resumo.registradas);
    $("resultado").hidden = false;
    $("resultado").scrollIntoView({ behavior: EPI.movimentoReduzido() ? "auto" : "smooth", block: "start" });
  }

  /** Troca o bloco de registrar pela confirmação, com link para as ocorrências pendentes. */
  function mostrarRegistrado(uuids) {
    $("bloco-ocorrencias").hidden = true;
    const caixa = $("registrado");
    caixa.querySelector("span").replaceChildren(
      uuids.length === 1 ? "1 ocorrência registrada. " : `${uuids.length} ocorrências registradas. `,
      el("a", { href: "/ocorrencias?validacao=PENDENTE", texto: "Ver em Ocorrências" }));
    caixa.hidden = false;
  }

  // Só vira ocorrência de verdade (e vai para a validação) quando a pessoa pede aqui; a análise sozinha não grava nada
  $("botao-registrar").addEventListener("click", async () => {
    if (!trabalhoAtual) return;
    const botao = $("botao-registrar");
    botao.disabled = true;
    try {
      const resposta = await api(`/api/uploads/${encodeURIComponent(trabalhoAtual)}/registrar`, { method: "POST" });
      mostrarRegistrado(resposta.registradas);
      aviso("Ocorrências registradas.");
      EPI.atualizarPendentes();
    } catch (falha) {
      aviso(falha.message, "erro");
    } finally {
      botao.disabled = false;
    }
  });
})();
