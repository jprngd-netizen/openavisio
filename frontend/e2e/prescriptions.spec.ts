import { test, expect, type Page } from "@playwright/test";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * Track console errors and all console output for token-leak detection.
 * Returns [errors, allOutput] so the test can assert both.
 */
function monitorConsole(page: Page): [string[], string[]] {
  const errors: string[] = [];
  const allOutput: string[] = [];
  const record = (text: string) => {
    console.log(`[browser] ${text}`);
    allOutput.push(text);
  };
  page.on("console", (msg) => {
    record(msg.text());
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => record(String(err)));
  return [errors, allOutput];
}

test.describe("Prescriptions", () => {
  test("Memed postMessage bridge end-to-end with fake backend", async ({ page, request }) => {
    // ── 1. Seed ──────────────────────────────────────────────────────────
    await request.post(`${BACKEND}/api/dev/seed`);

    // ── 2. Login via API to get Bearer token ─────────────────────────────
    const loginRes = await request.post(`${BACKEND}/api/auth/login`, {
      data: { email: "admin@openavisio.dev", password: "Admin123!Admin" },
    });
    const loginBody = await loginRes.json();
    const token = loginBody.access_token as string;
    expect(token).toBeTruthy();

    // ── 3. Get admin user id ─────────────────────────────────────────────
    const meRes = await request.get(`${BACKEND}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const meBody = await meRes.json();
    const userId = meBody.id as string;
    expect(userId).toBeTruthy();

    // ── 4. Configure prescriber ──────────────────────────────────────────
    const prescriberRes = await request.put(`${BACKEND}/api/admin/prescriber`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        given_name: "Admin",
        family_name: "User",
        cpf: "12345678909",
        birth_date: "1980-01-01",
        board_code: "CRM",
        board_number: "12345",
        board_state: "SP",
        user_id: userId,
      },
    });
    expect(prescriberRes.ok).toBeTruthy();

    // ── 5. Get first patient ─────────────────────────────────────────────
    const patientsRes = await request.get(`${BACKEND}/api/patients`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const patients = await patientsRes.json();
    const patientId = patients[0].id as string;
    expect(patientId).toBeTruthy();

    // ── 6. Create a prescription ─────────────────────────────────────────
    const rxRes = await request.post(
      `${BACKEND}/api/patients/${patientId}/prescriptions`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const rxBody = await rxRes.json();
    const rxId = rxBody.id as string;
    expect(rxId).toBeTruthy();
    expect(rxBody.status).toBe("draft");

    // ── 7. Monitor console ───────────────────────────────────────────────
    const [errors, allOutput] = monitorConsole(page);

    // ── 8. Stub the Memed script URL ─────────────────────────────────────
    await page.route("**/sinapse-prescricao*.js", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: "window.MdSinapsePrescricao = {};",
      });
    });

    // ── 9. Set up MdHub mock via addInitScript ───────────────────────────
    await page.addInitScript(() => {
      const calls: string[] = [];
      const handlers: Record<string, (...args: unknown[]) => void> = {};

      (window as any).__memedCalls = calls;
      (window as any).__memedHandlers = handlers;

      (window as any).MdHub = {
        command: {
          send: (module: string, command: string, ...args: unknown[]) => {
            calls.push(`${module}.${command}`);
          },
        },
        event: {
          add: (event: string, handler: (...args: unknown[]) => void) => {
            handlers[event] = handler;
          },
        },
      };
    });

    // ── 10. Login via UI ─────────────────────────────────────────────────
    await page.goto("/login");
    await page.locator('input[type="email"]').fill("admin@openavisio.dev");
    await page.locator('input[type="password"]').fill("Admin123!Admin");
    await page.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/\/patients$/);

    // ── 11. Navigate to prescriptions page with rx param ─────────────────
    await page.goto(`/patients/${patientId}/prescriptions?rx=${rxId}`);

    // Wait for the Memed container to render (session loads via fake backend)
    await page.waitForSelector("#memed-container", { timeout: 10000 });

    // ── 12. Fire core:moduleInit event ───────────────────────────────────
    await page.evaluate(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: {
            type: "core:moduleInit",
            module: { name: "plataforma.prescricao" },
          },
        }),
      );
    });

    // Wait for the event to be processed
    await page.waitForTimeout(1000);

    // ── 13. Assert setPaciente and show were called ──────────────────────
    const calls = await page.evaluate(() => (window as any).__memedCalls);
    console.log(`MdHub calls after core:moduleInit: ${JSON.stringify(calls)}`);

    expect(calls).toContain("plataforma.prescricao.setPaciente");
    expect(calls).toContain("plataforma.prescricao.show");

    // ── 14. Fire prescricaoImpressa handler ──────────────────────────────
    const hasHandler = await page.evaluate(
      () =>
        typeof (window as any).__memedHandlers?.prescricaoImpressa !==
        "undefined",
    );
    expect(hasHandler).toBe(true);

    await page.evaluate(() => {
      const h = (window as any).__memedHandlers.prescricaoImpressa;
      if (h) h({ prescription_id: "memed-123", signed: true });
    });

    // ── 15. Poll backend until status === "issued" ───────────────────────
    let issued = false;
    for (let i = 0; i < 20; i++) {
      await page.waitForTimeout(500);
      const checkRes = await request.get(
        `${BACKEND}/api/prescriptions/${rxId}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const checkBody = await checkRes.json();
      if (checkBody.status === "issued") {
        issued = true;
        console.log(`Prescription issued after ${(i + 1) * 500}ms`);
        break;
      }
    }
    expect(issued).toBe(true);

    // ── 16. Assert data_token never appears in console output ────────────
    const tokenLeak = allOutput.filter(
      (line) => line.includes("fake-token-001"),
    );
    expect(tokenLeak).toEqual([]);

    // ── 17. Assert no console errors ─────────────────────────────────────
    expect(errors).toEqual([]);
  });
});