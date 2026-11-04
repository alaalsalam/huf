/* System Guide. One body-level panel, no model, transaction values or external transport. */
(() => {
	if (window.huf_system_guide) return;
	const method = "huf.guide.api.";
	const t = (s) => __(s);
	const el = (tag, attrs = {}, text) => {
		const node = document.createElement(tag);
		for (const [k, value] of Object.entries(attrs)) node.setAttribute(k, value);
		if (text !== undefined) node.textContent = text;
		return node;
	};
	const call = (name, args = {}) => frappe.xcall(method + name, args);
	class SystemGuide {
		constructor() {
			this.revision = 0;
			this.request = 0;
			this.context = {};
			this.items = [];
			this.opened = false;
			this.mount();
			frappe.router.on("change", () => this.routeChanged());
			document.addEventListener("keydown", (e) => {
				if (e.key === "Escape" && this.opened) this.close();
			});
			document.addEventListener("focusin", (e) => {
				if (this.host.contains(e.target)) return;
				const field = e.target.closest(".frappe-control[data-fieldname]");
				this.field = field?.dataset.fieldname || "";
			});
			this.routeChanged();
		}
		mount() {
			this.host = el("div", { id: "huf-guide-host", dir: frappe.boot.lang?.startsWith("ar") ? "rtl" : "ltr" });
			this.launcher = el("button", { id: "huf-guide-launcher", class: "btn btn-primary", "aria-controls": "huf-guide-panel", "aria-expanded": "false" }, t("System Guide"));
			this.launcher.onclick = () => this.opened ? this.close() : this.open();
			this.panel = el("section", { id: "huf-guide-panel", role: "dialog", "aria-labelledby": "huf-guide-title", hidden: "" });
			const header = el("header");
			header.append(el("h2", { id: "huf-guide-title" }, t("System Guide")));
			const close = el("button", { class: "btn btn-default btn-sm", "aria-label": t("Close") }, "×");
			close.onclick = () => this.close(); header.append(close);
			this.panel.append(header, el("p", { class: "huf-guide-intro" }, t("Find instructions and their sources. Search results are documentation, not AI answers.")));
			const actions = el("nav", { "aria-label": t("System Guide") });
			for (const [label, fn] of [
				["Guide for this screen", () => this.loadContext()],
				["Search the guide", () => this.query.focus()],
				["Guide me step by step", () => this.startTour()],
				["Explain a known error", () => { this.errorBox.hidden = false; this.errorInput.focus(); }],
			]) {
				const button = el("button", { class: "btn btn-default" }, t(label));
				if (label === "Guide me step by step") { this.tourButton = button; button.disabled = true; }
				button.onclick = fn; actions.append(button);
			}
			this.panel.append(actions);
			const search = el("form");
			const label = el("label", { for: "huf-guide-query" }, t("Search the guide"));
			this.query = el("input", { id: "huf-guide-query", class: "form-control", type: "search", maxlength: "200", autocomplete: "off" });
			search.append(label, this.query, el("button", { class: "btn btn-primary", type: "submit" }, t("Search")));
			search.onsubmit = (e) => { e.preventDefault(); this.search(); };
			this.errorBox = el("form", { hidden: "" });
			this.errorInput = el("input", { id: "huf-guide-error", class: "form-control", maxlength: "140", autocomplete: "off" });
			this.errorBox.append(el("label", { for: "huf-guide-error" }, t("Known error code")), this.errorInput, el("button", { class: "btn btn-default", type: "submit" }, t("Explain a known error")));
			this.errorBox.onsubmit = (e) => { e.preventDefault(); this.explain(); };
			this.status = el("p", { role: "status", "aria-live": "polite" });
			this.results = el("div", { class: "huf-guide-results" });
			this.article = el("article", { class: "huf-guide-article" });
			this.support = el("p", { class: "huf-guide-support" });
			this.panel.append(search, this.errorBox, this.status, this.results, this.article, this.support);
			this.host.append(this.launcher, this.panel); this.host.hidden = true;
			document.body.append(this.host);
		}
		getContext() {
			const route = frappe.get_route() || [];
			if (["Form", "List"].includes(route[0])) return { screen_type: route[0], screen_name: route[1], ...(route[0] === "Form" && this.field ? { fieldname: this.field } : {}) };
			if (route[0] === "Workspaces" && route[1]) return { screen_type: "Workspace", screen_name: route[1] };
			return route[0] ? { screen_type: "Page", screen_name: route[0] } : {};
		}
		async routeChanged() {
			const revision = ++this.revision; ++this.request;
			this.tour?.driver?.reset();
			this.tourButton.disabled = true;
			this.field = ""; this.context = this.getContext(); this.items = [];
			this.results.replaceChildren(); this.article.replaceChildren();
			try {
				const settings = await call("bootstrap");
				if (revision !== this.revision) return;
				this.host.hidden = !settings.enabled;
				this.support.textContent = settings.support || "";
				if (!settings.enabled) this.close();
				else if (this.opened) await this.loadContext();
			} catch { if (revision === this.revision) this.host.hidden = true; }
		}
		open() {
			this.opened = true; this.panel.hidden = false;
			this.launcher.setAttribute("aria-expanded", "true"); this.query.focus(); this.loadContext();
		}
		close() {
			this.opened = false; this.panel.hidden = true;
			this.launcher.setAttribute("aria-expanded", "false"); this.launcher.focus();
		}
		async run(name, args, apply) {
			const revision = this.revision, request = ++this.request;
			this.status.textContent = t("Loading...");
			try {
				const result = await call(name, args);
				if (revision !== this.revision || request !== this.request) return;
				this.status.textContent = ""; apply(result);
			} catch {
				if (revision !== this.revision || request !== this.request) return;
				this.results.replaceChildren(); this.article.replaceChildren();
				this.status.textContent = t("Guide unavailable or not permitted.");
			}
		}
		async loadContext() {
			this.context = this.getContext();
			await this.run("resolve_help", { context: this.context }, (items) => {
				this.items = items; this.renderResults(items);
				this.tourButton.disabled = !items.some((item) => item.tour);
				if (!items.length) this.status.textContent = t("No published guide is linked to this screen.");
			});
		}
		search() {
			this.run("search_guides", { query: this.query.value, context: this.context }, (items) => {
				this.renderResults(items);
				if (!items.length) this.status.textContent = t("No permitted results. Try fewer words.");
			});
		}
		explain() {
			this.run("resolve_help", { context: { ...this.context, error_key: this.errorInput.value.trim() } }, (items) => {
				const exact = items.filter((item) => item.error_key === this.errorInput.value.trim() && item.error_key);
				this.renderResults(exact);
				if (!exact.length) this.status.textContent = t("This error is not documented. Use the approved support channel if available.");
			});
		}
		renderResults(items) {
			this.results.replaceChildren(); this.article.replaceChildren();
			for (const item of items) {
				const card = el("div", { class: "huf-guide-card" });
				const button = el("button", { class: "btn btn-link" }, item.title);
				button.onclick = () => this.read(item.path);
				const source = el("a", { href: item.url, class: "huf-guide-source" }, t("Open source"));
				source.onclick = (e) => { e.preventDefault(); frappe.set_route(item.url.replace(/^\/desk\//, "")); };
				card.append(button);
				if (item.snippet) card.append(el("p", {}, item.snippet));
				card.append(source); this.results.append(card);
			}
		}
		read(path) {
			this.run("get_guide", { path }, (page) => {
				this.article.replaceChildren(el("h3", {}, page.title));
				const body = el("div", { class: "from-markdown" });
				// HTML is rendered/sanitised by Compendium after its publication/role check.
				// Keep passive third-party resources out of the guide, including tracking images.
				const template = document.createElement("template");
				template.innerHTML = page.content;
				template.content.querySelectorAll("iframe,object,embed,script,link,style").forEach((node) => node.remove());
				for (const node of template.content.querySelectorAll("*")) {
					node.removeAttribute("srcset");
					if (/url\s*\(|@import/i.test(node.getAttribute("style") || "")) node.removeAttribute("style");
					for (const attr of ["src", "poster", "xlink:href", ...(node.tagName.toLowerCase() !== "a" ? ["href"] : [])]) {
						if (!node.hasAttribute(attr)) continue;
						try { const url = new URL(node.getAttribute(attr), location.origin); if (url.origin !== location.origin) node.removeAttribute(attr); }
						catch { node.removeAttribute(attr); }
					}
				}
				body.append(template.content); this.article.append(body);
			});
		}
		async startTour() {
			const item = this.items.find((entry) => entry.tour);
			if (!item) { this.status.textContent = t("No tour is available for this screen."); return; }
			const revision = this.revision;
			try {
				const doc = await call("get_tour", { binding: item.binding, context: this.context });
				if (revision !== this.revision) return;
				frappe.model.sync(doc);
				if (doc.ui_tour) {
					await frappe.require("onboarding_tours.bundle.js");
					if (revision !== this.revision) return;
					frappe.boot.user.onboarding_status ||= {};
					const tour = new frappe.ui.OnboardingTour();
					this.tour?.driver?.reset(); this.tour = tour;
					// Native Form Tour records, native step builder and native Driver.
					// Read-only guidance deliberately omits onboarding-status writes/telemetry.
					tour.tour = doc;
					tour.driver = new frappe.Driver({ className: "frappe-driver", allowClose: true,
						keyboardControl: true, padding: 10, opacity: 0.5,
						nextBtnText: t("Next"), prevBtnText: t("Previous"), doneBtnText: t("Done"), closeBtnText: t("Close") });
					tour.driver_steps = doc.steps.map((step) => tour.get_step({ ...step,
						title: t(step.title), description: t(step.description),
						ondemand_description: t(step.ondemand_description || "") }, () => {})).filter((step) => step.element);
					tour.update_driver_steps(); tour.start();
				} else if (window.cur_frm?.doctype === this.context.screen_name) {
					this.tour = new frappe.ui.form.FormTour({ frm: cur_frm });
					await this.tour.init({ tour_name: doc.name }); this.tour.start();
				}
			} catch { this.status.textContent = t("No tour is available for this screen."); }
		}
	}
	const start = () => {
		if (!window.frappe?.boot || frappe.session.user === "Guest" || window.huf_system_guide) return;
		window.huf_system_guide = new SystemGuide();
	};
	if (window.frappe?.boot) start(); else $(document).on("app_ready", start);
})();
