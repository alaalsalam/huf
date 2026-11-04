/* Actual Wiki/Desk integration. No business writes or exported authentication state. */
const fs = require("fs"),
  path = require("path"),
  cp = require("child_process"),
  crypto = require("crypto");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ||
  "playwright-core");
const bench = process.env.GUIDE_TEST_BENCH,
  site = process.env.GUIDE_TEST_SITE_NAME,
  origin = process.env.GUIDE_TEST_ORIGIN,
  out = process.env.GUIDE_TEST_OUTPUT;
if (!bench || !site || !origin || !out)
  throw Error("Explicit verified target required");
const token = crypto.randomBytes(6).toString("hex");
const users = ["employee_ar", "employee_en", "limited"].map((persona) => ({
  persona,
  email: `huf.wiki.${token}.${persona}@example.invalid`,
  password: crypto.randomBytes(32).toString("base64url"),
  language: persona === "employee_ar" ? "ar" : "en",
}));
const result = {
  started_utc: new Date().toISOString(),
  site,
  cases: [],
  external_attempts: [],
  asset_errors: [],
  page_errors: [],
};
function fixture(action) {
  const r = cp.spawnSync(
    path.join(bench, "env/bin/python"),
    [path.join(__dirname, "guide_wiki_accounts.py"), "--site", site],
    {
      cwd: path.join(bench, "sites"),
      input: JSON.stringify({ action, token, users }),
      encoding: "utf8",
    }
  );
  if (r.status !== 0) throw Error("Fixture " + action + ": " + r.stderr);
  return JSON.parse(r.stdout.trim().split("\n").at(-1));
}
function assert(v, m) {
  if (!v) throw Error(m);
}
async function check(name, fn) {
  if (
    process.env.GUIDE_SOURCE_FOCUS === "1" &&
    !name.startsWith("Real Wiki source") &&
    !name.startsWith("AR mobile") &&
    !name.startsWith("employee_ar screen")
  )
    return;
  try {
    await fn();
    result.cases.push({ name, pass: true });
    console.log(name + ": PASS");
  } catch (e) {
    result.cases.push({ name, pass: false, error: e.message.slice(0, 700) });
    console.log(name + ": FAIL " + e.message);
  }
}
async function api(page, name, args = {}) {
  return page.evaluate(
    async ({ name, args }) => {
      const r = await fetch("/api/method/huf.guide.api." + name, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Frappe-CSRF-Token": frappe.csrf_token,
        },
        body: JSON.stringify(args),
      });
      return { status: r.status, body: await r.json() };
    },
    { name, args }
  );
}
async function main() {
  let browser,
    created = false;
  try {
    result.creation = fixture("create");
    created = true;
    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH,
      headless: true,
      args: ["--no-sandbox"],
    });
    for (const u of users) {
      if (process.env.GUIDE_SOURCE_FOCUS === "1" && u.persona !== "employee_ar")
        continue;
      const ctx = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
        locale: u.language,
      });
      await ctx.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (
          !["data:", "blob:"].includes(url.protocol) &&
          url.origin !== origin
        ) {
          result.external_attempts.push(url.origin);
          return route.abort();
        }
        return route.continue();
      });
      assert(
        (
          await ctx.request.post(origin + "/api/method/login", {
            form: { usr: u.email, pwd: u.password },
          })
        ).status() === 200,
        "Fixture login failed"
      );
      const page = await ctx.newPage();
      page.on("pageerror", (e) =>
        result.page_errors.push(e.message.slice(0, 400))
      );
      page.on("response", (r) => {
        if (
          r.status() >= 400 &&
          new URL(r.url()).pathname.startsWith("/assets/")
        )
          result.asset_errors.push({
            path: new URL(r.url()).pathname,
            status: r.status(),
          });
      });
      await page.goto(
        origin + (u.persona === "limited" ? "/desk/docs" : "/desk/customer"),
        { waitUntil: "domcontentloaded" }
      );
      await page.locator("#huf-guide-launcher").waitFor({ timeout: 30000 });
      await check(
        u.persona + " loaded Wiki revision and guide-only",
        async () => {
          const r = await api(page, "bootstrap");
          assert(
            r.body.message.api_revision === "system-guide-wiki-v3",
            "Old worker revision"
          );
          assert(
            r.body.message.mode === "guide_only" &&
              r.body.message.source === "Wiki",
            "Unexpected source/mode"
          );
        }
      );
      if (u.persona === "limited") {
        await check(
          "Limited reader: direct Wiki article, native reader, search and screen binding denied",
          async () => {
            const r = await api(page, "get_guide", {
              path: "wiki:crms/subscriber-list-screen",
            });
            assert(
              r.status === 403 &&
                !JSON.stringify(r).includes("قائمة المشتركين"),
              "Denied article metadata leaked"
            );
            const search = await api(page, "search_guides", {
              query: "المشترك",
            });
            assert(
              search.status === 200 &&
                !search.body.message.some((x) =>
                  x.path.startsWith("wiki:crms/")
                ),
              "Search metadata leaked"
            );
            const help = await api(page, "resolve_help", {
              context: { screen_type: "List", screen_name: "Customer" },
            });
            assert(
              help.status === 200 && help.body.message.length === 0,
              "Denied screen binding leaked"
            );
            const native = await ctx.request.get(
              origin + "/crms/subscriber-list-screen"
            );
            assert(native.status() !== 200, "Native Wiki role denial failed");
          }
        );
        await ctx.close();
        continue;
      }
      await page.locator("#huf-guide-launcher").click();
      await check(
        u.persona + " screen manual opens automatically and keeps actions",
        async () => {
          await page
            .locator(".huf-guide-article h3")
            .filter({ hasText: "قائمة المشتركين" })
            .waitFor({ timeout: 20000 });
          assert(
            (
              await page.locator(".huf-guide-card").first().innerText()
            ).includes("قائمة المشتركين"),
            "Specialized procedure precedes screen guide"
          );
          assert(
            (await page.locator(".huf-guide-other").count()) === 1,
            "Secondary procedures missing"
          );
          assert(
            await page
              .locator(".huf-guide-card")
              .first()
              .getByRole("button", {
                name: u.language === "ar" ? "ابدأ الجولة" : "Start tour",
                exact: true,
              })
              .isVisible(),
            "Tour lost when article opened"
          );
          await page
            .locator("#huf-guide-panel")
            .screenshot({ path: path.join(out, u.persona + "-desktop.png") });
        }
      );
      if (u.persona === "employee_ar") {
        await check(
          "Real Wiki source opens while Desk stays on Customer",
          async () => {
            await page
              .locator(".huf-guide-card .huf-guide-source")
              .first()
              .waitFor();
            const before = await page.evaluate(() => ({
              path: location.pathname,
              route: frappe.get_route(),
            }));
            const opened = page.waitForEvent("popup");
            await page
              .locator(".huf-guide-card")
              .first()
              .locator(".huf-guide-source")
              .click();
            const reader = await opened;
            await reader.waitForLoadState("domcontentloaded");
            assert(
              new URL(reader.url()).pathname === "/crms/subscriber-list-screen",
              "Incorrect Wiki route"
            );
            assert(
              (await reader.locator("body").innerText()).includes(
                "قائمة المشتركين"
              ),
              "Wiki reader not rendered"
            );
            const after = await page.evaluate(() => ({
              path: location.pathname,
              route: frappe.get_route(),
            }));
            result.source_desk_context = { before, after };
            assert(
              JSON.stringify(before) === JSON.stringify(after) &&
                after.route.includes("Customer"),
              "Desk context lost"
            );
            await reader.screenshot({
              path: path.join(out, "wiki-source-ar.png"),
            });
            await reader.close();
          }
        );
        await check("Native Customer list Form Tour starts", async () => {
          await page
            .locator(".huf-guide-card")
            .first()
            .getByRole("button", { name: "ابدأ الجولة", exact: true })
            .click();
          await page
            .locator("#driver-popover-item")
            .waitFor({ timeout: 15000 });
          assert(
            (await page.locator(".driver-popover-title").innerText()).includes(
              "ابحث"
            ),
            "Wrong native tour"
          );
          await page.evaluate(() =>
            window.huf_system_guide.tour.driver.reset()
          );
        });
        await check(
          "Arabic Wiki search returns live original source",
          async () => {
            await page.locator("#huf-guide-query").fill("تسجيل مشترك");
            await page.locator("#huf-guide-query").press("Enter");
            await page.waitForFunction(() =>
              [...document.querySelectorAll(".huf-guide-card a")].some(
                (a) =>
                  a.getAttribute("href") ===
                  "/crms/d01-s01-new-customer-registration"
              )
            );
            assert(
              !(await page.locator(".huf-guide-results").innerText()).includes(
                "/desk/docs/"
              ),
              "Compendium copy in Wiki search"
            );
          }
        );
        await check("AR mobile panel has no horizontal overflow", async () => {
          await page.setViewportSize({ width: 390, height: 844 });
          await page
            .getByRole("button", { name: "دليل هذه الشاشة", exact: true })
            .click();
          await page
            .locator(".huf-guide-article h3")
            .filter({ hasText: "قائمة المشتركين" })
            .waitFor();
          assert(
            (await page.locator("#huf-guide-host").getAttribute("dir")) ===
              "rtl",
            "RTL missing"
          );
          assert(
            await page.evaluate(
              () =>
                document.querySelector("#huf-guide-panel").scrollWidth <=
                document.querySelector("#huf-guide-panel").clientWidth + 1
            ),
            "Horizontal overflow"
          );
          await page
            .locator("#huf-guide-panel")
            .screenshot({ path: path.join(out, "employee-ar-mobile.png") });
        });
        await check(
          "Route change clears previous manual and prioritizes general request instructions",
          async () => {
            await page.evaluate(() =>
              frappe.set_route("List", "Utility Service Request")
            );
            await page
              .locator(".huf-guide-article h3")
              .filter({ hasText: "تقديم طلب خدمة وتصحيح طلب معاد" })
              .waitFor({ timeout: 20000 });
            assert(
              !(await page.locator(".huf-guide-article").innerText()).includes(
                "قائمة المشتركين"
              ),
              "Stale screen body"
            );
            assert(
              (
                await page.locator(".huf-guide-card").first().innerText()
              ).includes("تقديم طلب خدمة"),
              "Specialized new connection shown as default"
            );
            await page
              .getByRole("button", { name: "ما الخطوة التالية؟", exact: true })
              .click();
            await page.waitForFunction(() => !frappe.ajax_count);
            assert(
              !(await page.locator("#huf-guide-panel").innerText()).includes(
                "نتيجة فحص هذا الطلب المحفوظ"
              ),
              "Guide falsely claims a record check"
            );
          }
        );
      } else {
        await check(
          "EN UI keeps original Arabic manual and supports AMS Wiki discovery",
          async () => {
            assert(
              await page
                .getByRole("button", {
                  name: "Guide for this screen",
                  exact: true,
                })
                .isVisible(),
              "EN controls missing"
            );
            const r = await api(page, "search_guides", { query: "الحضور" });
            assert(
              r.status === 200 &&
                r.body.message.some((x) => x.path.startsWith("wiki:ams/")),
              "Existing AMS manual not searchable"
            );
          }
        );
      }
      await ctx.close();
    }
  } finally {
    if (browser) await browser.close();
    if (created) {
      result.cleanup = fixture("cleanup");
      await new Promise((r) => setTimeout(r, 1500));
      result.cleanup_final = fixture("cleanup");
    }
    result.finished_utc = new Date().toISOString();
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(
      path.join(out, "BROWSER.json"),
      JSON.stringify(result, null, 2) + "\n"
    );
  }
  if (
    result.cases.some((x) => !x.pass) ||
    result.asset_errors.length ||
    result.page_errors.length ||
    result.external_attempts.length
  )
    process.exitCode = 1;
}
main().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
