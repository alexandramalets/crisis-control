import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "docs", "demo");
fs.mkdirSync(outDir, { recursive: true });

const baseURL = process.env.DEMO_BASE_URL || "http://127.0.0.1:8080";
const login = process.env.DEMO_LOGIN || "analyst";
const password = process.env.DEMO_PASSWORD;
if (!password) {
  console.error("Задайте DEMO_PASSWORD");
  process.exit(1);
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function visit(page, href, waitMs = 2200) {
  await page.locator(`nav a[href="${href}"]`).first().click({ timeout: 8000 }).catch(async () => {
    await page.goto(new URL(href, baseURL).toString(), { waitUntil: "networkidle" });
  });
  await delay(waitMs);
}

async function clickTab(page, name) {
  const tab = page.getByRole("tab", { name }).or(page.locator("button.tab", { hasText: name }));
  if (await tab.count()) {
    await tab.first().click();
    await delay(1600);
  }
}

const browser = await chromium.launch({
  headless: true,
  slowMo: 180,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: outDir, size: { width: 1440, height: 900 } },
  locale: "ru-RU",
});
const page = await context.newPage();

try {
  await page.goto(`${baseURL}/login`, { waitUntil: "networkidle" });
  await delay(1200);
  await page.locator("input").nth(0).fill(login);
  await page.locator("input[type=password]").fill(password);
  await delay(600);
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 20000 });
  await delay(2800);

  await visit(page, "/organizations");
  await visit(page, "/data", 2800);
  await visit(page, "/analysis", 2500);

  const openLink = page.locator("a[href^='/analysis/']").first();
  if (await openLink.count()) {
    await openLink.click();
    await delay(2800);
    for (const name of ["Заключение", "Оценка", "Коэффициенты", "Тенденции", "Проблемы", "Аномалии", "Прогноз"]) {
      await clickTab(page, name);
    }
  }

  await visit(page, "/recommendations", 2500);
  await visit(page, "/measures", 2200);
  await visit(page, "/scenarios", 2200);
  await visit(page, "/norms", 2500);
  await visit(page, "/reports", 2200);
  await visit(page, "/", 3200);
  await page.mouse.wheel(0, 500);
  await delay(1800);
  await page.mouse.wheel(0, 700);
  await delay(2000);
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const src = await video.path();
    const dest = path.join(outDir, "crisis-control-demo.webm");
    fs.renameSync(src, dest);
    console.log(dest);
  }
}
