import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
// Playwright from node_modules, or point PLAYWRIGHT_PATH at another install.
const { chromium } = require(process.env.PLAYWRIGHT_PATH || "playwright");

const root = path.dirname(decodeURIComponent(new URL(import.meta.url).pathname));
const pageUrl = pathToFileURL(path.join(root, "render_notes.html"));
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});

for (const option of [1, 2, 3]) {
  const page = await browser.newPage({
    viewport: { width: 1024, height: 1536 },
    deviceScaleFactor: 1,
  });
  await page.goto(`${pageUrl.href}?option=${option}`, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const metrics = await page.locator("#note").evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    text: element.innerText,
  }));
  if (metrics.scrollHeight > metrics.clientHeight || metrics.scrollWidth > metrics.clientWidth) {
    throw new Error(`Option ${option} overflows its note area: ${JSON.stringify(metrics)}`);
  }
  await page.screenshot({
    path: path.join(root, `note-option-${option}.png`),
    type: "png",
  });
  console.log(`Rendered option ${option}: ${metrics.text.length} characters, no overflow`);
  await page.close();
}

await browser.close();
