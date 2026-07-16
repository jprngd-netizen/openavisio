import { test, expect, type Page } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

// The bug class this suite exists for (hydration mismatch, a theme script eating
// React's meta tags) renders a dead page while every HTTP status stays 200. It is
// only ever visible in the console. So: any console error fails the test.
function failOnConsoleErrors(page: Page) {
  const errors: string[] = [];
  // echoed as they happen, not just asserted at the end: when the test dies on a
  // timeout instead, the assertion never runs and the console is all you have.
  const record = (text: string) => {
    console.log(`[browser] ${text}`);
    errors.push(text);
  };
  page.on("console", (msg) => msg.type() === "error" && record(msg.text()));
  page.on("pageerror", (err) => record(String(err)));
  return errors;
}

test("login, open a patient, and keep navigating", async ({ page, request }) => {
  // dev-only endpoint: admin@openavisio.dev + a Demo Patient with an explicit
  // grant (the admin *role* confers no clinical access — ADR 025).
  await request.post(`${BACKEND}/api/dev/seed`);
  const errors = failOnConsoleErrors(page);

  await page.goto("/login");
  await page.locator('input[type="email"]').fill("admin@openavisio.dev");
  await page.locator('input[type="password"]').fill("Admin123!Admin");
  await page.locator('button[type="submit"]').click();

  await expect(page).toHaveURL(/\/patients$/);
  await page.getByRole("link", { name: /Demo Patient/ }).click();
  await expect(page.getByRole("heading", { name: "Demo Patient" })).toBeVisible();

  // The second click is the actual test: a <div> in a <ul>, a stray loading.tsx —
  // each of those broke *this* click while the first one still worked.
  await page.locator('a[href="/settings"]').first().click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

  expect(errors).toEqual([]);
});
