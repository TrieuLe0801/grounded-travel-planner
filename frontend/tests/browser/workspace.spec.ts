import { expect, test, type Page } from "@playwright/test";

const plan = {
  destination: "Hà Nội",
  start_date: "2026-12-01",
  day_count: 1,
  revision: 1,
  summary: "Một ngày tham quan trung tâm thành phố.",
  entries: [{
    id: "stop-1",
    day_index: 1,
    start_time: "09:00",
    end_time: "10:30",
    place: {
      name: "Văn Miếu",
      description: "Điểm tham quan văn hóa.",
      visit_minutes_estimate: 90,
      travel_minutes_estimate: 20,
      opening_hours_verified: false,
      source_references: [{ title: "Nguồn kiểm thử", url: "https://example.com/source" }],
    },
  }],
};
const photo = {
  image_url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='180'%3E%3Crect width='320' height='180' fill='%23dbeafe'/%3E%3C/svg%3E",
  image_page_url: "https://example.com/photo",
  image_alt: "Ảnh kiểm thử Văn Miếu",
  image_credit: "Test creator",
  image_license: "CC BY 4.0",
};

async function mockWorkspace(page: Page, options: { withPlan?: boolean; admin?: boolean; language?: "vi" | "en" } = {}) {
  const language = options.language ?? "vi";
  const session = {
    language,
    plan: options.withPlan ? plan : null,
    pending: false,
    response: null,
    conversation: [],
    visuals_by_entry: options.withPlan ? { "stop-1": photo } : {},
  };
  await page.route("**/api/auth/me", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      authenticated: true,
      user_id: "test-user",
      email: "traveler@example.com",
      csrf_token: "test-csrf",
      access_status: "active",
      is_admin: options.admin ?? false,
      login_methods: ["google"],
    }),
  }));
  await page.route("**/api/session", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(session) }));
  await page.route("**/api/saved-tours?*", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ items: [{
      id: "saved-1", title: "Hà Nội một ngày", destination: "Hà Nội",
      start_date: plan.start_date, day_count: 1, revision: 1,
      saved_at: "2026-11-19T08:00:00Z",
    }], has_more: false, next_cursor: null }),
  }));
  await page.route("**/api/admin/users?*", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ items: [{
      id: "other-user", email: "other@example.com", created_at: "2026-11-18T08:00:00Z",
      access_status: "active", is_admin: false, input_tokens: 12,
      output_tokens: 6, estimated_cost_usd: null,
    }], usage_available: true, has_more: false, next_cursor: null }),
  }));
}

test("authenticated planner accepts ordinary chat before a plan", async ({ page }) => {
  await mockWorkspace(page);
  await page.route("**/api/turns", (route) => route.fulfill({ contentType: "application/json", body: '{"accepted":true}' }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Lập lịch tham quan/ })).toBeVisible();
  await expect(page.getByLabel("Điểm đến")).toBeEnabled();
  await page.getByRole("button", { name: "Mở cửa sổ chat" }).click();
  await expect(page.getByText("Bạn có thể hỏi về chuyến đi ngay.", { exact: false })).toBeVisible();
  const request = page.waitForRequest((candidate) => candidate.url().endsWith("/api/turns") && candidate.method() === "POST");
  await page.getByRole("textbox", { name: "Yêu cầu thay đổi lịch trình" }).fill("Gợi ý cách đi lại trong thành phố?");
  await page.getByRole("button", { name: "Gửi" }).click();
  expect((await request).postDataJSON()).toEqual({ message: "Gợi ý cách đi lại trong thành phố?" });
});

test("plan keeps source and estimates visible and chat offers edit examples", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true });
  await page.goto("/");
  await expect(page.getByLabel("Điểm đến")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Tạo lịch trình" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Chuyến đi mới" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Văn Miếu" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Nguồn kiểm thử/ })).toHaveAttribute("href", "https://example.com/source");
  await expect(page.getByText(/~90/)).toBeVisible();
  await expect(page.getByText(/chưa xác minh/)).toBeVisible();
  await expect(page.getByText(/Test creator · CC BY 4.0/)).toBeVisible();
  await expect(page.getByRole("link", { name: "nguồn ảnh" })).toHaveAttribute("href", "https://example.com/photo");
  await page.getByRole("button", { name: "Mở cửa sổ chat" }).click();
  await expect(page.getByRole("button", { name: "Đổi thứ tự hai điểm tham quan" })).toBeVisible();
});

test("new trip returns to setup after confirming plan reset", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true });
  await page.route("**/api/session/reset", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ language: "vi", plan: null, pending: false, response: null, conversation: [] }),
  }));
  await page.goto("/");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Chuyến đi mới" }).click();
  await expect(page.getByLabel("Điểm đến")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tạo lịch trình" })).toBeVisible();
});

test("saved tours, profile and admin keep authenticated navigation", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true, admin: true });
  await page.goto("/?view=saved");
  await expect(page.getByRole("heading", { name: "Tour đã lưu" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Hà Nội một ngày/ })).toBeVisible();
  await page.goto("/?view=profile");
  await expect(page.getByRole("heading", { name: "Thông tin cá nhân" })).toBeVisible();
  await expect(page.locator("dd", { hasText: "traveler@example.com" })).toBeVisible();
  await page.goto("/?view=admin");
  await expect(page.getByRole("heading", { name: "Quản lý người dùng" })).toBeVisible();
  await expect(page.getByText("other@example.com")).toBeVisible();
});

test("desktop header keeps chat available outside admin", async ({ page }) => {
  await mockWorkspace(page, { admin: true });
  await page.setViewportSize({ width: 1024, height: 900 });
  const headerChat = page.locator("header button[aria-controls='chat-panel']");
  await page.goto("/?view=saved");
  await expect(headerChat).toBeVisible();
  await page.goto("/?view=profile");
  await expect(headerChat).toBeVisible();
  await page.goto("/?view=admin");
  await expect(headerChat).toBeHidden();
});

test("workspace layout fits representative widths with reduced motion", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "One browser project captures all target widths");
  await mockWorkspace(page, { withPlan: true, admin: true, language: "en" });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Văn Miếu" })).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator(".rise").first()).toHaveCSS("animation-name", "none");
    if (width === 390) {
      const chat = await page.getByRole("button", { name: "Open chat" }).boundingBox();
      const save = await page.getByRole("button", { name: "Save tour", exact: true }).boundingBox();
      expect(chat).not.toBeNull();
      expect(save).not.toBeNull();
      const overlapX = Math.min(save!.x + save!.width, chat!.x + chat!.width) - Math.max(save!.x, chat!.x);
      const overlapY = Math.min(save!.y + save!.height, chat!.y + chat!.height) - Math.max(save!.y, chat!.y);
      expect(overlapX <= 0 || overlapY <= 0, "chat launcher must not cover the save action").toBe(true);
      await expect(page.locator("button.fixed[aria-controls='chat-panel']")).toBeVisible();
    }
    if (width === 768) {
      const save = await page.getByRole("button", { name: "Save tour", exact: true }).boundingBox();
      const chat = await page.getByRole("button", { name: "Open chat" }).boundingBox();
      expect(save).not.toBeNull();
      expect(chat).not.toBeNull();
      const overlapX = Math.min(save!.x + save!.width, chat!.x + chat!.width) - Math.max(save!.x, chat!.x);
      const overlapY = Math.min(save!.y + save!.height, chat!.y + chat!.height) - Math.max(save!.y, chat!.y);
      expect(overlapX <= 0 || overlapY <= 0, "chat launcher must not cover the save action").toBe(true);
    }
    if (width === 1024) {
      await expect(page.locator("header button[aria-controls='chat-panel']")).toBeVisible();
      await expect(page.locator("button.fixed[aria-controls='chat-panel']")).toBeHidden();
      await expect(page.getByRole("heading", { name: "Day 1" })).toBeVisible();
    }
    if (width === 1440) {
      const day = await page.getByRole("heading", { name: "Day 1" }).locator("xpath=..").boundingBox();
      const photo = await page.getByRole("img", { name: "Ảnh kiểm thử Văn Miếu" }).boundingBox();
      const place = await page.getByRole("heading", { name: "Văn Miếu" }).boundingBox();
      expect(day).not.toBeNull();
      expect(photo).not.toBeNull();
      expect(place).not.toBeNull();
      expect(day!.width).toBeGreaterThan(1000);
      expect(photo!.x).toBeGreaterThan(place!.x + place!.width);
    }
    await page.screenshot({ path: testInfo.outputPath(`workspace-${width}.png`), fullPage: true });
  }
});

test("Vietnamese create action stays clear of chat launcher at phone width", async ({ page }, testInfo) => {
  await mockWorkspace(page, { language: "vi" });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto("/");
  const create = await page.getByRole("button", { name: "Tạo lịch trình" }).boundingBox();
  const chat = await page.getByRole("button", { name: "Mở cửa sổ chat" }).boundingBox();
  expect(create).not.toBeNull();
  expect(chat).not.toBeNull();
  const overlapX = Math.min(create!.x + create!.width, chat!.x + chat!.width) - Math.max(create!.x, chat!.x);
  const overlapY = Math.min(create!.y + create!.height, chat!.y + chat!.height) - Math.max(create!.y, chat!.y);
  expect(overlapX <= 0 || overlapY <= 0, "chat launcher must not cover the Vietnamese create action").toBe(true);
  await page.screenshot({ path: testInfo.outputPath("workspace-390-vi.png"), fullPage: true });
});
