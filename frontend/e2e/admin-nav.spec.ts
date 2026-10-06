import { test, expect } from "@playwright/test";

/**
 * O menu Admin tem que existir nas DUAS navegações.
 *
 * No mobile a barra inferior tem só Início/Pacientes/Mais, e o Admin vive na aba
 * "Mais". Era exatamente ali que o Prescritor tinha sumido: a rota existia e o
 * sidebar desktop a listava, mas no celular não havia link nenhum — a tela do
 * prescritor (e com ela a configuração de emissão) era inalcançável.
 *
 * Localizador por href de propósito: o rótulo muda com o idioma.
 */
const PRESCRIBER = 'a[href="/admin/prescriber"]';

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill("admin@openavisio.dev");
  await page.locator('input[type="password"]').fill("Admin123!Admin");
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/patients$/);
}

test.describe("Admin navigation", () => {
  test("no mobile, a aba Mais leva ao Prescritor", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);

    await page.getByRole("button", { name: /more|mais|mehr/i }).click();
    const link = page.locator(PRESCRIBER);
    await expect(link.first()).toBeVisible();

    await link.first().click();
    await expect(page).toHaveURL(/\/admin\/prescriber$/);
  });

  test("no desktop, o sidebar leva ao Prescritor", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);

    const link = page.locator(PRESCRIBER);
    await expect(link.first()).toBeVisible();
    await link.first().click();
    await expect(page).toHaveURL(/\/admin\/prescriber$/);
  });
});