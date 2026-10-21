import { expect, test, type Page } from "@playwright/test";

// Тестовый админ из backend/seed_e2e.py
const ADMIN_EMAIL = "admin@e2e.test";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "e2e-admin-pass";

// Свой номер на каждый запуск — база между запусками не очищается
const phone = `+7999${String(Date.now()).slice(-7)}`;
let orderNumber = "";

async function addBoardToCart(page: Page) {
  await page.goto("/");
  await page.getByLabel("Поиск по каталогу").fill("доски 50х150");
  await page.getByLabel("Поиск по каталогу").press("Enter");
  await expect(page).toHaveURL(/\/catalog\?q=/);

  await page.getByRole("link", { name: "Доска обрезная 50×150×6000" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Доска обрезная 50×150×6000");
  // Количество вписывается вручную
  await page.getByLabel("Количество", { exact: true }).fill("2");
  await page.getByLabel("Количество", { exact: true }).press("Enter");
  await expect(page.getByRole("button", { name: /^В корзину · 1\s240/ })).toBeVisible();
  await page.getByRole("button", { name: /^В корзину · / }).click();
  await page.getByRole("button", { name: "Открыть корзину", exact: true }).click();
}

test.describe.serial("покупка и обработка заказа", () => {
  test("покупатель находит доску, регистрируется и оформляет самовывоз", async ({ page }) => {
    await addBoardToCart(page);
    await page.getByRole("button", { name: "Оформить заказ" }).click();

    await page.getByRole("button", { name: "Регистрация" }).click();
    await page.getByLabel("Номер телефона").fill(phone);
    await page.getByLabel("Пароль").fill("e2e-customer-pass");
    await page.getByRole("checkbox").check();
    await page.getByLabel("Как к вам обращаться?").fill("Тест Покупатель");
    await page.getByRole("radio", { name: /Самовывоз/ }).click();
    await page.getByRole("button", { name: "Зарегистрироваться и заказать" }).click();

    await expect(page.getByRole("heading", { name: "Спасибо за заказ!" })).toBeVisible();
    orderNumber = (await page.getByText(/^#\d+$/).innerText()).slice(1);
    expect(Number(orderNumber)).toBeGreaterThan(0);

    await page.getByRole("button", { name: "Перейти к моим заказам" }).click();
    await expect(page.getByText(`№${orderNumber}`).first()).toBeVisible();
  });

  test("администратор подтверждает заказ", async ({ page }) => {
    await page.goto("/admin");
    await page.getByLabel("Почта или номер телефона").fill(ADMIN_EMAIL);
    await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.getByRole("heading", { name: "Управление магазином" })).toBeVisible();

    await page.getByRole("link", { name: /Заказы/ }).click();
    const card = page.locator(".admin-order-card").filter({ hasText: `Заказ №${orderNumber}` });
    await expect(card).toContainText("Новый");
    await expect(card).toContainText("Самовывоз");

    await card.getByRole("button", { name: "Подтвердить заказ" }).click();
    await expect(card.locator(".admin-status").first()).toHaveText("Подтверждён");
  });
});

test("у страницы свой заголовок во вкладке", async ({ page }) => {
  await page.goto("/delivery");
  await expect(page).toHaveTitle(/Доставка и возврат/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Доставка и возврат");
});

test("товар убирается из корзины кнопкой и вводом нуля", async ({ page }) => {
  await page.goto("/catalog?q=брус");
  await page.getByRole("link", { name: "Брус 100×100×6000" }).click();
  await page.getByLabel("Количество", { exact: true }).fill("30");
  await page.getByLabel("Количество", { exact: true }).press("Enter");
  await page.getByRole("button", { name: /^В корзину · / }).click();
  await page.getByRole("button", { name: "Открыть корзину", exact: true }).click();

  const item = page.locator(".cart-item");
  await expect(item.getByLabel("Количество", { exact: true })).toHaveValue("30");
  // 30 штук — одним нажатием, а не тридцатью
  await item.getByRole("button", { name: /^Удалить .* из корзины$/ }).click();
  await expect(page.getByRole("heading", { name: "Пока здесь пусто" })).toBeVisible();

  await page.getByRole("button", { name: "Закрыть корзину" }).click();
  await page.getByRole("button", { name: /^В корзину · / }).click();
  await page.getByRole("button", { name: "Открыть корзину", exact: true }).click();
  await item.getByLabel("Количество", { exact: true }).fill("0");
  await item.getByLabel("Количество", { exact: true }).press("Enter");
  await expect(page.getByRole("heading", { name: "Пока здесь пусто" })).toBeVisible();
});

test("гость оставляет заявку без регистрации, админ перезванивает", async ({ page }) => {
  const guestPhone = `+7998${String(Date.now()).slice(-7)}`;
  await addBoardToCart(page);
  await page.getByRole("button", { name: "Оформить заказ" }).click();
  await page.getByRole("button", { name: /перезвоните мне/ }).click();
  await page.getByLabel("Как к вам обращаться?").fill("Гость Тестовый");
  await page.getByLabel("Номер телефона").fill(guestPhone);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Жду звонка" }).click();
  await expect(page.getByRole("heading", { name: "Перезвоним!" })).toBeVisible();

  await page.goto("/admin");
  await page.getByLabel("Почта или номер телефона").fill(ADMIN_EMAIL);
  await page.getByLabel("Пароль").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Войти" }).click();
  await page.getByRole("link", { name: /Заказы/ }).click();
  const request = page.locator(".admin-callback").filter({ hasText: guestPhone });
  await expect(request).toContainText("Доска обрезная 50×150×6000");
  await request.getByRole("button", { name: "Перезвонили" }).click();
  await expect(request).toHaveCount(0);
});
