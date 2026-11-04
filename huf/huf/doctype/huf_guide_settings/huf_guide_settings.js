frappe.ui.form.on("HUF Guide Settings", {
	refresh(frm) {
		const area = frm.fields_dict.resources.$wrapper.empty();
		for (const [label, doctype] of [[__("Articles"), "Compendium Page"], [__("Service Bindings"), "HUF Guide Binding"], [__("Form Tours"), "Form Tour"]]) {
			if (!frappe.model.can_read(doctype)) continue;
			$("<button type='button' class='btn btn-default mr-2 mb-2'>").text(label).appendTo(area).on("click", () => frappe.set_route("List", doctype));
		}
		const results = frm.fields_dict.readiness.$wrapper.empty();
		$("<button type='button' class='btn btn-default'>").text(__("Check Service Readiness")).appendTo(results).on("click", async () => {
			if (frm.is_dirty()) { frappe.msgprint(__("Save settings before checking readiness.")); return; }
			try {
				const report = await frappe.xcall("huf.guide.api.readiness");
				results.find(".guide-readiness-result").remove();
				const content = $("<div class='guide-readiness-result mt-3'>").appendTo(results);
				$("<p>").text(report.installed && report.compatible ? __("Compendium is ready.") : __("Install a compatible Compendium version before enabling the guide.")).appendTo(content);
				if (!report.services.length) $("<p>").text(__("Add a service binding to start.")).appendTo(content);
				for (const service of report.services) {
					const card = $("<div class='mb-3'>").appendTo(content);
					$("<button type='button' class='btn btn-link'>").text(service.screen).appendTo(card).on("click", () => frappe.set_route("Form", "HUF Guide Binding", service.binding));
					if (service.ready) $("<p>").text(__("Configuration ready; verify with the employee role.")).appendTo(card);
					for (const issue of service.issues) $("<p>").text(issue).appendTo(card);
				}
			} catch { frappe.msgprint(__("Readiness check unavailable or not permitted.")); }
		});
	}
});
