(function () {
  const WIDGET_ID = "huf-enhanced-chat-widget";
  const API = "huf.api.chat";
  const prompts = ["اعرض مبيعات هذا الشهر في جدول مختصر", "ما الفواتير المتأخرة؟ رتبها حسب الأولوية", "لخص حالة المخزون والأصناف التي تحتاج متابعة", "اقترح تحسينات عملية على التدفق النقدي", "أنشئ مهمة متابعة للعميل بعد مراجعة بياناته"];
  let sessionId = null;
  function isDesk() { return location.pathname.startsWith("/app") && !location.pathname.includes("login"); }
  function call(method, args) { return new Promise((resolve, reject) => frappe.call({ method: `${API}.${method}`, args, callback: r => resolve(r.message), error: reject })); }
  function esc(v) { return String(v ?? "").replace(/[&<>"']/g, s => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[s])); }
  function md(text) { return esc(text).replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>"); }
  function addMsg(root, role, text, meta) {
    const list = root.querySelector("[data-chat-list]");
    const item = document.createElement("div");
    item.className = `huf-chat-msg ${role}`;
    item.innerHTML = `<div class="huf-chat-bubble"><p>${md(text)}</p>${role === "assistant" ? `<div class="huf-chat-feedback"><button type="button" data-feedback="Positive">مفيد</button><button type="button" data-feedback="Negative">غير مفيد</button>${meta?.debug_available ? `<button type="button" data-debug-button>Debug</button>` : ""}</div>` : ""}</div>`;
    list.appendChild(item);
    item.querySelectorAll("[data-feedback]").forEach(btn => btn.onclick = async () => {
      if (!meta?.message_id) return;
      btn.disabled = true;
      try { await call("submit_feedback", { message_id: meta.message_id, rating: btn.dataset.feedback }); btn.textContent = "تم"; }
      catch (e) { btn.disabled = false; console.error(e); }
    });
    list.scrollTop = list.scrollHeight;
  }
  function setBusy(root, busy) { root.classList.toggle("busy", !!busy); root.querySelector("[data-send]").disabled = !!busy; }
  async function send(root, text) {
    if (!text.trim()) return;
    addMsg(root, "user", text);
    root.querySelector("textarea").value = "";
    setBusy(root, true);
    try {
      const res = await call("send_message", { message: text, session_id: sessionId });
      sessionId = res.session_id || sessionId;
      addMsg(root, "assistant", res.content || "لم يصل رد واضح.", res);
      if (res.requires_confirmation) addMsg(root, "assistant", `يتطلب تأكيد: ${res.confirmation?.summary || "إجراء حساس"}`);
    } catch (e) {
      addMsg(root, "assistant", "تعذر تنفيذ الطلب. راجع الصلاحيات أو إعدادات النموذج.");
      console.error(e);
    } finally { setBusy(root, false); }
  }
  async function render() {
    if (!isDesk() || document.getElementById(WIDGET_ID) || !window.frappe) return;
    let config = { enable_chat_widget: true, debug_available: false };
    try { config = await call("get_ui_config", {}); } catch (e) { console.warn("Trilogy Ai config unavailable", e); }
    if (!config?.enable_chat_widget) return;
    const rtl = document.dir === "rtl" || config.rtl || (frappe.boot?.lang || "").startsWith("ar");
    const root = document.createElement("div");
    root.id = WIDGET_ID;
    root.dir = rtl ? "rtl" : "ltr";
    root.innerHTML = `<button class="huf-chat-launch" type="button">Trilogy Ai</button><aside class="huf-chat-panel" aria-label="Trilogy Ai Chat"><header><div><strong>Trilogy Ai</strong><span>مساعد ERPNext الذكي</span></div><button data-close type="button">×</button></header><main data-chat-list><div class="huf-chat-welcome"><strong>كيف أساعدك؟</strong><span>اسأل عن المبيعات، المخزون، الفواتير أو إجراءات المتابعة.</span></div></main><section class="huf-chat-prompts">${prompts.map(p => `<button type="button" data-prompt="${esc(p)}">${esc(p)}</button>`).join("")}</section><footer><textarea rows="2" placeholder="اكتب طلبك هنا..."></textarea><button data-send type="button">إرسال</button></footer><a class="huf-chat-full" href="/app/huf-chat">فتح الصفحة الكاملة</a></aside>`;
    document.body.appendChild(root);
    root.querySelector(".huf-chat-launch").onclick = () => root.classList.toggle("open");
    root.querySelector("[data-close]").onclick = () => root.classList.remove("open");
    root.querySelector("[data-send]").onclick = () => send(root, root.querySelector("textarea").value);
    root.querySelector("textarea").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(root, e.target.value); } });
    root.querySelectorAll("[data-prompt]").forEach(b => b.onclick = () => send(root, b.dataset.prompt));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render); else render();
})();
