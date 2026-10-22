import { expect, test } from "@playwright/test";

test("баннер cookie: выбор запоминается и меняется из подвала", async ({ page }) => {
  await page.goto("/");
  const banner = page.getByRole("dialog", { name: "Файлы cookie" });
  await expect(banner).toBeVisible();

  await banner.getByRole("button", { name: "Только необходимые" }).click();
  await expect(banner).toBeHidden();
  await page.reload();
  await expect(banner).toBeHidden();

  await page.getByRole("button", { name: "Настройки cookie" }).click();
  await expect(banner).toBeVisible();
  await banner.getByRole("button", { name: "Принять" }).click();
  await expect(banner).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem("wood_commerce_cookie_choice"))).toBe("accepted");
});
