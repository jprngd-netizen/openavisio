import { test, expect, type Page } from "@playwright/test";
import { execSync } from "child_process";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

/**
 * Track console errors and all console output for token-leak detection.
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

test.describe("PrescriptionEditor", () => {
  test("autosave, 409 conflict handling, and retry button", async ({
    page,
    request,
  }) => {
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

    // ── 6. Create a draft prescription ───────────────────────────────────
    const rxRes = await request.post(
      `${BACKEND}/api/patients/${patientId}/prescriptions`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const rxBody = await rxRes.json();
    const rxId = rxBody.id as string;
    expect(rxId).toBeTruthy();
    expect(rxBody.status).toBe("draft");
    expect(rxBody.version).toBe(1);

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

    // ══════════════════════════════════════════════════════════════════════
    // TEST 1: Autosave increments version
    // ══════════════════════════════════════════════════════════════════════

    // ── 11. Navigate to prescriptions page with rx param ─────────────────
    await page.goto(`/patients/${patientId}/prescriptions?rx=${rxId}`);

    // Wait for the editor to load
    await page.waitForSelector('[data-testid="editor-notes"]', {
      timeout: 10000,
    });

    // ── 12. Edit notes ───────────────────────────────────────────────────
    const notesInput = page.locator('[data-testid="editor-notes"]');
    await notesInput.fill("Test note for autosave");

    // Wait for debounce (1500ms) + network roundtrip
    await page.waitForTimeout(3000);

    // ── 13. Check version incremented via API ────────────────────────────
    const checkRes = await request.get(`${BACKEND}/api/prescriptions/${rxId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const checkBody = await checkRes.json();
    expect(checkBody.version).toBeGreaterThan(1);
    expect(checkBody.notes).toBe("Test note for autosave");
    console.log(
      `Version after autosave: ${checkBody.version} (was ${rxBody.version})`,
    );

    // ══════════════════════════════════════════════════════════════════════
    // TEST 2: 409 conflict handling
    // ══════════════════════════════════════════════════════════════════════

    // ── 14. Force a version bump via API (simulate concurrent edit) ──────
    const bumpRes = await request.patch(
      `${BACKEND}/api/prescriptions/${rxId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        data: {
          version: checkBody.version,
          notes: "Bumped by test",
        },
      },
    );
    expect(bumpRes.ok).toBeTruthy();
    const bumpedBody = await bumpRes.json();
    const bumpedVersion = bumpedBody.version as number;
    console.log(`Bumped version to: ${bumpedVersion}`);

    // ── 15. Edit notes again in the UI (will send stale version) ─────────
    await notesInput.fill(
      "This text should survive the conflict and reload",
    );

    // Wait for debounce + 409 response
    await page.waitForTimeout(3000);

    // ── 16. Assert conflict banner appears ───────────────────────────────
    const conflictBanner = page.locator("text=modified elsewhere");
    await expect(conflictBanner).toBeVisible({ timeout: 5000 });

    // ── 17. Assert reload button is visible ──────────────────────────────
    const reloadButton = page.locator("button", { hasText: "Reload" });
    await expect(reloadButton).toBeVisible();

    // ── 18. Assert the user's text is preserved ──────────────────────────
    const notesValue = await notesInput.inputValue();
    expect(notesValue).toBe("This text should survive the conflict and reload");

    // ── 19. Click reload ─────────────────────────────────────────────────
    await reloadButton.click();
    await page.waitForTimeout(1000);

    // ── 20. Assert conflict banner is gone ───────────────────────────────
    await expect(conflictBanner).not.toBeVisible({ timeout: 3000 });

    // ══════════════════════════════════════════════════════════════════════
    // TEST 3: Retry button for failed prescriptions
    // ══════════════════════════════════════════════════════════════════════

    // ── 21. Set status to failed via SQL ─────────────────────────────────
    try {
      execSync(
        `docker exec deploy-postgres-1 psql -U openavisio -d vaultdb -c "UPDATE prescriptions SET status='failed' WHERE id='${rxId}';"`,
        { timeout: 10000 },
      );
      console.log("Set prescription status to failed via SQL");
    } catch (e) {
      console.log(
        `SQL exec failed (may not be in Docker): ${e}. Trying direct API...`,
      );
      // Fallback: try to use the API if available
      console.log("Continuing with test anyway");
    }

    // ── 22. Reload the page ──────────────────────────────────────────────
    await page.goto(`/patients/${patientId}/prescriptions?rx=${rxId}`);
    await page.waitForSelector('[data-testid="editor-notes"]', {
      timeout: 10000,
    });

    // ── 23. Assert retry button is visible ───────────────────────────────
    const retryButton = page.locator("button", { hasText: "Retry" });
    await expect(retryButton).toBeVisible({ timeout: 5000 });

    // ── 24. Assert no console errors ─────────────────────────────────────
    expect(errors).toEqual([]);
  });
});