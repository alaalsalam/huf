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
			this.host = el("div", {
				id: "huf-guide-host",
				dir: frappe.boot.lang?.startsWith("ar") ? "rtl" : "ltr",
			});
			this.launcher = el(
				"button",
				{
					id: "huf-guide-launcher",
					class: "btn btn-primary",
					"aria-controls": "huf-guide-panel",
					"aria-expanded": "false",
				},
				t("System Guide")
			);
			this.launcher.onclick = () => (this.opened ? this.close() : this.open());
			this.panel = el("section", {
				id: "huf-guide-panel",
				role: "dialog",
				"aria-labelledby": "huf-guide-title",
				hidden: "",
			});
			const header = el("header");
			header.append(el("h2", { id: "huf-guide-title" }, t("System Guide")));
			const close = el(
				"button",
				{ class: "btn btn-default btn-sm", "aria-label": t("Close") },
				"×"
			);
			close.onclick = () => this.close();
			header.append(close);
			this.panel.append(
				header,
				el(
					"p",
					{ class: "huf-guide-intro" },
					t(
						"Find instructions and their sources. Search results are documentation, not AI answers."
					)
				)
			);
			this.screenLabel = el("p", { class: "huf-guide-screen" });
			this.panel.append(this.screenLabel);
			const actions = el("nav", { "aria-label": t("System Guide") });
			for (const [label, fn] of [
				["Guide for this screen", () => this.loadContext()],
				["What is the next step?", () => this.loadContext(true)],
				["Search the service guide", () => this.query.focus()],
			]) {
				const button = el("button", { class: "btn btn-default" }, t(label));
				button.onclick = fn;
				actions.append(button);
			}
			this.panel.append(actions);
			const search = el("form");
			const label = el("label", { for: "huf-guide-query" }, t("Search the guide"));
			this.query = el("input", {
				id: "huf-guide-query",
				class: "form-control",
				type: "search",
				maxlength: "200",
				autocomplete: "off",
				placeholder: t("Service or screen name, for example service request"),
			});
			search.append(
				label,
				this.query,
				el("button", { class: "btn btn-primary", type: "submit" }, t("Search"))
			);
			search.onsubmit = (e) => {
				e.preventDefault();
				this.search();
			};
			const details = el("details");
			details.append(el("summary", {}, t("Explain a known error")));
			this.errorBox = el("form");
			this.errorInput = el("input", {
				id: "huf-guide-error",
				class: "form-control",
				maxlength: "140",
				autocomplete: "off",
			});
			this.errorBox.append(
				el("label", { for: "huf-guide-error" }, t("Known error code")),
				this.errorInput,
				el(
					"button",
					{ class: "btn btn-default", type: "submit" },
					t("Explain a known error")
				)
			);
			this.errorBox.onsubmit = (e) => {
				e.preventDefault();
				this.explain();
			};
			this.status = el("p", { role: "status", "aria-live": "polite" });
			this.results = el("div", { class: "huf-guide-results" });
			this.article = el("article", { class: "huf-guide-article" });
			this.support = el("p", { class: "huf-guide-support" });
			details.append(this.errorBox);
			this.panel.append(
				search,
				details,
				this.status,
				this.results,
				this.article,
				this.support
			);
			this.host.append(this.launcher, this.panel);
			this.host.hidden = true;
			document.body.append(this.host);
		}
		getContext() {
			const route = frappe.get_route() || [];
			if (["Form", "List"].includes(route[0]))
				return {
					screen_type: route[0],
					screen_name: route[1],
					...(route[0] === "Form" && this.field ? { fieldname: this.field } : {}),
				};
			if (route[0] === "Workspaces" && route[1])
				return { screen_type: "Workspace", screen_name: route[1] };
			return route[0] ? { screen_type: "Page", screen_name: route[0] } : {};
		}
		async routeChanged() {
			const revision = ++this.revision;
			++this.request;
			this.tour?.driver?.reset();
			this.field = "";
			this.context = this.getContext();
			this.items = [];
			this.results.replaceChildren();
			this.article.replaceChildren();
			this.status.textContent = "";
			this.errorInput.value = "";
			this.query.value = "";
			try {
				const settings = await call("bootstrap", { context: this.context });
				if (revision !== this.revision) return;
				this.host.hidden = !settings.enabled;
				this.support.textContent =
					settings.support ||
					t("Contact your site administrator if no guidance is available.");
				this.screenLabel.textContent = settings.screen_label || t("Current screen");
				if (!settings.enabled) this.close();
				else if (this.opened) await this.loadContext();
			} catch {
				if (revision === this.revision) this.host.hidden = true;
			}
		}
		open() {
			this.opened = true;
			this.panel.hidden = false;
			this.launcher.setAttribute("aria-expanded", "true");
			this.query.focus();
			this.loadContext();
		}
		close() {
			this.opened = false;
			this.panel.hidden = true;
			this.launcher.setAttribute("aria-expanded", "false");
			this.launcher.focus();
		}
		async run(name, args, apply, keepResults = false) {
			const revision = this.revision,
				request = ++this.request;
			this.status.textContent = t("Loading...");
			if (!keepResults) this.results.replaceChildren();
			this.article.replaceChildren();
			try {
				const result = await call(name, args);
				if (revision !== this.revision || request !== this.request) return;
				this.status.textContent = "";
				apply(result);
			} catch {
				if (revision !== this.revision || request !== this.request) return;
				this.results.replaceChildren();
				this.article.replaceChildren();
				this.status.textContent = t(
					"Guidance is unavailable. Try again or use the approved support channel."
				);
			}
		}
		async loadContext(next = false) {
			this.context = this.getContext();
			await this.run("resolve_help", { context: this.context }, (items) => {
				this.items = items;
				this.renderResults(items, next);
				if (!items.length)
					this.status.textContent = t("No published guide is linked to this screen.");
				else if (!next) this.read(items[0].path);
			});
		}
		search() {
			this.run(
				"search_guides",
				{ query: this.query.value, context: this.context },
				(items) => {
					this.renderResults(items);
					if (!items.length)
						this.status.textContent = t("No permitted results. Try fewer words.");
				}
			);
		}
		explain() {
			this.run(
				"resolve_help",
				{ context: { ...this.context, error_key: this.errorInput.value.trim() } },
				(items) => {
					const exact = items.filter(
						(item) => item.error_key === this.errorInput.value.trim() && item.error_key
					);
					this.renderResults(exact, true);
					if (!exact.length)
						this.status.textContent = t(
							"No documented guidance is available for this situation."
						);
				}
			);
		}
		renderResults(items, next = false) {
			this.results.replaceChildren();
			this.article.replaceChildren();
			let other;
			for (const [index, item] of items.entries()) {
				if (index === 1 && !item.snippet) {
					other = el("details", { class: "huf-guide-other" });
					other.append(el("summary", {}, t("Other documented procedures")));
					this.results.append(other);
				}
				const card = el("div", { class: "huf-guide-card" });
				card.append(
					el(
						"span",
						{ class: "huf-guide-badge" },
						`${t("From the guide")} · ${item.source || "Compendium"}`
					)
				);
				if (next) {
					if (item.cause) card.append(el("p", {}, t(item.cause)));
					card.append(
						el(
							"p",
							{},
							item.instruction
								? t(item.instruction)
								: t(
										"Read the source before proceeding. No next step is documented."
								  )
						)
					);
				}
				const button = el("button", { class: "btn btn-link" }, item.title);
				button.onclick = () => this.read(item.path);
				const source = this.sourceLink(item);
				card.append(button);
				if (item.snippet) card.append(el("p", {}, item.snippet));
				if (item.tour) {
					const tour = el(
						"button",
						{ class: "btn btn-default btn-sm" },
						t("Start tour")
					);
					tour.onclick = () => this.startTour(item);
					card.append(tour);
				}
				if (item.action && this.actionVisible(item.action)) {
					const go = el(
						"button",
						{ class: "btn btn-default btn-sm huf-guide-destination" },
						t(item.action.kind === "field" ? "Go to field" : "Open page")
					);
					go.onclick = () => this.navigate(item);
					card.append(go);
				}
				if (next && item.can_check) {
					const check = el(
						"button",
						{ class: "btn btn-default btn-sm" },
						t("Check this request")
					);
					check.onclick = () => this.checkRecord(item);
					card.append(check);
				}
				card.append(source);
				(other || this.results).append(card);
			}
		}
		sourceLink(page) {
			const source = el(
				"a",
				{ href: page.url, class: "huf-guide-source" },
				t("Open source")
			);
			if (page.url.startsWith("/desk/")) {
				source.onclick = (e) => {
					e.preventDefault();
					frappe.set_route(page.url.replace(/^\/desk\//, ""));
				};
			} else {
				// Wiki is a website reader, not a Desk route. Keep the working form intact.
				source.target = "_blank";
				source.rel = "noopener noreferrer";
			}
			return source;
		}
		read(path) {
			this.run(
				"get_guide",
				{ path, context: this.context },
				(page) => {
					this.article.replaceChildren(el("h3", {}, page.title));
					this.article.append(this.sourceLink(page));
					const body = el("div", { class: "from-markdown", dir: "auto" });
					// HTML is rendered/sanitised by the source adapter after native access checks.
					// Keep passive third-party resources out of the guide, including tracking images.
					const template = document.createElement("template");
					template.innerHTML = page.content;
					template.content
						.querySelectorAll("iframe,object,embed,script,link,style")
						.forEach((node) => node.remove());
					for (const node of template.content.querySelectorAll("*")) {
						for (const attr of [...node.attributes])
							if (attr.name.startsWith("on")) node.removeAttribute(attr.name);
						node.removeAttribute("srcset");
						if (/url\s*\(|@import/i.test(node.getAttribute("style") || ""))
							node.removeAttribute("style");
						for (const attr of [
							"src",
							"poster",
							"xlink:href",
							...(node.tagName.toLowerCase() !== "a" ? ["href"] : []),
						]) {
							if (!node.hasAttribute(attr)) continue;
							try {
								const url = new URL(node.getAttribute(attr), location.origin);
								if (url.origin !== location.origin) node.removeAttribute(attr);
							} catch {
								node.removeAttribute(attr);
							}
						}
						if (node.tagName.toLowerCase() === "a" && node.hasAttribute("href")) {
							try {
								const url = new URL(
									node.getAttribute("href"),
									new URL(page.url, location.origin)
								);
								if (!["http:", "https:"].includes(url.protocol))
									node.removeAttribute("href");
								else {
									node.href = url.href;
									node.target = "_blank";
									node.rel = "noopener noreferrer";
								}
							} catch {
								node.removeAttribute("href");
							}
						}
					}
					body.append(template.content);
					this.article.append(body);
				},
				true
			);
		}
		actionVisible(action) {
			return (
				action.kind !== "field" ||
				(window.cur_frm?.doctype === action.screen &&
					cur_frm.fields_dict[action.field]?.$wrapper?.is(":visible"))
			);
		}
		navigate(item) {
			this.run("resolve_help", { context: this.context }, (items) => {
				const action = items.find((v) => v.binding === item.binding)?.action;
				if (!action || !this.actionVisible(action)) {
					this.status.textContent = t("Destination unavailable or not permitted.");
					return;
				}
				if (action.kind === "field") {
					this.close();
					cur_frm.scroll_to_field(action.field);
					cur_frm.fields_dict[action.field].set_focus();
				} else
					frappe.set_route(
						action.screen_type === "Page"
							? [action.screen]
							: [
									action.screen_type === "Workspace"
										? "Workspaces"
										: action.screen_type,
									action.screen,
							  ]
					);
			});
		}
		checkRecord(item) {
			if (!window.cur_frm || cur_frm.is_new() || cur_frm.is_dirty()) {
				this.status.textContent = t(
					"Unsaved draft: save it before requesting a record check. No record was checked."
				);
				return;
			}
			this.run(
				"check_record",
				{ binding: item.binding, document_name: cur_frm.doc.name, context: this.context },
				(result) => {
					const card = el("div", {
						class: "huf-guide-check",
						"data-state": result.state,
					});
					card.append(
						el("strong", {}, t("Check of this saved request")),
						el("p", {}, t(result.instruction)),
						el("p", {}, t(result.limitation))
					);
					const source = el("a", { href: result.source.url }, result.source.title);
					card.append(source);
					this.results.append(card);
					this.support.hidden = result.state !== "unknown" && !this.support.textContent;
					if (result.action) {
						const go = el(
							"button",
							{ class: "btn btn-default huf-guide-destination" },
							t(result.action.kind === "field" ? "Go to field" : "Open page")
						);
						go.onclick = () => this.navigate(item);
						card.append(go);
					}
				}
			);
		}
		async startTour(item = this.items.find((entry) => entry.tour)) {
			if (!item) {
				this.status.textContent = t("No tour is available for this screen.");
				return;
			}
			const revision = this.revision;
			try {
				const doc = await call("get_tour", {
					binding: item.binding,
					context: this.context,
				});
				if (revision !== this.revision) return;
				frappe.model.sync(doc);
				if (doc.ui_tour) {
					await frappe.require("onboarding_tours.bundle.js");
					if (revision !== this.revision) return;
					frappe.boot.user.onboarding_status ||= {};
					const tour = new frappe.ui.OnboardingTour();
					this.tour?.driver?.reset();
					this.tour = tour;
					// Native Form Tour records, native step builder and native Driver.
					// Read-only guidance deliberately omits onboarding-status writes/telemetry.
					tour.tour = doc;
					tour.driver = new frappe.Driver({
						className: "frappe-driver",
						allowClose: true,
						keyboardControl: true,
						padding: 10,
						opacity: 0.5,
						nextBtnText: t("Next"),
						prevBtnText: t("Previous"),
						doneBtnText: t("Done"),
						closeBtnText: t("Close"),
					});
					tour.driver_steps = doc.steps
						.map((step) =>
							tour.get_step(
								{
									...step,
									title: t(step.title),
									description: t(step.description),
									ondemand_description: t(step.ondemand_description || ""),
								},
								() => {}
							)
						)
						.filter((step) => step.element);
					tour.update_driver_steps();
					tour.start();
				} else if (window.cur_frm?.doctype === this.context.screen_name) {
					this.tour = new frappe.ui.form.FormTour({ frm: cur_frm });
					await this.tour.init({ tour_name: doc.name });
					this.tour.start();
				}
			} catch {
				this.status.textContent = t("No tour is available for this screen.");
			}
		}
	}
	const start = () => {
		if (!window.frappe?.boot || frappe.session.user === "Guest" || window.huf_system_guide)
			return;
		window.huf_system_guide = new SystemGuide();
	};
	if (window.frappe?.boot) start();
	else $(document).on("app_ready", start);
})();
