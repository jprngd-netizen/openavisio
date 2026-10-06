import { test, expect, type Page } from "@playwright/test";

function monitorConsole(page: Page): [string[], string[]] {
  const errors: string[] = [];
  const allOutput: string[] = [];
  page.on("console", (msg) => {
    allOutput.push(msg.text());
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => allOutput.push(String(err)));
  return [errors, allOutput];
}

test.describe("Prescriber Admin", () => {
  test("create prescriber and show masked CPF", async ({ page }) => {
    const [errors, allOutput] = monitorConsole(page);

    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    await page.goto("/admin/prescriber");
    await expect(page.locator("h1")).toHaveText("Prescriber");

    await page.locator('input[placeholder="CRM"]').fill("CRM");
    await page.locator('input[placeholder="12345"]').fill("12345");
    await page.locator("select").first().selectOption("SP");

    const nameInputs = page.locator('input[type="text"]');
    await nameInputs.nth(0).fill("Admin");
    await nameInputs.nth(1).fill("User");
    await nameInputs.nth(2).fill("12345678909");

    await page.locator('input[type="date"]').fill("1980-01-01");

    const userSelect = page.locator("select").last();
    const userId = process.env.TEST_USER_ID || "";
    if (userId) await userSelect.selectOption(userId);

    await page.locator('button[type="submit"]').click();

    await expect(page.locator("text=***8909")).toBeVisible({ timeout: 10000 });

    const pageText = await page.locator("body").textContent();
    expect(pageText).not.toContain("12345678909");

    const cpfLeak = allOutput.filter((line) => line.includes("12345678909"));
    expect(cpfLeak).toEqual([]);

    expect(errors).toEqual([]);
  });

  test("missing required fields block submit on create", async ({ page }) => {
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    await page.goto("/admin/prescriber");

    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();

    await expect(page).toHaveURL(/\/admin\/prescriber/);
    await expect(page.locator("h1")).toHaveText("Prescriber");
  });

  test("update without CPF preserves existing value", async ({ page }) => {
    const [errors, allOutput] = monitorConsole(page);

    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    await page.goto("/admin/prescriber");

    await expect(page.locator("text=***8909")).toBeVisible({ timeout: 10000 });

    await page.locator('input[type="email"]').fill("updated@test.com");

    await page.locator('button[type="submit"]').click();

    await expect(page.locator("text=***8909")).toBeVisible({ timeout: 10000 });

    const pageText = await page.locator("body").textContent();
    expect(pageText).not.toContain("12345678909");

    const cpfLeak = allOutput.filter((line) => line.includes("12345678909"));
    expect(cpfLeak).toEqual([]);

    expect(errors).toEqual([]);
  });
});