frappe.pages["huf-chat"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Trilogy Assistant",
    single_column: true,
  });

  const API = "huf.api.chat";
  const DEFAULT_PROMPTS = [
    "اعرض مبيعات هذا الشهر",
    "لخص حالة المخزون",
    "ما الفواتير المتأخرة؟",
    "أنشئ مهمة متابعة للعميل",
    "اقترح تحسينات على التدفق النقدي",
  ];
  const PROMPT_GROUPS = [
    { key: "sales", label: "المبيعات", prompts: ["اعرض مبيعات هذا الشهر", "من هم أفضل العملاء هذا الشهر؟", "قارن مبيعات هذا الشهر بالشهر السابق"] },
    { key: "inventory", label: "المخزون", prompts: ["لخص حالة المخزون", "ما الأصناف منخفضة الكمية؟", "اعرض أعلى الأصناف حسب قيمة المخزون"] },
    { key: "receivables", label: "المستحقات", prompts: ["ما الفواتير المتأخرة؟", "اعرض العملاء الأعلى مديونية", "ما الفواتير المستحقة هذا الأسبوع؟"] },
    { key: "tasks", label: "المهام", prompts: ["أنشئ مهمة متابعة للعميل", "لخص المهام المفتوحة", "ما المهام المتأخرة؟"] },
    { key: "general", label: "عام", prompts: ["ماذا أستطيع أن أسأل؟", "ساعدني في تحليل أداء الشركة اليوم"] },
  ];

  const state = {
    config: {},
    sessions: [],
    sessionId: null,
    sending: false,
    lastAssistantMeta: null,
    lastFailedText: "",
    selectedAgent: null,
    showAllSuggestions: false,
  };

  const $root = $(page.body).addClass("huf-chat-workspace-page");

  function call(method, args) {
    return new Promise((resolve, reject) => {
      frappe.call({
        method: `${API}.${method}`,
        args: args || {},
        freeze: false,
        callback: (r) => resolve(r.message || {}),
        error: reject,
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

  function label(key, fallback) {
    return state.config?.labels?.[key] || fallback;
  }

  function agentOptions(config) {
    const agents = Array.isArray(config?.agents) ? config.agents : [];
    const selected = state.selectedAgent || config?.default_agent || "";
    return agents.map((agent) => `<option value="${escapeAttr(agent.name)}" ${agent.name === selected || (!selected && agent.is_default) ? "selected" : ""}>${escapeHtml(agent.title || agent.name)}</option>`).join("");
  }

  function selectedAgentArg() {
    return state.selectedAgent ? { agent: state.selectedAgent } : {};
  }

  function allSuggestedPrompts() {
    const fromConfig = state.config?.suggested_prompt_groups;
    if (Array.isArray(fromConfig) && fromConfig.length) return fromConfig;
    return PROMPT_GROUPS;
  }

  function flatSuggestedPrompts() {
    return allSuggestedPrompts().flatMap((group) => Array.isArray(group.prompts) ? group.prompts : []);
  }

  function selectedAgentInfo() {
    const agents = Array.isArray(state.config?.agents) ? state.config.agents : [];
    return agents.find((agent) => agent.name === state.selectedAgent) || agents.find((agent) => agent.is_default) || null;
  }

  function agentDescription() {
    const agent = selectedAgentInfo();
    return agent?.description || label("agent_default_description", "مساعد عام لأسئلة ERPNext اليومية");
  }

  function renderPromptButtons(expanded) {
    const prompts = flatSuggestedPrompts();
    if (!expanded) {
      return prompts.slice(0, 8).map((prompt) => `<button type="button" data-prompt="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("");
    }
    return allSuggestedPrompts().map((group) => `
      <div class="huf-page-suggestion-group">
        <span>${escapeHtml(group.label || "")}</span>
        <div>${(group.prompts || []).map((prompt) => `<button type="button" data-prompt="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("")}</div>
      </div>
    `).join("");
  }

  function renderSuggestionArea() {
    const prompts = flatSuggestedPrompts();
    return `
      <div class="huf-page-suggestions ${state.showAllSuggestions ? "expanded" : ""}">
        ${renderPromptButtons(state.showAllSuggestions)}
      </div>
      ${prompts.length > 8 ? `<button type="button" class="huf-page-more-prompts" data-more-prompts>${escapeHtml(state.showAllSuggestions ? label("less_prompts", "عرض أقل") : label("more_prompts", "عرض المزيد"))}</button>` : ""}
    `;
  }

  function inlineMarkdown(text) {
    return escapeHtml(text)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, title, url) => `<a href="${safeUrl(url)}" target="_blank" rel="noopener noreferrer">${title}</a>`);
  }

  function cleanSuggestedPrompt(line) {
    return String(line || "")
      .replace(/^\s*[-*]\s+/, "")
      .replace(/^\s*\d+\.\s+/, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function isSuggestionHeading(block) {
    const text = String(block || "").toLowerCase();
    return /اقتراح|جرّب|جرب|اختر|متابعة|أسئلة|اسئلة|try|next|suggest/.test(text);
  }

  function renderSuggestedPrompts(lines) {
    const prompts = lines.map(cleanSuggestedPrompt).filter(Boolean).slice(0, 6);
    if (!prompts.length) return "";
    return `<div class="huf-page-followups" aria-label="أسئلة مقترحة">
      ${prompts.map((prompt) => `
        <div class="huf-page-followup">
          <button type="button" class="huf-page-followup-send" data-suggested-prompt="${escapeAttr(prompt)}">${inlineMarkdown(prompt)}</button>
          <button type="button" class="huf-page-followup-edit" data-edit-prompt="${escapeAttr(prompt)}" title="تعديل السؤال">تعديل</button>
        </div>
      `).join("")}
    </div>`;
  }

  function renderTable(lines) {
    const rows = lines
      .filter((line) => line.includes("|"))
      .map((line) => line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => inlineMarkdown(cell.trim())));
    if (rows.length < 2) return "";
    const header = rows[0];
    const body = rows.slice(2).length ? rows.slice(2) : rows.slice(1);
    return `<div class="huf-page-table-wrap"><table><thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead><tbody>${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  }

  function renderMarkdownBlock(block, previousBlock) {
    const lines = block.split("\n");
    if (lines.length > 1 && lines[0].includes("|") && lines[1].includes("|")) {
      return renderTable(lines);
    }
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      if (isSuggestionHeading(previousBlock)) return renderSuggestedPrompts(lines);
      return `<ul>${lines.map((line) => `<li>${inlineMarkdown(line.replace(/^\s*[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    }
    if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
      if (isSuggestionHeading(previousBlock)) return renderSuggestedPrompts(lines);
      return `<ol>${lines.map((line) => `<li>${inlineMarkdown(line.replace(/^\s*\d+\.\s+/, ""))}</li>`).join("")}</ol>`;
    }
    return `<p>${lines.map(inlineMarkdown).join("<br>")}</p>`;
  }

  function renderMarkdown(text) {
    const html = [];
    String(text || "").split(/(```[\s\S]*?```)/g).forEach((part) => {
      if (!part) return;
      if (part.startsWith("```")) {
        html.push(`<pre><code>${escapeHtml(part.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/```$/, ""))}</code></pre>`);
        return;
      }
      let previousBlock = "";
      part.split(/\n{2,}/).forEach((block) => {
        const clean = block.trim();
        if (clean) {
          html.push(renderMarkdownBlock(clean, previousBlock));
          previousBlock = clean;
        }
      });
    });
    return html.join("") || "<p></p>";
  }

  function messageDir(text) {
    return /[\u0600-\u06FF]/.test(String(text || "")) ? "rtl" : "ltr";
  }

  function autoGrow(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 156)}px`;
  }

  function setSending(sending) {
    state.sending = sending;
    $root.toggleClass("is-sending", sending);
    const value = $root.find("[data-composer]").val() || "";
    $root.find("[data-send]").prop("disabled", sending || !value.trim());
  }

  function emptyState() {
    return `
      <section class="huf-page-empty" data-empty-state>
        <div class="huf-page-empty-icon">AI</div>
        <h2>${escapeHtml(label("empty_title", "كيف أستطيع مساعدتك؟"))}</h2>
        <p>${escapeHtml(label("empty_text", "اسألني عن بيانات ERPNext أو اطلب تلخيصًا أو إجراءً آمنًا."))}</p>
        ${renderSuggestionArea()}
      </section>
    `;
  }

  function ensureEmptyState() {
    const list = $root.find("[data-message-list]");
    if (!list.find(".huf-page-msg").length && !list.find("[data-empty-state]").length) {
      list.html(emptyState());
    }
  }

  function clearEmptyState() {
    $root.find("[data-empty-state]").remove();
  }

  function addMessage(role, text, meta) {
    clearEmptyState();
    const normalizedRole = role === "agent" ? "assistant" : role;
    const messageId = meta?.message_id || meta?.name || "";
    const feedback = normalizedRole === "assistant" && messageId ? `
      <div class="huf-page-feedback">
        <button type="button" title="مفيد" data-feedback="Positive">👍</button>
        <button type="button" title="غير مفيد" data-feedback="Negative">👎</button>
        ${meta?.debug_available ? `<button type="button" data-debug-trigger>${escapeHtml(label("show_details", "إظهار التفاصيل"))}</button>` : ""}
        <span data-feedback-note hidden>${escapeHtml(label("feedback_saved", "تم تسجيل ملاحظتك"))}</span>
      </div>` : "";
    const html = `
      <article class="huf-page-msg ${escapeAttr(normalizedRole)}" data-message-id="${escapeAttr(messageId)}">
        <div class="huf-page-bubble" dir="${messageDir(text)}">
          <div class="huf-page-content">${renderMarkdown(text)}</div>
          ${feedback}
        </div>
      </article>
    `;
    $root.find("[data-message-list]").append(html);
    const list = $root.find("[data-message-list]").get(0);
    if (list) list.scrollTop = list.scrollHeight;
  }

  function addTyping() {
    clearEmptyState();
    $root.find("[data-message-list]").append(`
      <article class="huf-page-msg assistant" data-typing="1">
        <div class="huf-page-bubble typing">
          <span>${escapeHtml(label("thinking", "جاري التفكير..."))}</span>
          <span class="huf-page-dots"><i></i><i></i><i></i></span>
        </div>
      </article>
    `);
    const list = $root.find("[data-message-list]").get(0);
    if (list) list.scrollTop = list.scrollHeight;
  }

  function removeTyping() {
    $root.find("[data-typing]").remove();
  }

  function showError() {
    addMessage("assistant", label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول."));
    if (state.lastFailedText) {
      $root.find(".huf-page-msg:last .huf-page-bubble").append(`<button type="button" class="huf-page-retry" data-retry>${escapeHtml(label("retry", "إعادة المحاولة"))}</button>`);
    }
  }

  function formatActivity(value) {
    if (!value) return "";
    try {
      return frappe.datetime.comment_when(value);
    } catch {
      return value;
    }
  }

  function renderSessions() {
    const filter = String($root.find("[data-session-filter]").val() || "").trim().toLowerCase();
    const rows = state.sessions.filter((session) => !filter || String(session.title || session.name).toLowerCase().includes(filter));
    const html = rows.map((session) => `
      <button type="button" class="huf-page-session ${session.name === state.sessionId ? "active" : ""}" data-session="${escapeAttr(session.name)}">
        <strong>${escapeHtml(session.title || session.name)}</strong>
        <span>${escapeHtml(formatActivity(session.last_activity || session.creation))}</span>
      </button>
    `).join("");
    $root.find("[data-session-list]").html(html || `<div class="huf-page-sidebar-empty">لا توجد محادثات مطابقة.</div>`);
  }

  async function refreshSessions() {
    try {
      const res = await call("get_sessions", { limit: 50 });
      state.sessions = res.sessions || [];
      renderSessions();
    } catch (err) {
      console.error(err);
      frappe.show_alert({ message: __("Unable to load Trilogy sessions"), indicator: "red" });
    }
  }

  async function loadSession(sessionId) {
    state.sessionId = sessionId;
    renderSessions();
    $root.find("[data-message-list]").empty();
    try {
      const res = await call("get_messages", { session_id: sessionId, limit: 120 });
      (res.messages || []).forEach((msg) => addMessage(msg.role === "agent" ? "assistant" : msg.role, msg.content, {
        name: msg.name,
        message_id: msg.name,
        debug_available: res.debug_available,
      }));
      ensureEmptyState();
    } catch (err) {
      console.error(err);
      showError();
    }
  }

  async function newSession() {
    try {
      const res = await call("new_session", { title: state.config?.default_title || "Trilogy Assistant", ...selectedAgentArg() });
      state.sessionId = res.session_id || res.name;
      $root.find("[data-message-list]").empty();
      ensureEmptyState();
      await refreshSessions();
      $root.find("[data-composer]").trigger("focus");
    } catch (err) {
      console.error(err);
      showError();
    }
  }

  async function deleteCurrentSession() {
    if (!state.sessionId) return;
    const ok = await new Promise((resolve) => {
      frappe.confirm("هل تريد حذف هذه المحادثة من القائمة؟", () => resolve(true), () => resolve(false));
    });
    if (!ok) return;
    try {
      await call("delete_session", { session_id: state.sessionId });
      state.sessionId = null;
      $root.find("[data-message-list]").empty();
      ensureEmptyState();
      await refreshSessions();
    } catch (err) {
      console.error(err);
      frappe.show_alert({ message: __("Unable to delete session"), indicator: "red" });
    }
  }

  async function send(text) {
    const clean = String(text || "").trim();
    if (!clean || state.sending) return;
    state.lastFailedText = clean;
    addMessage("user", clean);
    const composer = $root.find("[data-composer]").get(0);
    composer.value = "";
    autoGrow(composer);
    setSending(true);
    addTyping();
    try {
      const res = await call("send_message", { message: clean, session_id: state.sessionId, ...selectedAgentArg() });
      state.sessionId = res.session_id || state.sessionId;
      state.lastAssistantMeta = res;
      removeTyping();
      addMessage("assistant", res.content || "لم يصل رد واضح.", res);
      if (res.requires_confirmation) {
        addMessage("assistant", `يتطلب هذا الطلب تأكيدًا قبل التنفيذ: ${res.confirmation?.summary || "إجراء حساس"}`, res);
      }
      state.lastFailedText = "";
      await refreshSessions();
    } catch (err) {
      console.error(err);
      removeTyping();
      showError();
    } finally {
      setSending(false);
      composer.focus();
    }
  }

  async function submitFeedback(button) {
    const messageId = $(button).closest("[data-message-id]").data("message-id");
    if (!messageId) return;
    const rating = button.dataset.feedback;
    const comment = rating === "Negative" ? window.prompt("ما الذي يمكن تحسينه؟") || "" : "";
    button.disabled = true;
    try {
      await call("submit_feedback", { message_id: messageId, rating, comment });
      $(button).siblings("[data-feedback-note]").prop("hidden", false);
    } catch (err) {
      console.error(err);
      button.disabled = false;
      frappe.show_alert({ message: label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول."), indicator: "red" });
    }
  }

  async function loadDebug() {
    if (!state.config?.debug_available) return;
    const $panel = $root.find("[data-debug-panel]");
    $panel.prop("hidden", !$panel.prop("hidden"));
    if ($panel.prop("hidden")) return;
    $root.find("[data-debug-output]").text(label("loading", "جاري التحميل..."));
    try {
      const res = await call("get_debug_trace", {
        session_id: state.sessionId,
        run_id: state.lastAssistantMeta?.metadata?.run_id,
      });
      $root.find("[data-debug-output]").text(JSON.stringify(res, null, 2));
    } catch (err) {
      console.error(err);
      $root.find("[data-debug-output]").text(label("error", "تعذر الحصول على رد الآن. حاول مرة أخرى أو تواصل مع المسؤول."));
    }
  }

  function render() {
    const rtl = state.config?.rtl || String(state.config?.language || frappe.boot.lang || "").startsWith("ar");
    page.set_title(label("title", "مساعد Trilogy الذكي"));
    $root.html(`
      <div class="huf-page-shell" dir="${rtl ? "rtl" : "ltr"}">
        <aside class="huf-page-sidebar">
          <button type="button" class="huf-page-new" data-new-chat>${escapeHtml(label("new_chat", "محادثة جديدة"))}</button>
          <div class="huf-page-search">
            <input type="search" data-session-filter placeholder="بحث في المحادثات">
          </div>
          <div class="huf-page-session-list" data-session-list></div>
        </aside>
        <main class="huf-page-main">
          <header class="huf-page-header">
            <div>
              <strong>${escapeHtml(label("title", "مساعد Trilogy الذكي"))}</strong>
              <span>${escapeHtml(label("subtitle", "اسأل عن المبيعات، المخزون، الفواتير، أو المهام"))}</span>
            </div>
            <div class="huf-page-header-actions">
              ${state.config?.can_select_agent || state.config?.can_select_model ? `<details><summary>${escapeHtml(label("advanced", "خيارات متقدمة"))}</summary><p>${escapeHtml(label("advanced_hint", "سيتم استخدام الوكيل والنموذج الافتراضيين ما لم يتم تحديد غير ذلك من الإعدادات."))}</p></details>` : ""}
              ${state.config?.debug_available ? `<button type="button" data-debug-trigger>${escapeHtml(label("show_details", "إظهار التفاصيل"))}</button>` : ""}
              <button type="button" data-delete-session>${escapeHtml(label("clear", "مسح"))}</button>
            </div>
          </header>
          ${state.config?.can_select_agent && Array.isArray(state.config.agents) && state.config.agents.length ? `
            <section class="huf-page-agent-strip">
              <div class="huf-page-agent-copy">
                <label>${escapeHtml(label("agent", "الوكيل"))}</label>
                <small data-agent-description>${escapeHtml(agentDescription())}</small>
              </div>
              <select data-agent-selector aria-label="${escapeAttr(label("agent", "الوكيل"))}">
                ${agentOptions(state.config)}
              </select>
            </section>` : ""}
          <section class="huf-page-message-list" data-message-list></section>
          <footer class="huf-page-composer">
            <div class="huf-page-composer-row">
              <textarea rows="1" data-composer placeholder="${escapeAttr(label("placeholder", rtl ? "اكتب سؤالك هنا…" : "Ask Trilogy Assistant…"))}"></textarea>
              <button type="button" data-send disabled>${escapeHtml(label("send", "إرسال"))}</button>
            </div>
            <div class="huf-page-composer-hint">${escapeHtml(label("composer_hint", "مثال: اعرض مبيعات هذا الشهر أو لخص حالة المخزون"))}</div>
          </footer>
        </main>
        <aside class="huf-page-debug" data-debug-panel hidden>
          <div class="huf-page-debug-head">${escapeHtml(label("details", "التفاصيل"))}</div>
          <pre data-debug-output></pre>
        </aside>
      </div>
    `);
    ensureEmptyState();
  }

  function bind() {
    const $agentSelector = $root.find("[data-agent-selector]");
    if ($agentSelector.length) {
      state.selectedAgent = $agentSelector.val() || state.config?.default_agent || null;
      $root.on("change", "[data-agent-selector]", function () {
        state.selectedAgent = this.value || null;
        state.sessionId = null;
        state.lastAssistantMeta = null;
        $root.find("[data-message-list]").empty();
        $root.find("[data-agent-description]").text(agentDescription());
        ensureEmptyState();
        renderSessions();
        $root.find("[data-composer]").trigger("focus");
        frappe.show_alert?.({ message: `${label("agent_changed", "تم بدء محادثة جديدة مع")} ${this.options[this.selectedIndex]?.text || ""}`, indicator: "blue" }, 4);
      });
    } else {
      state.selectedAgent = state.config?.default_agent || null;
    }
    $root.on("click", "[data-new-chat]", () => newSession());
    $root.on("click", "[data-session]", function () {
      loadSession(this.dataset.session);
    });
    $root.on("input", "[data-session-filter]", renderSessions);
    $root.on("click", "[data-delete-session]", deleteCurrentSession);
    $root.on("click", "[data-send]", () => send($root.find("[data-composer]").val()));
    $root.on("click", "[data-prompt]", function () {
      send(this.dataset.prompt);
    });
    $root.on("click", "[data-more-prompts]", function () {
      state.showAllSuggestions = !state.showAllSuggestions;
      $root.find("[data-empty-state]").replaceWith(emptyState());
    });
    $root.on("click", "[data-suggested-prompt]", function () {
      send(this.dataset.suggestedPrompt);
    });
    $root.on("click", "[data-edit-prompt]", function () {
      const composer = $root.find("[data-composer]").get(0);
      composer.value = this.dataset.editPrompt || "";
      autoGrow(composer);
      setSending(state.sending);
      composer.focus();
    });
    $root.on("click", "[data-retry]", () => send(state.lastFailedText));
    $root.on("click", "[data-feedback]", function () {
      submitFeedback(this);
    });
    $root.on("click", "[data-debug-trigger]", loadDebug);
    $root.on("input", "[data-composer]", function () {
      autoGrow(this);
      setSending(state.sending);
    });
    $root.on("keydown", "[data-composer]", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send(this.value);
      }
    });
  }

  function injectStyles() {
    if (document.getElementById("huf-chat-page-polish-style")) return;
    $("<style id='huf-chat-page-polish-style'>").text(`
      .huf-chat-workspace-page{font-family:inherit;--huf-chat-bg:#f6f8fb;--huf-chat-surface:#fff;--huf-chat-border:#dce4ef;--huf-chat-text:#172033;--huf-chat-muted:#66758c;--huf-chat-primary:#1f6feb;--huf-chat-primary-soft:#eaf2ff;--huf-chat-radius:14px;--huf-chat-shadow:0 20px 60px rgba(21,32,52,.14);color:var(--huf-chat-text)}
      .huf-chat-workspace-page *,.huf-chat-workspace-page button,.huf-chat-workspace-page input,.huf-chat-workspace-page textarea,.huf-chat-workspace-page select{font-family:inherit!important}.huf-page-shell{display:grid;grid-template-columns:280px minmax(0,1fr) 340px;gap:14px;height:calc(100vh - 134px);min-height:560px}
      .huf-page-sidebar,.huf-page-main,.huf-page-debug{overflow:hidden;border:1px solid var(--huf-chat-border);border-radius:var(--huf-chat-radius);background:var(--huf-chat-surface);box-shadow:0 1px 2px rgba(16,24,40,.03)}
      .huf-page-sidebar{display:flex;flex-direction:column;padding:12px}.huf-page-new{height:38px;border:0;border-radius:10px;background:var(--huf-chat-primary);color:#fff;font-weight:800}.huf-page-search{margin:10px 0}.huf-page-search input{width:100%;height:36px;border:1px solid var(--huf-chat-border);border-radius:10px;padding:0 10px}
      .huf-page-session-list{overflow:auto}.huf-page-session{display:block;width:100%;margin:0 0 8px;border:1px solid var(--huf-chat-border);border-radius:11px;background:#fff;padding:10px;text-align:inherit;cursor:pointer}.huf-page-session.active{border-color:#aac5fa;background:var(--huf-chat-primary-soft)}.huf-page-session strong,.huf-page-session span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.huf-page-session strong{font-size:13px}.huf-page-session span,.huf-page-sidebar-empty{margin-top:4px;color:var(--huf-chat-muted);font-size:11px}
      .huf-page-main{display:flex;flex-direction:column}.huf-page-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border-bottom:1px solid var(--huf-chat-border)}.huf-page-header strong,.huf-page-header span{display:block}.huf-page-header strong{font-size:16px}.huf-page-header span{margin-top:3px;color:var(--huf-chat-muted);font-size:12px}.huf-page-header-actions{display:flex;align-items:center;gap:8px}.huf-page-header-actions button,.huf-page-header-actions summary{border:1px solid var(--huf-chat-border);border-radius:9px;background:#fff;color:#42516a;cursor:pointer;padding:7px 10px;font-size:12px;font-weight:800}.huf-page-header-actions details{position:relative}.huf-page-header-actions details p{position:absolute;z-index:4;inset-inline-end:0;width:260px;margin:8px 0 0;border:1px solid var(--huf-chat-border);border-radius:10px;background:#fff;padding:10px;color:var(--huf-chat-muted);font-size:12px;box-shadow:var(--huf-chat-shadow)}
      .huf-page-agent-strip{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 16px;border-bottom:1px solid var(--huf-chat-border);background:#fbfdff}.huf-page-agent-copy{display:grid;gap:2px;min-width:0}.huf-page-agent-strip label{margin:0;color:var(--huf-chat-muted);font-size:12px;font-weight:800}.huf-page-agent-copy small{color:var(--huf-chat-text);font-size:11px;line-height:1.35;opacity:.78}.huf-page-agent-strip select{min-width:190px;height:34px;border:1px solid var(--huf-chat-border);border-radius:9px;background:#fff;color:var(--huf-chat-text);padding:0 10px;font-size:12px;font-weight:700}
      .huf-page-message-list{flex:1;overflow:auto;padding:20px;background:var(--huf-chat-bg)}.huf-page-empty{display:grid;align-content:center;min-height:100%;text-align:center}.huf-page-empty-icon{display:grid;place-items:center;width:64px;height:64px;margin:0 auto 14px;border-radius:20px;background:var(--huf-chat-primary-soft);color:var(--huf-chat-primary);font-weight:900}.huf-page-empty h2{margin:0;font-size:24px}.huf-page-empty p{max-width:420px;margin:10px auto 18px;color:var(--huf-chat-muted);line-height:1.8}.huf-page-suggestions{display:flex;flex-wrap:wrap;justify-content:center;gap:8px}.huf-page-suggestions.expanded{display:grid;gap:10px;max-width:760px;margin:0 auto}.huf-page-suggestion-group{display:grid;gap:6px}.huf-page-suggestion-group>span{color:var(--huf-chat-muted);font-size:11px;font-weight:800}.huf-page-suggestion-group>div{display:flex;flex-wrap:wrap;justify-content:center;gap:7px}.huf-page-suggestions button{border:1px solid var(--huf-chat-border);border-radius:999px;background:#fff;color:#27354d;cursor:pointer;padding:8px 12px;font-size:12px}.huf-page-more-prompts{margin-top:10px;border:0;background:transparent;color:var(--huf-chat-primary);font-size:12px;font-weight:800;cursor:pointer}
      .huf-page-msg{display:flex;margin:12px 0}.huf-page-shell[dir=rtl] .huf-page-msg.user,.huf-page-shell[dir=ltr] .huf-page-msg.assistant{justify-content:flex-start}.huf-page-shell[dir=rtl] .huf-page-msg.assistant,.huf-page-shell[dir=ltr] .huf-page-msg.user{justify-content:flex-end}.huf-page-bubble{max-width:min(760px,86%);overflow:hidden;border:1px solid var(--huf-chat-border);border-radius:15px;background:#fff;padding:12px 14px;box-shadow:0 4px 16px rgba(16,24,40,.04);font-size:13px;line-height:1.75}.huf-page-msg.user .huf-page-bubble{border-color:#c4d8ff;background:var(--huf-chat-primary);color:#fff}.huf-page-content p{margin:0 0 9px}.huf-page-content p:last-child,.huf-page-content ul:last-child,.huf-page-content ol:last-child{margin-bottom:0}.huf-page-content ul,.huf-page-content ol{margin:0 0 10px;padding-inline-start:20px}.huf-page-content a{color:var(--huf-chat-primary);font-weight:700;text-decoration:none}.huf-page-content code{border-radius:5px;background:rgba(15,23,42,.07);padding:1px 5px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}.huf-page-content pre{overflow:auto;border-radius:10px;background:#101828;color:#fff;padding:10px;direction:ltr;text-align:left}
      .huf-page-table-wrap{max-width:100%;overflow-x:auto;margin:8px 0;border:1px solid var(--huf-chat-border);border-radius:10px;background:#fff}.huf-page-table-wrap table{width:100%;min-width:460px;border-collapse:collapse;font-size:12px}.huf-page-table-wrap th,.huf-page-table-wrap td{border-bottom:1px solid var(--huf-chat-border);padding:8px 9px;text-align:inherit;white-space:nowrap}.huf-page-table-wrap th{background:#f8fafc;color:#4b5870;font-weight:800}
      .huf-page-feedback{display:flex;align-items:center;gap:6px;margin-top:8px}.huf-page-feedback button,.huf-page-retry{border:1px solid var(--huf-chat-border);border-radius:8px;background:#fff;color:#48566d;cursor:pointer;padding:5px 8px;font-size:11px}.huf-page-feedback span{color:#15803d;font-size:11px}.typing{display:flex;align-items:center;gap:8px;color:var(--huf-chat-muted)}.huf-page-dots{display:inline-flex;gap:3px}.huf-page-dots i{width:5px;height:5px;border-radius:999px;background:#9aa8bd;animation:hufPageTyping 1s infinite ease-in-out}.huf-page-dots i:nth-child(2){animation-delay:.14s}.huf-page-dots i:nth-child(3){animation-delay:.28s}@keyframes hufPageTyping{0%,80%,100%{opacity:.35;transform:translateY(0)}40%{opacity:1;transform:translateY(-2px)}}
      .huf-page-composer{display:flex;flex-direction:column;align-items:stretch;gap:7px;padding:13px;border-top:1px solid var(--huf-chat-border);background:#fff}.huf-page-composer-row{display:flex;align-items:flex-end;gap:10px}.huf-page-composer-hint{color:var(--huf-chat-muted);font-size:11px;line-height:1.4}.huf-page-composer textarea{flex:1;max-height:156px;min-height:44px;resize:none;border:1px solid var(--huf-chat-border);border-radius:12px;padding:11px 12px;outline:none;line-height:1.55}.huf-page-composer textarea:focus{border-color:#b9cef4;box-shadow:0 0 0 3px rgba(31,111,235,.10)}.huf-page-composer button{min-width:82px;height:44px;border:0;border-radius:12px;background:var(--huf-chat-primary);color:#fff;font-weight:800}.huf-page-composer button:disabled{opacity:.45}
      .huf-page-debug{padding:12px}.huf-page-debug[hidden]{display:none}.huf-page-debug-head{margin-bottom:8px;color:var(--huf-chat-muted);font-size:12px;font-weight:800}.huf-page-debug pre{max-height:calc(100vh - 190px);overflow:auto;white-space:pre-wrap;direction:ltr;text-align:left;font-size:11px}
      @media(max-width:1100px){.huf-page-shell{grid-template-columns:250px minmax(0,1fr)}.huf-page-debug{display:none}}@media(max-width:800px){.huf-page-shell{grid-template-columns:1fr;height:calc(100vh - 118px)}.huf-page-sidebar{display:none}.huf-page-header{align-items:flex-start;flex-direction:column}.huf-page-bubble{max-width:94%}.huf-page-empty h2{font-size:21px}}
    `).appendTo(document.head);
  }

  async function init() {
    injectStyles();
    try {
      state.config = await call("get_ui_config", {});
      state.selectedAgent = state.config?.default_agent || null;
    } catch (err) {
      console.error(err);
      state.config = {
        rtl: String(frappe.boot.lang || "").startsWith("ar"),
        labels: {},
        suggested_prompts: DEFAULT_PROMPTS,
      };
      state.selectedAgent = null;
    }
    if (!state.config?.enabled && !state.config?.enable_chat_widget) {
      $root.empty();
      return;
    }
    render();
    bind();
    await refreshSessions();
    $root.find("[data-composer]").trigger("focus");
  }

  init();
};
