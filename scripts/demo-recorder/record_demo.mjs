import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../..");
const outDir = path.join(root, "docs", "demo");
fs.mkdirSync(outDir, { recursive: true });

const baseURL = process.env.DEMO_BASE_URL || "http://127.0.0.1:8080";
const login = process.env.DEMO_LOGIN || "analyst";
const password = process.env.DEMO_PASSWORD;
if (!password) {
  console.error("Задайте DEMO_PASSWORD");
  process.exit(1);
}

const chromePath = process.env.CHROME_PATH
  || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function visit(page, href, waitMs = 2400) {
  const link = page.locator(`nav a[href="${href}"]`).first();
  if (await link.count()) {
    await link.click({ timeout: 8000 });
  } else {
    await page.goto(new URL(href, baseURL).toString(), { waitUntil: "domcontentloaded" });
  }
  await delay(waitMs);
}

async function clickTab(page, name) {
  const tab = page.locator("button.tab", { hasText: name }).first();
  if (await tab.count()) {
    await tab.click();
    await delay(1700);
  }
}

const browser = await chromium.launch({
  headless: true,
  slowMo: 160,
  executablePath: chromePath,
  args: ["--disable-dev-shm-usage"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: outDir, size: { width: 1440, height: 900 } },
  locale: "ru-RU",
});
const page = await context.newPage();

try {
  await page.goto(`${baseURL}/login`, { waitUntil: "domcontentloaded" });
  await delay(1400);
  await page.locator("input").nth(0).fill(login);
  await page.locator("input[type=password]").fill(password);
  await delay(700);
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL((url) => !String(url).includes("/login"), { timeout: 25000 });
  await delay(3000);

  await visit(page, "/organizations");
  await visit(page, "/data", 3000);
  await visit(page, "/analysis", 2800);

  const openLink = page.locator("a[href^='/analysis/']").first();
  if (await openLink.count()) {
    await openLink.click();
    await delay(3000);
    for (const name of ["Заключение", "Оценка", "Коэффициенты", "Тенденции", "Проблемы", "Аномалии", "Прогноз"]) {
      await clickTab(page, name);
    }
  }

  await visit(page, "/recommendations", 2600);
  await visit(page, "/measures", 2400);
  await visit(page, "/scenarios", 2400);
  await visit(page, "/norms", 2600);
  await visit(page, "/reports", 2400);
  await visit(page, "/", 3500);
  await page.mouse.wheel(0, 600);
  await delay(1800);
  await page.mouse.wheel(0, 800);
  await delay(2200);
} catch (error) {
  console.error(error);
  await page.screenshot({ path: path.join(outDir, "demo-error.png"), fullPage: true }).catch(() => {});
  throw error;
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  if (video) {
    const src = await video.path();
    const dest = path.join(outDir, "crisis-control-demo.webm");
    if (fs.existsSync(dest)) {
      fs.unlinkSync(dest);
    }
    fs.renameSync(src, dest);
    console.log(dest);
  }
}
