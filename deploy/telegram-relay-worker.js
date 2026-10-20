// Посредник для Telegram Bot API на Cloudflare Workers (бесплатный тариф).
//
// Нужен, только если с сервера закрыт api.telegram.org: бот и backend шлют
// запросы сюда, а Worker пересылает их в Telegram. Сайт и база остаются
// на своём сервере.
//
// Установка — DEPLOY.md, раздел «Если Telegram недоступен с сервера».
// В настройках Worker задайте переменную BOT_ID — число до двоеточия
// в токене бота (123456789 из 123456789:AA...). Чужие боты получат 404.

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Только методы нашего бота: /bot<BOT_ID>:<секрет>/<метод>
    if (!env.BOT_ID || !url.pathname.startsWith(`/bot${env.BOT_ID}:`)) {
      return new Response("Not found", { status: 404 });
    }

    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    return fetch(`https://api.telegram.org${url.pathname}${url.search}`, {
      method: request.method,
      headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
      body: hasBody ? request.body : undefined,
    });
  },
};
