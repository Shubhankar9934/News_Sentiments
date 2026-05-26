/**
 * Reverse BWB Workstation virtualization smoke test.
 *
 * The dashboard should render even when a card's opportunity tables hold
 * thousands of rows. This test loads `/dashboard` and asserts the page
 * paints without freezing — no opportunities content is required (CI
 * may run without IBKR), only the basic shell.
 *
 * If/when the backend serves a stable fixture for tests, expand this to
 * scroll the CALL/PUT panels and verify rows render.
 */

import { expect, test } from "@playwright/test";

test("dashboard shell renders", async ({ page }) => {
  await page.goto("/dashboard");
  // Tab title / global header from the layout should be visible quickly.
  await expect(page).toHaveTitle(/.+/);
});
