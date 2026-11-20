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

async function mockWorkspace(page: Page, options: { withPlan?: boolean; admin?: boolean; language?: "vi" | "en"; dayCount?: number; withPhoto?: boolean; pending?: boolean } = {}) {
  const language = options.language ?? "vi";
  const session = {
    language,
    plan: options.withPlan ? { ...plan, day_count: options.dayCount ?? plan.day_count } : null,
    pending: options.pending ?? false,
    response: null,
    conversation: [],
    visuals_by_entry: options.withPlan && options.withPhoto !== false ? { "stop-1": photo } : {},
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

test("a later itinerary request clears the previous snapshot save notice", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true });
  await page.route("**/api/saved-tours", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      id: "saved-current", title: "Hà Nội", destination: "Hà Nội",
      start_date: plan.start_date, day_count: 1, revision: 1,
      saved_at: "2026-11-20T08:00:00Z", plan,
    }),
  }));
  await page.route("**/api/turns", (route) => route.fulfill({
    contentType: "application/json", body: '{"accepted":true}',
  }));
  await page.goto("/");
  await page.getByRole("button", { name: "Lưu tour", exact: true }).click();
  await expect(page.getByRole("status").getByText("Đã lưu tour.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Mở cửa sổ chat" }).click();
  await page.getByRole("textbox", { name: "Yêu cầu thay đổi lịch trình" }).fill("Đổi thời gian tham quan.");
  await page.getByRole("button", { name: "Gửi" }).click();
  await expect(page.getByRole("status").getByText("Đã lưu tour.", { exact: false })).toHaveCount(0);
});

test("one-day itinerary has no day links and renders the English singular unit", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true, language: "en" });
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Navigate itinerary by day" })).toHaveCount(0);
  await expect(page.getByText(/December 1, 2026\s*·\s*1 day/)).toBeVisible();
});

test("multi-day itinerary links navigate to the last day by keyboard", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true, dayCount: 7 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Điều hướng lịch trình theo ngày" });
  await expect(nav.getByRole("link")).toHaveCount(7);
  const lastDayLink = nav.getByRole("link", { name: "Ngày 7" });
  await lastDayLink.focus();
  await lastDayLink.press("Enter");
  await expect(page).toHaveURL(/#itinerary-day-7$/);
  await expect(page.locator("#itinerary-day-7")).toBeInViewport();
});

test("language switch keeps the current plan and pending turn", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true, pending: true });
  await page.route("**/api/session/language", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({
      language: "en", plan, pending: true, response: null,
      conversation: [{ role: "user", content: "Giữ nguyên lượt đang chạy." }],
      visuals_by_entry: { "stop-1": photo },
    }),
  }));
  await page.goto("/");
  await page.getByRole("button", { name: "Mở cửa sổ chat" }).click();
  await expect(page.getByText("Đang kiểm tra yêu cầu…")).toBeVisible();
  await page.getByRole("button", { name: "Chuyển sang tiếng Anh" }).click();
  await expect(page.getByRole("heading", { name: "Văn Miếu" })).toBeVisible();
  await expect(page.getByText("Giữ nguyên lượt đang chạy.")).toBeVisible();
  await expect(page.getByText("Checking your request…")).toBeVisible();
});

test("missing photo uses a compact fallback while source information remains", async ({ page }) => {
  await mockWorkspace(page, { withPlan: true, withPhoto: false });
  await page.goto("/");
  await expect(page.getByText("Chưa tìm được ảnh có giấy phép cho Văn Miếu.")).toBeVisible();
  await expect(page.getByRole("link", { name: /Nguồn kiểm thử/ })).toBeVisible();
  await expect(page.locator("#itinerary-day-1 .aspect-\\[16\\/9\\]")).toHaveCount(0);
});

test("language and calendar controls meet the 44px touch target", async ({ page }) => {
  await mockWorkspace(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const language = page.getByRole("button", { name: "Chuyển sang tiếng Anh" });
  await expect(language).toBeVisible();
  expect((await language.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  await page.getByRole("button", { name: "Chuyển sang tiếng Việt" }).click();
  await page.getByRole("button", { name: "Ngày bắt đầu" }).click();
  const calendar = page.getByRole("dialog", { name: "Ngày bắt đầu" });
  await expect(calendar).toBeVisible();
  const controls = await calendar.getByRole("button").all();
  for (const control of controls) {
    expect((await control.boundingBox())?.height).toBeGreaterThanOrEqual(44);
  }
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

test("saved snapshot remains read-only and chat retains keyboard access", async ({ page }, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockWorkspace(page, { withPlan: true });
  await page.route("**/api/saved-tours/saved-1", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ id: "saved-1", title: "Hà Nội một ngày", plan, visuals_by_entry: { "stop-1": photo } }),
  }));
  const widths = testInfo.project.name === "chromium" ? [390, 768, 1024, 1440] : [390];
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?view=saved");
    await page.getByRole("button", { name: /^Hà Nội một ngày/ }).click();
    await expect(page.getByText("Bản lưu đã xác nhận", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Lưu tour", exact: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Nguồn kiểm thử/ })).toBeVisible();
    await expect(page.getByText(/Test creator · CC BY 4.0/)).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`saved-${width}.png`), fullPage: true });
    await page.getByRole("button", { name: "Mở cửa sổ chat" }).click();
    const input = page.getByRole("textbox", { name: "Yêu cầu thay đổi lịch trình" });
    await expect(input).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath(`chat-${width}.png`) });
    await input.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  }
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
