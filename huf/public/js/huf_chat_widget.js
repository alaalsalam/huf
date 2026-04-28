(function () {
  const WIDGET_ID = "huf-enhanced-chat-widget";
  const API = "huf.api.chat";
  const DEFAULT_PROMPTS = [
    "اعرض مبيعات هذا الشهر",
    "لخص حالة المخزون",
    "ما الفواتير المتأخرة؟",
    "أنشئ مهمة متابعة للعميل",
    "اقترح تحسينات على التدفق النقدي",
  ];

  const state = {
    config: null,
    open: false,
    loading: false,
    sending: false,
    sessionId: null,
    messagesLoaded: false,
    lastAssistantMeta: null,
    lastFailedText: "",
    routeWatcher: null,
    selectedAgent: null,
  };

  function isDesk() {
    const path = window.location.pathname || "";
    return path.startsWith("/app") && !path.includes("/login") && !path.includes("/website");
  }

  function isHomeRoute() {
    const path = window.location.pathname || "";
    if (path === "/app" || path === "/app/" || path === "/app/home") return true;
    const route = window.frappe?.get_route ? window.frappe.get_route() : [];
    const first = String(route?.[0] || "").toLowerCase();
    return ["", "home", "workspaces", "workspace"].includes(first);
  }

  function isArabic(config) {
    const lang = config?.language || window.frappe?.boot?.lang || document.documentElement.lang || "";
    return Boolean(config?.rtl || document.dir === "rtl" || String(lang).toLowerCase().startsWith("ar"));
  }

  function label(key, fallback) {
    return state.config?.labels?.[key] || fallback;
  }

  function agentOptions(config) {
    const agents = Array.isArray(config?.agents) ? config.agents : [];
    if (!agents.length) return "";
    return agents.map((agent) => `<option value="${escapeAttr(agent.name)}" ${agent.is_default ? "selected" : ""}>${escapeHtml(agent.title || agent.name)}</option>`).join("");
  }

  function selectedAgentArg() {
    return state.selectedAgent ? { agent: state.selectedAgent } : {};
  }

  function call(method, args) {
    return new Promise((resolve, reject) => {
      if (!window.frappe?.call) {
        reject(new Error("Frappe API is not available"));
        return;
      }
      window.frappe.call({
        method: `${API}.${method}`,
        args: args || {},
        freeze: false,
        callback: (r) => resolve(r.message || {}),
        error: (err) => reject(err),
      });
    });
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "\"": "&quot;",
      "'": "&#039;",
    }[char]));
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }

  function safeUrl(value) {
    const raw = String(value || "").trim();
    if (/^(https?:|mailto:|\/)/i.test(raw)) return escapeAttr(raw);
    return "#";
  }

  function inlineMarkdown(text) {
    return escapeHtml(text)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, title, url) => `<a href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`);
  }

  function renderTable(lines) {
    const rows = lines
      .filter((line) => line.includes("|"))
      .map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => inlineMarkdown(cell.trim())));
    if (rows.length < 2) return "";
    const header = rows[0];
    const body = rows.slice(2).length ? rows.slice(2) : rows.slice(1);
    return `<div class="huf-chat-table-wrap"><table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  function renderMarkdownBlock(block) {
    const lines = block.split("\n");
    if (lines.length > 1 && lines[0].includes("|") && lines[1].includes("|")) {
      return renderTable(lines);
    }
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return `<ul>${lines.map((line) => `<li>${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    }
    if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
      return `<ol>${lines.map((line) => `<li>${inlineMarkdown(line.replace(/^\s*\d+\.\s+/, ""))}</li>`).join("")}</ol>`;
    }
    return `<p>${lines.map(inlineMarkdown).join("<br>")}</p>`;
  }

  function renderMarkdown(text) {
    const input = String(text || "");
    const html = [];
    const parts = input.split(/(```[\s\S]*?```)/g);
    parts.forEach((part) => {
      if (!part) return;
      if (part.startsWith("```")) {
        html.push(`<pre><code>${escapeHtml(part.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/```$/, ""))}</code></pre>`);
        return;
      }
      const chunks = part.split(/\n{2,}/);
      for (let i = 0; i < chunks.length; i += 1) {
      const block = chunks[i].trim();
      if (!block) continue;
        html.push(renderMarkdownBlock(block));
      }
    });
    return html.join("") || "<p></p>";
  }

  function messageDir(text) {
    return /[\u0600-\u06FF]/.test(String(text || "")) ? "rtl" : "ltr";
  }

  function setOpen(root, open) {
    state.open = open;
    root.classList.toggle("open", open);
    root.querySelector(".huf-chat-launch")?.setAttribute("aria-expanded", String(open));
    if (open) {
      if (!state.messagesLoaded) loadInitialMessages(root);
      setTimeout(() => root.querySelector("[data-composer]")?.focus(), 120);
    }
  }

  function scrollToBottom(root) {
    const list = root.querySelector("[data-chat-list]");
    if (list) list.scrollTop = list.scrollHeight;
  }

  function removeEmptyState(root) {
    root.querySelector("[data-empty-state]")?.remove();
  }

  function ensureEmptyState(root) {
    const list = root.querySelector("[data-chat-list]");
    if (!list || list.querySelector(".huf-chat-msg") || list.querySelector("[data-empty-state]")) return;
    const prompts = state.config?.suggested_prompts?.length ? state.config.suggested_prompts : DEFAULT_PROMPTS;
    list.insertAdjacentHTML("beforeend", `
      <section class="huf-chat-empty" data-empty-state>
        <div class="huf-chat-empty-icon" aria-hidden="true">AI</div>
        <h3>${escapeHtml(label("empty_title", "كيف أستطيع مساعدتك؟"))}</h3>
        <p>${escapeHtml(label("empty_text", "اسألني عن بيانات ERPNext أو اطلب تلخيصًا أو إجراءً آمنًا."))}</p>
        <div class="huf-chat-suggestions">
          ${prompts.map((prompt) => `<button type="button" data-prompt="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("")}
        </div>
      </section>
    `);
  }

  function addMessage(root, role, text, meta) {
    removeEmptyState(root);
    const list = root.querySelector("[data-chat-list]");
    const node = document.createElement("article");
    node.className = `huf-chat-msg ${role}`;
    node.dataset.role = role;
    if (meta?.message_id) node.dataset.messageId = meta.message_id;
    const isAssistant = role === "assistant";
    const feedback = isAssistant && meta?.message_id ? `
      <div class="huf-chat-feedback" aria-label="Feedback">
        <button type="button" title="مفيد" data-feedback="Positive">👍</button>
        <button type="button" title="غير مفيد" data-feedback="Negative">👎</button>
        ${meta?.debug_available ? `<button type="button" data-debug-trigger>${escapeHtml(label("show_details", "إظهار التفاصيل"))}</button>` : ""}
        <span data-feedback-note hidden>${escapeHtml(label("feedback_saved", "تم تسجيل ملاحظتك"))}</span>
      </div>` : "";
    node.innerHTML = `
      <div class="huf-chat-bubble" dir="${messageDir(text)}">
        <div class="huf-chat-content">${renderMarkdown(text)}</div>
        ${feedback}
      </div>
    `;
    list.appendChild(node);
    scrollToBottom(root);
    return node;
  }

  function addTyping(root) {
    removeEmptyState(root);
    const list = root.querySelector("[data-chat-list]");
    const node = document.createElement("article");
    node.className = "huf-chat-msg assistant typing";
    node.dataset.typing = "1";
    node.innerHTML = `
      <div class="huf-chat-bubble">
        <span class="huf-typing-label">${escapeHtml(label("thinking", "جاري التفكير..."))}</span>
        <span class="huf-typing-dots"><i></i><i></i><i></i></span>
      </div>
    `;
    list.appendChild(node);
    scrollToBottom(root);
    return node;
  }

  function showError(root, text) {
    const node = addMessage(root, "assistant", text || label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول."));
    if (state.lastFailedText) {
      node.querySelector(".huf-chat-bubble").insertAdjacentHTML("beforeend", `<button type="button" class="huf-chat-retry" data-retry>${escapeHtml(label("retry", "إعادة المحاولة"))}</button>`);
    }
  }

  function setSending(root, sending) {
    state.sending = sending;
    root.classList.toggle("sending", sending);
    const send = root.querySelector("[data-send]");
    const composer = root.querySelector("[data-composer]");
    if (send) send.disabled = sending || !composer?.value.trim();
  }

  function autoGrow(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 132)}px`;
  }

  async function loadInitialMessages(root) {
    state.messagesLoaded = true;
    ensureEmptyState(root);
  }

  async function startNew(root) {
    try {
      const res = await call("new_session", { title: state.config?.default_title || "HUF Assistant", ...selectedAgentArg() });
      state.sessionId = res.session_id || res.name || null;
      root.querySelector("[data-chat-list]").innerHTML = "";
      state.lastAssistantMeta = null;
      ensureEmptyState(root);
      root.querySelector("[data-composer]")?.focus();
    } catch (err) {
      console.error(err);
      showError(root);
    }
  }

  async function send(root, rawText) {
    const text = String(rawText || "").trim();
    if (!text || state.sending) return;
    state.lastFailedText = text;
    addMessage(root, "user", text);
    const composer = root.querySelector("[data-composer]");
    composer.value = "";
    autoGrow(composer);
    setSending(root, true);
    const typing = addTyping(root);
    try {
      const res = await call("send_message", { message: text, session_id: state.sessionId, ...selectedAgentArg() });
      state.sessionId = res.session_id || state.sessionId;
      state.lastAssistantMeta = res;
      typing.remove();
      addMessage(root, "assistant", res.content || "لم يصل رد واضح.", res);
      if (res.requires_confirmation) {
        addMessage(root, "assistant", `يتطلب هذا الطلب تأكيدًا قبل التنفيذ: ${res.confirmation?.summary || "إجراء حساس"}`, res);
      }
      state.lastFailedText = "";
    } catch (err) {
      console.error(err);
      typing.remove();
      showError(root);
    } finally {
      setSending(root, false);
      composer.focus();
    }
  }

  async function submitFeedback(root, button) {
    const msg = button.closest(".huf-chat-msg");
    const messageId = msg?.dataset.messageId;
    if (!messageId) return;
    const rating = button.dataset.feedback;
    const comment = rating === "Negative" ? window.prompt("ما الذي يمكن تحسينه؟") || "" : "";
    button.disabled = true;
    try {
      await call("submit_feedback", { message_id: messageId, rating, comment });
      msg.querySelector("[data-feedback-note]")?.removeAttribute("hidden");
    } catch (err) {
      console.error(err);
      button.disabled = false;
      window.frappe?.show_alert?.({ message: label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول."), indicator: "red" });
    }
  }

  async function toggleDebug(root) {
    const panel = root.querySelector("[data-debug-panel]");
    const pre = root.querySelector("[data-debug-output]");
    if (!panel || !state.config?.debug_available) return;
    const open = panel.hidden;
    panel.hidden = !open;
    if (!open) return;
    pre.textContent = label("loading", "جاري التحميل...");
    try {
      const trace = await call("get_debug_trace", { session_id: state.sessionId, run_id: state.lastAssistantMeta?.metadata?.run_id });
      pre.textContent = JSON.stringify(trace, null, 2);
    } catch (err) {
      console.error(err);
      pre.textContent = label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول.");
    }
  }

  function renderShell(config) {
    const rtl = isArabic(config);
    const root = document.createElement("div");
    root.id = WIDGET_ID;
    root.dir = rtl ? "rtl" : "ltr";
    const launchLabel = rtl ? "مساعد HUF" : "HUF Assistant";
    root.innerHTML = `
      <button class="huf-chat-launch" type="button" aria-label="${escapeAttr(launchLabel)}" aria-expanded="false" title="${escapeAttr(launchLabel)}">
        <span class="huf-launch-icon" aria-hidden="true">AI</span>
        <span class="huf-launch-tip">${escapeHtml(launchLabel)}</span>
      </button>
      <aside class="huf-chat-panel" aria-label="${escapeAttr(label("title", "مساعد HUF الذكي"))}">
        <header class="huf-chat-header">
          <div class="huf-chat-title-wrap">
            <span class="huf-chat-avatar" aria-hidden="true">AI</span>
            <div>
              <strong>${escapeHtml(label("title", "مساعد HUF الذكي"))}</strong>
              <small>${escapeHtml(label("subtitle", "اسأل عن المبيعات، المخزون، الفواتير، أو المهام"))}</small>
            </div>
          </div>
          <div class="huf-chat-actions">
            <button type="button" data-new-chat title="${escapeAttr(label("new_chat", "محادثة جديدة"))}">＋</button>
            <a href="/app/huf-chat" title="${escapeAttr(label("expand", "فتح الصفحة الكاملة"))}" aria-label="${escapeAttr(label("expand", "فتح الصفحة الكاملة"))}">↗</a>
            <button type="button" data-close title="${escapeAttr(label("close", "إغلاق"))}">×</button>
          </div>
        </header>
        ${config.can_select_agent && Array.isArray(config.agents) && config.agents.length ? `
          <section class="huf-chat-agent-strip">
            <label>${escapeHtml(label("agent", "الوكيل"))}</label>
            <select data-agent-selector aria-label="${escapeAttr(label("agent", "الوكيل"))}">
              ${agentOptions(config)}
            </select>
          </section>` : ""}
        <main class="huf-chat-messages" data-chat-list></main>
        <section class="huf-chat-debug" data-debug-panel hidden>
          <div class="huf-chat-debug-head">${escapeHtml(label("details", "التفاصيل"))}</div>
          <pre data-debug-output></pre>
        </section>
        ${config.can_select_agent || config.can_select_model ? `
          <details class="huf-chat-advanced">
            <summary>${escapeHtml(label("advanced", "خيارات متقدمة"))}</summary>
            <p>${escapeHtml(label("advanced_hint", "سيتم استخدام الوكيل والنموذج الافتراضيين ما لم يتم تحديد غير ذلك من الإعدادات."))}</p>
          </details>` : ""}
        <footer class="huf-chat-composer">
          <textarea data-composer rows="1" placeholder="${escapeAttr(label("placeholder", rtl ? "اكتب سؤالك هنا…" : "Ask HUF Assistant…"))}"></textarea>
          <button type="button" data-send disabled title="${escapeAttr(label("send", "إرسال"))}" aria-label="${escapeAttr(label("send", "إرسال"))}">➤</button>
        </footer>
      </aside>
    `;
    document.body.appendChild(root);
    ensureEmptyState(root);
    return root;
  }

  function bind(root) {
    const composer = root.querySelector("[data-composer]");
    const agentSelector = root.querySelector("[data-agent-selector]");
    if (agentSelector) {
      state.selectedAgent = agentSelector.value || state.config?.default_agent || null;
      agentSelector.addEventListener("change", () => {
        state.selectedAgent = agentSelector.value || null;
        state.sessionId = null;
        state.messagesLoaded = true;
        root.querySelector("[data-chat-list]").innerHTML = "";
        state.lastAssistantMeta = null;
        ensureEmptyState(root);
        root.querySelector("[data-composer]")?.focus();
      });
    } else {
      state.selectedAgent = state.config?.default_agent || null;
    }
    root.querySelector(".huf-chat-launch").addEventListener("click", () => setOpen(root, !state.open));
    root.querySelector("[data-close]").addEventListener("click", () => setOpen(root, false));
    root.querySelector("[data-new-chat]").addEventListener("click", () => startNew(root));
    root.querySelector("[data-send]").addEventListener("click", () => send(root, composer.value));
    composer.addEventListener("input", () => {
      autoGrow(composer);
      root.querySelector("[data-send]").disabled = state.sending || !composer.value.trim();
    });
    composer.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send(root, composer.value);
      }
    });
    root.addEventListener("click", (event) => {
      const prompt = event.target.closest("[data-prompt]");
      if (prompt) send(root, prompt.dataset.prompt);
      const feedback = event.target.closest("[data-feedback]");
      if (feedback) submitFeedback(root, feedback);
      if (event.target.closest("[data-debug-trigger]")) toggleDebug(root);
      if (event.target.closest("[data-retry]")) send(root, state.lastFailedText);
    });
  }

  function findHomeTarget() {
    return document.querySelector(".layout-main-section") ||
      document.querySelector(".page-body .container") ||
      document.querySelector(".desk-page") ||
      document.querySelector(".page-container");
  }

  function removeHomeCard() {
    document.getElementById("huf-home-chat-card")?.remove();
  }

  function ensureHomeCard(root) {
    if (!state.config?.show_home_chat || !state.config?.enable_chat_widget || !isHomeRoute()) {
      removeHomeCard();
      return;
    }
    if (document.getElementById("huf-home-chat-card")) return;
    const target = findHomeTarget();
    if (!target) return;
    const rtl = isArabic(state.config);
    const prompts = state.config?.suggested_prompts?.length ? state.config.suggested_prompts : DEFAULT_PROMPTS;
    const card = document.createElement("section");
    card.id = "huf-home-chat-card";
    card.dir = rtl ? "rtl" : "ltr";
    card.innerHTML = `
      <div class="huf-home-card-head">
        <span class="huf-home-card-icon" aria-hidden="true">AI</span>
        <div>
          <strong>${escapeHtml(label("title", "مساعد HUF الذكي"))}</strong>
          <p>${escapeHtml(label("subtitle", "اسأل عن المبيعات، المخزون، الفواتير، العملاء، أو المهام"))}</p>
        </div>
      </div>
      <div class="huf-home-card-composer">
        <textarea rows="2" data-home-input placeholder="${escapeAttr(label("placeholder", rtl ? "اكتب سؤالك هنا…" : "Ask HUF Assistant…"))}"></textarea>
        <button type="button" data-home-send>${escapeHtml(label("send", "إرسال"))}</button>
      </div>
      <div class="huf-home-card-prompts">
        ${prompts.map((prompt) => `<button type="button" data-home-prompt="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("")}
      </div>
    `;
    target.prepend(card);
    card.addEventListener("click", (event) => {
      const prompt = event.target.closest("[data-home-prompt]");
      if (prompt) {
        setOpen(root, true);
        send(root, prompt.dataset.homePrompt);
        return;
      }
      if (event.target.closest("[data-home-send]")) {
        const input = card.querySelector("[data-home-input]");
        setOpen(root, true);
        send(root, input.value);
        input.value = "";
      }
    });
    const input = card.querySelector("[data-home-input]");
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = `${Math.min(input.scrollHeight, 116)}px`;
      card.querySelector("[data-home-send]").disabled = !input.value.trim();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        setOpen(root, true);
        send(root, input.value);
        input.value = "";
        input.style.height = "";
      }
    });
    card.querySelector("[data-home-send]").disabled = true;
  }

  function watchHomeCard(root) {
    ensureHomeCard(root);
    if (state.routeWatcher) window.clearInterval(state.routeWatcher);
    let lastPath = `${location.pathname}${location.hash}`;
    state.routeWatcher = window.setInterval(() => {
      const current = `${location.pathname}${location.hash}`;
      if (current !== lastPath) {
        lastPath = current;
        window.setTimeout(() => ensureHomeCard(root), 250);
      }
    }, 8000);
    window.addEventListener("hashchange", () => window.setTimeout(() => ensureHomeCard(root), 250));
    window.addEventListener("popstate", () => window.setTimeout(() => ensureHomeCard(root), 250));
  }

  async function init() {
    if (!isDesk() || document.getElementById(WIDGET_ID) || !window.frappe) return;
    try {
      state.config = await call("get_ui_config", {});
      state.selectedAgent = state.config?.default_agent || null;
    } catch (err) {
      console.warn("HUF chat config unavailable", err);
      return;
    }
    if (!state.config?.enabled && !state.config?.enable_chat_widget) return;
    if (!state.config?.enable_chat_widget) return;
    const root = renderShell(state.config);
    bind(root);
    watchHomeCard(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
