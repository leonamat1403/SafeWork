/* Troca de senha (obrigatória no primeiro acesso e depois de uma redefinição pelo administrador). */
"use strict";

(() => {
  const form = document.getElementById("form-senha");
  const atual = document.getElementById("senha-atual");
  const nova = document.getElementById("nova-senha");
  const repita = document.getElementById("repita-senha");
  const caixaErro = document.getElementById("erro-senha");
  const login = (form.dataset.login || "").trim().toLowerCase();

  // Mesmas regras do servidor (app/auth.py, problema_na_senha); o servidor confere de novo
  const regras = {
    tamanho: () => nova.value.length >= 8,
    diferente: () => nova.value.length > 0 && nova.value.trim().toLowerCase() !== login && nova.value !== atual.value,
    igual: () => nova.value.length > 0 && nova.value === repita.value,
  };

  function conferir() {
    let tudoOk = true;
    for (const [nome, regra] of Object.entries(regras)) {
      const ok = regra();
      tudoOk = tudoOk && ok;
      const item = form.querySelector(`[data-regra="${nome}"]`);
      item.classList.toggle("ok", ok);
      item.querySelector("i").className = "bi " + (ok ? "bi-check-circle-fill" : "bi-dash");
    }
    return tudoOk;
  }

  function erro(texto) {
    caixaErro.querySelector("span").textContent = texto;
    caixaErro.hidden = !texto;
  }

  [atual, nova, repita].forEach((campo) => campo.addEventListener("input", conferir));

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    erro("");
    if (!atual.value) { erro("Digite a senha atual."); atual.focus(); return; }
    if (!conferir()) { erro("A nova senha ainda não cumpre as regras da lista."); nova.focus(); return; }
    const botao = form.querySelector('button[type="submit"]');
    botao.disabled = true;
    try {
      await EPI.api("/api/trocar-senha", { method: "POST", json: { senha_atual: atual.value, nova_senha: nova.value } });
      location.href = "/ao-vivo";
    } catch (falha) {
      erro(falha.message);
    } finally {
      botao.disabled = false;
    }
  });
})();
