/* T01 – Login. Depois de entrar vai para a troca obrigatória de senha ou para a página pedida. */
"use strict";

(() => {
  const form = document.getElementById("form-login");
  const campoLogin = document.getElementById("login");
  const campoSenha = document.getElementById("senha");
  const botao = document.getElementById("botao-entrar");
  const caixaErro = document.getElementById("erro-login");
  const mostrar = document.getElementById("mostrar-senha");

  /** Mostra a mensagem de erro no aviso do formulário; texto vazio esconde o aviso. */
  function erro(texto) {
    caixaErro.querySelector("span").textContent = texto;
    caixaErro.hidden = !texto;
  }

  // Botão do olho: alterna entre senha escondida e visível (aria-pressed e aria-label avisam o leitor de tela)
  mostrar.addEventListener("click", () => {
    const visivel = campoSenha.type === "password";
    campoSenha.type = visivel ? "text" : "password";
    mostrar.setAttribute("aria-pressed", String(visivel));
    mostrar.setAttribute("aria-label", visivel ? "Esconder senha" : "Mostrar senha");
    mostrar.querySelector("i").className = "bi " + (visivel ? "bi-eye-slash" : "bi-eye");
  });

  // Envio: confere os campos, chama POST /login e segue para a troca de senha (se obrigatória) ou para a página pedida
  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    erro("");
    if (!campoLogin.value.trim() || !campoSenha.value) {
      erro("Preencha o usuário e a senha.");
      (campoLogin.value.trim() ? campoSenha : campoLogin).focus();
      return;
    }
    // Desabilita o botão durante o envio para evitar duplo clique
    botao.disabled = true;
    botao.textContent = "Entrando…";
    try {
      // fetch direto (e não EPI.api): o login ainda não tem sessão, e um erro aqui é senha errada, não sessão expirada
      const resposta = await fetch("/login", {
        method: "POST", credentials: "same-origin",
        body: new URLSearchParams({ login: campoLogin.value.trim(), senha: campoSenha.value }),
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        erro(typeof dados.detail === "string" ? dados.detail : "Não foi possível entrar. Tente de novo.");
        // Segurança: apaga a senha errada do campo
        campoSenha.value = "";
        campoSenha.focus();
        return;
      }
      location.href = dados.deve_trocar_senha ? "/trocar-senha" : (form.dataset.proximo || "/ao-vivo");
    } catch (_) {
      erro("Sem conexão com o sistema. Confira se o servidor está ligado.");
    } finally {
      botao.disabled = false;
      botao.textContent = "Entrar";
    }
  });
})();
