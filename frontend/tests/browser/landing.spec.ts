import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"authenticated":false}' }),
  );
});

test("public guide follows the selected language", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("lang", "vi-VN");
  await expect(page.locator("#how-to-use h3")).toHaveCount(5);
  await page.getByRole("button", { name: "Chuyển sang tiếng Anh" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-US");
  await expect(page.getByRole("heading", { name: "Use the planner in 5 steps" })).toBeVisible();
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
