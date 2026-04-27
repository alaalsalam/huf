(function () {
  const WIDGET_ID = "trilogy-ai-desk-widget";
  const BRIDGE_METHOD = "huf.ai.trilogy_erp_analytics.analyze_erp_question";

  const QUICK_COMMANDS = [
    {
      group: "مالي",
      items: [
        "اعرض ملخص الحسابات المدينة حسب أعلى العملاء",
        "ما إجمالي فواتير المبيعات غير المدفوعة؟",
        "حلل الفواتير المتأخرة وحدد أولويات التحصيل",
      ],
    },
    {
      group: "مبيعات",
      items: [
        "اعرض أعلى 10 عملاء حسب قيمة المبيعات",
        "حلل أوامر البيع المفتوحة",
        "ما العملاء الذين يحتاجون متابعة عاجلة؟",
      ],
    },
    {
      group: "مخزون",
      items: [
        "اعرض أكثر الأصناف حركة",
        "حلل وضع المخزون حسب الأصناف المهمة",
        "ما الأصناف التي تحتاج مراجعة توفر؟",
      ],
    },
    {
      group: "تنفيذي",
      items: [
        "اعطني لوحة تنفيذية مختصرة عن المبيعات والمالية",
        "استخرج أهم 5 مؤشرات تحتاج انتباه الإدارة",
        "اقترح قرارات تشغيلية بناء على بيانات النظام",
      ],
    },
  ];

  function isDeskPage() {
    return window.location.pathname.startsWith("/app");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function call(method, args) {
    return new Promise((resolve, reject) => {
      if (!window.frappe || !window.frappe.call) {
        reject(new Error("Frappe API is not available."));
        return;
      }
      window.frappe.call({
        method,
        args,
        callback: (r) => resolve(r.message),
        error: reject,
      });
    });
  }

  function firstNumber(payload) {
    const row = Array.isArray(payload?.result) ? payload.result[0] : null;
    if (!row || typeof row !== "object") return "";
    const value = Object.values(row).find((item) => typeof item === "number" || /^\d+(\.\d+)?$/.test(String(item)));
    return value === undefined ? "" : String(value);
  }

  function renderResultTable(result) {
    if (!Array.isArray(result) || !result.length || typeof result[0] !== "object") return "";
    const columns = Object.keys(result[0]).slice(0, 5);
    const rows = result.slice(0, 8);
    return `
      <div class="trilogy-result-table-wrap">
        <table class="trilogy-result-table">
          <thead>
            <tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr>${columns.map((col) => `<td>${escapeHtml(row[col])}</td>`).join("")}</tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderAnswer(root, payload) {
    const answer = root.querySelector("[data-trilogy-answer]");
    if (!answer) return;

    if (!payload) {
      answer.innerHTML = "";
      return;
    }

    const metric = firstNumber(payload);
    const ok = payload.ok && !payload.error;
    const answerText = payload.answer || payload.error || "لم ترجع نتيجة واضحة.";
    const table = renderResultTable(payload.result);
    const sql = payload.sql ? escapeHtml(payload.sql) : "";

    answer.innerHTML = `
      <div class="trilogy-result-head">
        <span class="trilogy-result-state ${ok ? "ok" : "warn"}">${ok ? "جاهز" : "مراجعة"}</span>
        ${metric ? `<strong>${escapeHtml(metric)}</strong>` : ""}
      </div>
      <div class="trilogy-result-answer">${escapeHtml(answerText)}</div>
      ${table}
      <div class="trilogy-result-actions">
        <button type="button" data-copy-answer>نسخ النتيجة</button>
        <a href="/huf/chat" target="_blank" rel="noopener">فتح الوكلاء</a>
      </div>
      ${sql ? `
        <details class="trilogy-sql-details">
          <summary>تفاصيل التحليل</summary>
          <pre>${sql}</pre>
        </details>
      ` : ""}
    `;

    const copyBtn = answer.querySelector("[data-copy-answer]");
    copyBtn?.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(answerText);
        setStatus(root, "تم نسخ النتيجة.", "success");
      } catch {
        setStatus(root, "تعذر النسخ من المتصفح.", "error");
      }
    });
  }

  function setStatus(root, text, type) {
    const el = root.querySelector("[data-trilogy-status]");
    if (!el) return;
    el.textContent = text || "";
    el.dataset.type = type || "idle";
  }

  function setDebug(root, payload) {
    const el = root.querySelector("[data-trilogy-debug]");
    if (!el) return;
    if (!payload) {
      el.textContent = "";
      return;
    }
    el.textContent = JSON.stringify({
      question: payload.question,
      formatted_question: payload.formatted_question,
      sql: payload.sql,
      tables: payload.tables,
      result: payload.result,
      validation: payload.validation,
      elapsed_seconds: payload.elapsed_seconds,
      error: payload.error,
    }, null, 2);
  }

  function renderCommandGroups() {
    return QUICK_COMMANDS.map((group, index) => `
      <section class="trilogy-command-group ${index === 0 ? "active" : ""}" data-command-group="${escapeHtml(group.group)}">
        <div class="trilogy-command-title">${escapeHtml(group.group)}</div>
        <div class="trilogy-command-list">
          ${group.items.map((item) => `<button type="button" data-command="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}
        </div>
      </section>
    `).join("");
  }

  function render() {
    if (!isDeskPage() || document.getElementById(WIDGET_ID)) return;

    const root = document.createElement("div");
    root.id = WIDGET_ID;
    root.dir = "rtl";
    root.innerHTML = `
      <button class="trilogy-ai-launcher" type="button" aria-label="Open TrilogyAi">
        <span>TrilogyAi</span>
      </button>
      <section class="trilogy-ai-panel" aria-label="TrilogyAi Assistant">
        <header class="trilogy-ai-header">
          <div>
            <strong>TrilogyAi</strong>
            <span>مركز التحليل الذكي</span>
          </div>
          <button class="trilogy-ai-close" type="button" aria-label="Close">×</button>
        </header>

        <div class="trilogy-ai-tabs">
          <button type="button" data-tab="analyze" class="active">تحليل</button>
          <button type="button" data-tab="agents">وكلاء</button>
          <button type="button" data-tab="debug">تفاصيل</button>
        </div>

        <div class="trilogy-ai-body">
          <div data-panel="analyze">
            <div class="trilogy-ai-hero">
              <div>
                <span>Live ERP</span>
                <strong>اسأل بيانات النظام مباشرة</strong>
              </div>
              <a href="/huf/chat" target="_blank" rel="noopener">محادثة كاملة</a>
            </div>

            <textarea data-trilogy-question rows="3" placeholder="اكتب سؤالاً تحليلياً عن المبيعات، الفواتير، العملاء، المخزون..."></textarea>

            <div class="trilogy-command-tabs">
              ${QUICK_COMMANDS.map((group, index) => `
                <button type="button" class="${index === 0 ? "active" : ""}" data-command-tab="${escapeHtml(group.group)}">${escapeHtml(group.group)}</button>
              `).join("")}
            </div>

            <div class="trilogy-command-groups">
              ${renderCommandGroups()}
            </div>

            <button class="trilogy-ai-run" type="button">
              <span>تشغيل التحليل</span>
            </button>
            <div data-trilogy-status class="trilogy-ai-status"></div>
            <div data-trilogy-answer class="trilogy-ai-answer"></div>
          </div>

          <div data-panel="agents" hidden>
            <div class="trilogy-agent-links">
              <a href="/huf/chat" target="_blank" rel="noopener"><strong>محادثات TrilogyAi</strong><span>استخدم الوكلاء المتخصصين</span></a>
              <a href="/huf/agents" target="_blank" rel="noopener"><strong>إدارة الوكلاء</strong><span>تعديل الأدوار والأدوات</span></a>
              <a href="/huf" target="_blank" rel="noopener"><strong>لوحة التحكم</strong><span>الانتقال إلى منصة TrilogyAi</span></a>
            </div>
          </div>

          <div data-panel="debug" hidden>
            <pre data-trilogy-debug></pre>
          </div>
        </div>
      </section>
    `;

    document.body.appendChild(root);

    const launcher = root.querySelector(".trilogy-ai-launcher");
    const close = root.querySelector(".trilogy-ai-close");
    const question = root.querySelector("[data-trilogy-question]");

    launcher.addEventListener("click", () => {
      root.classList.toggle("open");
      if (root.classList.contains("open")) setTimeout(() => question.focus(), 50);
    });
    close.addEventListener("click", () => root.classList.remove("open"));

    root.querySelectorAll("[data-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        root.querySelectorAll("[data-tab]").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        root.querySelectorAll("[data-panel]").forEach((panel) => {
          panel.hidden = panel.dataset.panel !== tab.dataset.tab;
        });
      });
    });

    root.querySelectorAll("[data-command-tab]").forEach((tab) => {
      tab.addEventListener("click", () => {
        root.querySelectorAll("[data-command-tab]").forEach((item) => item.classList.remove("active"));
        root.querySelectorAll("[data-command-group]").forEach((group) => {
          group.classList.toggle("active", group.dataset.commandGroup === tab.dataset.commandTab);
        });
        tab.classList.add("active");
      });
    });

    root.querySelectorAll("[data-command]").forEach((btn) => {
      btn.addEventListener("click", () => {
        question.value = btn.dataset.command || "";
        question.focus();
      });
    });

    root.querySelector(".trilogy-ai-run").addEventListener("click", async () => {
      const text = question.value.trim();
      if (!text) {
        setStatus(root, "اكتب السؤال أولاً.", "error");
        return;
      }
      renderAnswer(root, null);
      setDebug(root, null);
      root.classList.add("is-loading");
      setStatus(root, "جاري قراءة البيانات وبناء التحليل...", "loading");
      try {
        const payload = await call(BRIDGE_METHOD, { question: text });
        renderAnswer(root, payload);
        setDebug(root, payload);
        setStatus(root, payload && payload.ok ? "اكتمل التحليل." : "تحتاج النتيجة مراجعة.", payload && payload.ok ? "success" : "error");
      } catch (err) {
        renderAnswer(root, { ok: false, error: "تعذر الاتصال بمحرك التحليل." });
        setStatus(root, err?.message || "حدث خطأ أثناء التحليل.", "error");
      } finally {
        root.classList.remove("is-loading");
      }
    });

    root.querySelector(".trilogy-ai-panel").addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        root.querySelector(".trilogy-ai-run").click();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();

