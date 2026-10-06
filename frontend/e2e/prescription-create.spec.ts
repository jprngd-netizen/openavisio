import { test, expect } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * O fluxo que faltava: criar o rascunho PELA INTERFACE.
 *
 * A criação via API já era coberta em prescriptions.spec.ts; aqui o que se
 * testa é o gatilho da UI — botão "Nova receita" → POST do rascunho → abrir o
 * editor com ?rx=<id>. Sem isso o editor fica inalcançável (só abre com rx).
 */
test.describe("Prescription creation from the UI", () => {
  test("cria o rascunho pela UI e abre o editor", async ({ page, request }) => {
    await request.post(`${BACKEND}/api/dev/seed`);

    const loginRes = await request.post(`${BACKEND}/api/auth/login`, {
      data: { email: "admin@openavisio.dev", password: "Admin123!Admin" },
    });
    const token = (await loginRes.json()).access_token as string;
    expect(token).toBeTruthy();
    const auth = { Authorization: `Bearer ${token}` };

    const meBody = await (await request.get(`${BACKEND}/api/auth/me`, { headers: auth })).json();
    const prescriberRes = await request.put(`${BACKEND}/api/admin/prescriber`, {
      headers: auth,
      data: {
        given_name: "Admin",
        family_name: "User",
        cpf: "12345678909",
        birth_date: "1980-01-01",
        board_code: "CRM",
        board_number: "12345",
        board_state: "SP",
        user_id: meBody.id,
      },
    });
    expect(prescriberRes.ok).toBeTruthy();

    const patients = await (await request.get(`${BACKEND}/api/patients`, { headers: auth })).json();
    const patientId = patients[0].id as string;
    expect(patientId).toBeTruthy();

    const before = await (
      await request.get(`${BACKEND}/api/patients/${patientId}/prescriptions`, { headers: auth })
    ).json();

    // ── Login pela UI ────────────────────────────────────────────────────
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    // ── Seção Receitas: o botão tem que estar visível ────────────────────
    await page.goto(`/patients/${patientId}/prescriptions`);
    const button = page.getByTestId("new-prescription");
    await expect(button).toBeVisible();
    await expect(button).toContainText(/receita|prescription|Rezept/i);

    // ── Criar: abre o editor com ?rx=<id> ───────────────────────────────
    await button.click();
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/prescriptions\\?rx=`));

    // Verificação independente da UI: o rascunho existe de verdade no backend.
    const after = await (
      await request.get(`${BACKEND}/api/patients/${patientId}/prescriptions`, { headers: auth })
    ).json();
    expect(after.length).toBe(before.length + 1);
    const created = after.find((p: any) => !before.some((b: any) => b.id === p.id));
    expect(created?.status).toBe("draft");
    expect(page.url()).toContain(created.id);
  });
});
