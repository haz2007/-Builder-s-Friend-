/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * В продакшене SEO-теги в <head> вставляет Caddy (шаблон в index.html).
 * В режиме разработки Caddy нет — подставляем обычные теги по умолчанию.
 */
function devSeoHead(): Plugin {
  return {
    name: "dev-seo-head",
    apply: "serve",
    transformIndexHtml(html) {
      return html.replace(
        /<!-- seo:start -->[\s\S]*?<!-- seo:end -->/,
        "<title>Друг Строителя — доска, брус и крепёж в Химках</title>\n" +
          '    <meta name="description" content="Обрезная доска, брус, вагонка и крепёж. Поштучно и кубами, доставка или самовывоз." />',
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), devSeoHead()],
  // Юнит-тесты — рядом с кодом; e2e/ запускает Playwright
  test: { include: ["src/**/*.test.ts"] },
  server: {
    proxy: {
      "/uploads": {
        target: process.env.API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/api": {
        // Можно указать другой бэкенд: API_TARGET=http://127.0.0.1:8001 npm run dev
        target: process.env.API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
