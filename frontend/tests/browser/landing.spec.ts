import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"authenticated":false}' }),
  );
});

test("public guide follows the selected language", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "vi-VN");
  await expect(page.locator("#how-to-use h3")).toHaveCount(5);
  await page.getByRole("button", { name: "Chuyển sang tiếng Anh" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
  await expect(page.getByRole("heading", { name: "Use the planner in 5 steps" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("landing-en.png"), fullPage: true });
});

test("remember login is opt-in for every direct account action", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/auth/login?**", (route) => route.fulfill({ status: 204 }));
  const actions = [
    ["Tiếp tục với Google", "google"],
    ["Đăng nhập bằng email và mật khẩu", "email"],
    ["Đăng ký bằng email", "signup"],
    ["Đăng nhập bằng mã email", "otp"],
  ] as const;
  for (const [label, intent] of actions) {
    await page.goto("/");
    const remember = page.getByRole("checkbox", { name: "Giữ đăng nhập trên thiết bị này" });
    await expect(remember).not.toBeChecked();
    const ordinary = page.waitForRequest((request) => request.url().includes("/api/auth/login?"));
    await page.getByRole("button", { name: label }).click();
    const ordinaryUrl = new URL((await ordinary).url());
    expect(ordinaryUrl.searchParams.get("intent")).toBe(intent);
    expect(ordinaryUrl.searchParams.has("remember_login")).toBe(false);

    await page.goto("/");
    await remember.check();
    const persistent = page.waitForRequest((request) => request.url().includes("/api/auth/login?"));
    await page.getByRole("button", { name: label }).click();
    const persistentUrl = new URL((await persistent).url());
    expect(persistentUrl.searchParams.get("intent")).toBe(intent);
    expect(persistentUrl.searchParams.get("remember_login")).toBe("true");
  }
  await page.goto("/");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Chuyển sang tiếng Anh" }).click();
  await expect(page.getByRole("checkbox", { name: "Keep me signed in on this device" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("remember-login-en-390.png"), fullPage: true });
});

test("authenticated open tab rechecks login before persistent cookie ages out", async ({ page }) => {
  await page.clock.install();
  let authChecks = 0;
  await page.route("**/api/auth/me", (route) => {
    authChecks += 1;
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        user_id: "test-user",
        email: "traveler@example.test",
        csrf_token: "test-csrf",
        access_status: "active",
        is_admin: false,
        login_methods: ["google"],
      }),
    });
  });
  await page.route("**/api/session", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ language: "vi", plan: null, pending: false, response: null, conversation: [] }),
  }));
  await page.goto("/");
  await expect(page.getByLabel("Điểm đến")).toBeVisible();
  const initialChecks = authChecks;
  expect(initialChecks).toBeGreaterThanOrEqual(1);
  await page.clock.fastForward(24 * 60 * 60 * 1000);
  await expect.poll(() => authChecks).toBeGreaterThan(initialChecks);
  await expect(page.getByLabel("Điểm đến")).toBeVisible();
});

test("primary sign-in action is visible in the first phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const primaryAction = page.getByRole("button", { name: "Tiếp tục với Google" });
  await expect(primaryAction).toBeVisible();
  const bounds = await primaryAction.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844);
  expect(await page.getByRole("button", { name: "Chuyển sang tiếng Anh" }).evaluate((button) => button.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
});

test("public guide fits the viewport and respects reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("#how-to-use h3")).toHaveCount(5);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.locator(".guide-art-mark").first()).toHaveCSS("animation-name", "none");
});

test("public landing layout at phone, tablet and desktop widths", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "One browser project captures all target widths");
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.locator("#how-to-use h3")).toHaveCount(5);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (width === 1440) {
      const guide = await page.locator("#how-to-use").boundingBox();
      const cards = await page.locator("#how-to-use li").all();
      const positions = await Promise.all(cards.map((card) => card.boundingBox()));
      expect(guide).not.toBeNull();
      expect(guide!.y).toBeLessThan(900);
      expect(positions[0]?.y).toBe(positions[1]?.y);
      expect(positions[1]?.y).toBe(positions[2]?.y);
      expect(positions[3]!.y).toBeGreaterThan(positions[2]!.y);
    }
    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true });
  }
});
