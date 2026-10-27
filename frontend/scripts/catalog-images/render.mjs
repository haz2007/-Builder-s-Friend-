// Рисует картинки каталога: node scripts/catalog-images/render.mjs [slug…]
// SVG из draw.mjs → WebP 1200×900 в public/catalog/ (через Chromium из Playwright).
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import * as draw from "./draw.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const outDir = join(root, "public", "catalog");
const catalog = JSON.parse(readFileSync(join(here, "catalog.json"), "utf-8"));
const only = new Set(process.argv.slice(2));

// Шрифт сайта (Manrope) встраиваем прямо в SVG, иначе картинка возьмёт системный
const font = (subset) =>
  readFileSync(join(root, "node_modules/@fontsource/manrope/files", `manrope-${subset}-800-normal.woff2`)).toString("base64");
const fontCss = ["latin", "cyrillic"]
  .map((s) => `@font-face{font-family:Manrope;font-weight:600 800;src:url(data:font/woff2;base64,${font(s)}) format("woff2");}`)
  .join("");

mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent("<canvas id=c width=1200 height=900></canvas>");

// Первый рисунок с текстом иногда опережает загрузку шрифта: прогреваем его заранее
const warm = draw.frame(draw.roll({ title: "ПРОГРЕВ", big: "A", sub: "70" }), "1", fontCss);
await page.evaluate(async (src) => {
  const img = new Image();
  img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(src)));
  await img.decode();
  await new Promise((resolve) => setTimeout(resolve, 300));
}, warm);

for (const item of catalog) {
  if (only.size && !only.has(item.slug)) continue;
  const body = draw[item.kind](item.params ?? {});
  const svg = draw.frame(body, item.caption ?? "", fontCss);
  const dataUrl = await page.evaluate(async (src) => {
    const img = new Image();
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(src)));
    await img.decode();
    await document.fonts.ready;
    const canvas = document.getElementById("c");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, 1200, 900);
    ctx.drawImage(img, 0, 0);
    return canvas.toDataURL("image/webp", 0.86);
  }, svg);
  writeFileSync(join(outDir, `${item.slug}.webp`), Buffer.from(dataUrl.split(",")[1], "base64"));
}

await browser.close();
console.log("Готово:", only.size || catalog.length, "картинок →", outDir);
