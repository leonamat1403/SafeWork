/* T08 – Usuários (só administrador): lista, novo usuário, desativar/reativar e redefinir senha. */
"use strict";

(() => {
  const { api, el, icone, aviso } = EPI;
  const $ = (id) => document.getElementById(id);
  const LOGIN_VALIDO = /^[A-Za-z0-9._-]{3,50}$/;
  const PERFIS = { ADMIN: "Administrador", SUPERVISOR: "Supervisor" };
  const modalNovo = bootstrap.Modal.getOrCreateInstance($("modal-novo"));

  // ---------------------------------------------------------------- lista
  function situacao(u) {
    const partes = [el("span", { classe: u.ativo ? "" : "text-secondary" },
      icone(u.ativo ? "bi-person-check me-1" : "bi-person-slash me-1"), u.ativo ? "Ativo" : "Desativado")];
    if (u.ativo && u.deve_trocar_senha) partes.push(el("div", { classe: "small text-secondary", texto: "falta trocar a senha inicial" }));
    return el("td", {}, ...partes);
  }

  function acoes(u) {
    const redefinir = el("button", { type: "button", classe: "btn btn-sm btn-outline-secondary" },
      icone("bi-key me-1"), "Redefinir senha");
    redefinir.addEventListener("click", () => redefinirSenha(u));
    const alternar = el("button", { type: "button", classe: "btn btn-sm " + (u.ativo ? "btn-outline-danger" : "btn-outline-primary") },
      icone(u.ativo ? "bi-person-slash me-1" : "bi-person-check me-1"), u.ativo ? "Desativar" : "Reativar");
    if (u.voce && u.ativo) {
      alternar.disabled = true;
      alternar.title = "Você não pode desativar o seu próprio usuário.";
    }
    alternar.addEventListener("click", () => (u.ativo ? desativar(u) : reativar(u)));
    redefinir.hidden = !u.ativo || u.voce;   // a própria senha muda em "Trocar senha"
    return el("td", { classe: "text-end" }, el("div", { classe: "d-inline-flex flex-wrap gap-2 justify-content-end" }, redefinir, alternar));
  }

  async function carregar() {
    try {
      const usuarios = await api("/api/usuarios");
      $("linhas").replaceChildren(...usuarios.map((u) => el("tr", { classe: u.ativo ? "" : "text-secondary" },
        el("td", {}, el("strong", { texto: u.nome }), u.voce ? el("span", { classe: "text-secondary", texto: " (você)" }) : null),
        el("td", { classe: "numero", texto: u.login }),
        el("td", { texto: PERFIS[u.perfil] || u.perfil }),
        situacao(u),
        el("td", { classe: "numero", texto: u.criado_em }),
        acoes(u))));
    } catch (falha) {
      aviso(falha.message, "erro");
    }
  }

  // ---------------------------------------------------------------- ações
  async function desativar(u) {
    if (!confirm(`Desativar ${u.nome}? A pessoa não consegue mais entrar, mas o histórico dela fica guardado.`)) return;
    try {
      await api(`/api/usuarios/${u.id}/desativar`, { method: "POST" });
      aviso(`${u.nome} foi desativado(a).`);
      carregar();
    } catch (falha) { aviso(falha.message, "erro"); }
  }

  async function reativar(u) {
    try {
      await api(`/api/usuarios/${u.id}/reativar`, { method: "POST" });
      aviso(`${u.nome} foi reativado(a).`);
      carregar();
    } catch (falha) { aviso(falha.message, "erro"); }
  }

  async function redefinirSenha(u) {
    if (!confirm(`Gerar uma senha temporária para ${u.nome}? A senha atual deixa de funcionar.`)) return;
    try {
      const resposta = await api(`/api/usuarios/${u.id}/senha`, { method: "POST" });
      $("senha-gerada-login").textContent = resposta.login;
      $("senha-gerada-valor").textContent = resposta.senha_temporaria;
      $("senha-gerada").hidden = false;
      $("senha-gerada").scrollIntoView({ behavior: EPI.movimentoReduzido() ? "auto" : "smooth", block: "center" });
      carregar();
    } catch (falha) { aviso(falha.message, "erro"); }
  }

  $("copiar-senha").addEventListener("click", async () => {
    const valor = $("senha-gerada-valor");
    try {
      await navigator.clipboard.writeText(valor.textContent);
      aviso("Senha copiada.");
    } catch (_) {
      // Fora de https/localhost o navegador não deixa copiar por script: seleciona o texto para Ctrl+C
      const faixa = document.createRange();
      faixa.selectNodeContents(valor);
      const selecao = getSelection();
      selecao.removeAllRanges();
      selecao.addRange(faixa);
      aviso("Senha selecionada: aperte Ctrl+C para copiar.");
    }
  });

  // ---------------------------------------------------------------- novo usuário
  const form = $("form-novo");
  function erroNovo(texto) {
    $("erro-novo").querySelector("span").textContent = texto || "";
    $("erro-novo").hidden = !texto;
  }

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    erroNovo("");
    const nome = $("novo-nome").value.trim();
    const login = $("novo-login").value.trim();
    const senha = $("novo-senha").value;
    const perfil = form.querySelector('input[name="perfil"]:checked').value;
    if (nome.length < 2) { erroNovo("Informe o nome (pelo menos 2 caracteres)."); $("novo-nome").focus(); return; }
    if (!LOGIN_VALIDO.test(login)) {
      erroNovo("O login deve ter de 3 a 50 caracteres: letras sem acento, números, ponto, hífen ou _.");
      $("novo-login").focus();
      return;
    }
    if (senha.length < 8) { erroNovo("A senha inicial precisa ter pelo menos 8 caracteres."); $("novo-senha").focus(); return; }
    if (senha.trim().toLowerCase() === login.toLowerCase()) {
      erroNovo("A senha não pode ser igual ao login."); $("novo-senha").focus(); return;
    }
    const botao = form.querySelector('button[type="submit"]');
    botao.disabled = true;
    try {
      await api("/api/usuarios", { method: "POST", json: { nome, login, perfil, senha_inicial: senha } });
      modalNovo.hide();
      aviso(`Usuário ${login} criado. No primeiro acesso a pessoa troca a senha.`);
      carregar();
    } catch (falha) {
      erroNovo(falha.message);
    } finally {
      botao.disabled = false;
    }
  });

  $("modal-novo").addEventListener("hidden.bs.modal", () => { form.reset(); erroNovo(""); });
  $("modal-novo").addEventListener("shown.bs.modal", () => $("novo-nome").focus());

  carregar();
})();
