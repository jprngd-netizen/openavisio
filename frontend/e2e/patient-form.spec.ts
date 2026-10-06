import { test, expect } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * CPF/contato/endereço do paciente pela interface.
 *
 * O CPF nunca volta inteiro: o DTO expõe só `cpf_last4`, então o formulário de
 * edição abre em branco com o valor mascarado no placeholder (mesmo contrato do
 * prescritor). A verificação do que foi gravado é feita pelo backend, não pela
 * tela.
 */
test.describe("Patient CPF and address", () => {
  test("cadastra e edita com CPF, contato e endereço", async ({ page, request }) => {
    await request.post(`${BACKEND}/api/dev/seed`);

    const loginRes = await request.post(`${BACKEND}/api/auth/login`, {
      data: { email: "admin@openavisio.dev", password: "Admin123!Admin" },
    });
    const token = (await loginRes.json()).access_token as string;
    expect(token).toBeTruthy();
    const auth = { Authorization: `Bearer ${token}` };

    const before = await (await request.get(`${BACKEND}/api/patients`, { headers: auth })).json();

    // ── Login pela UI ─────────────────────────────────────────────────────
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    // ── Criar com os campos novos ─────────────────────────────────────────
    await page.goto("/patients/new");
    await page.getByTestId("patient-given-name").fill("Zilda");
    await page.getByTestId("patient-family-name").fill("Endereco");
    await page.getByTestId("patient-cpf").fill("52998224725");
    await page.getByTestId("patient-cns").fill("123456789012345");
    await page.getByTestId("patient-cep").fill("27910-000");
    await page.getByTestId("patient-street").fill("Rua das Flores");
    await page.getByTestId("patient-city").fill("Macae");
    await page.getByTestId("patient-state").selectOption("RJ");
    await page.getByTestId("patient-submit").click();

    await expect(page).toHaveURL(/\/patients\/[0-9a-f-]{36}$/);

    // Verificação independente da UI.
    const after = await (await request.get(`${BACKEND}/api/patients`, { headers: auth })).json();
    expect(after.length).toBe(before.length + 1);
    const created = after.find((p: any) => !before.some((b: any) => b.id === p.id));
    expect(created?.cpf_last4).toBe("4725");
    expect(created?.cns).toBe("123456789012345");
    expect(created?.cep).toBe("27910-000");
    expect(created?.city_name).toBe("Macae");
    expect(created?.state_code).toBe("RJ");
    // O CPF inteiro não pode transitar de volta.
    expect(JSON.stringify(created)).not.toContain("52998224725");

    // ── Editar: CPF em branco + máscara; o resto muda e persiste ──────────
    await page.goto(`/patients/${created.id}/edit`);
    const cpfInput = page.getByTestId("patient-cpf");
    await expect(cpfInput).toHaveValue("");
    await expect(cpfInput).toHaveAttribute("placeholder", /4725/);
    await expect(page.getByTestId("patient-city")).toHaveValue("Macae");

    await page.getByTestId("patient-street").fill("Rua Nova");
    await page.getByTestId("patient-city").fill("Campos");
    await page.getByTestId("patient-submit").click();
    await expect(page).toHaveURL(new RegExp(`/patients/${created.id}$`));

    const updated = await (await request.get(`${BACKEND}/api/patients`, { headers: auth })).json();
    const row = updated.find((p: any) => p.id === created.id);
    expect(row?.street).toBe("Rua Nova");
    expect(row?.city_name).toBe("Campos");
    expect(row?.cpf_last4).toBe("4725"); // em branco preserva o CPF existente
  });
});