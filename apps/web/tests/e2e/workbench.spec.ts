import { test, expect } from "@playwright/test";
import path from "node:path";

const validGedcom = path.resolve("../../examples/valid/family.ged");
const invalidStructure = path.resolve(
  "../../examples/invalid/invalid-structure.ged",
);
const validXlsx = path.resolve("../../examples/valid/family.xlsx");

async function uploadAndScan(
  page: import("@playwright/test").Page,
  source: string,
) {
  await page.getByLabel("选择文件").setInputFiles(source);
  await expect(page.getByText("可以扫描")).toBeVisible();
  await page.getByRole("button", { name: "运行扫描" }).click();
  await expect(page.getByText("SCAN COMPLETE").first()).toBeVisible();
}

test("uploads a valid GEDCOM through the real backend with zero errors", async ({
  page,
}) => {
  await page.goto("/");
  await uploadAndScan(page, validGedcom);
  await expect(
    page.getByRole("heading", { name: /0 findings \/ 16 people/ }),
  ).toBeVisible();
  await expect(
    page.locator(".stats div", { hasText: "Errors" }).locator("strong"),
  ).toHaveText("0");
});

test("shows named structure rules from an invalid GEDCOM", async ({ page }) => {
  await page.goto("/");
  await uploadAndScan(page, invalidStructure);
  await expect(
    page.locator(".issue-code", { hasText: "ZP001" }).first(),
  ).toBeVisible();
  await expect(
    page.locator(".issue-code", { hasText: "ZP004" }).first(),
  ).toBeVisible();
  await expect(
    page.locator(".issue-code", { hasText: "ZP005" }).first(),
  ).toBeVisible();
});

test("selects an Excel worksheet, maps columns, and scans", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("选择文件").setInputFiles(validXlsx);
  await expect(page.getByLabel("Worksheet")).toBeVisible();
  await page.getByLabel("Worksheet").selectOption("People");
  await page.getByRole("button", { name: "Load worksheet" }).click();
  await expect(page.getByRole("cell", { name: "X1" }).first()).toBeVisible();
  await page.getByLabel("Map Person ID").selectOption("id");
  await page.getByLabel("Map Display Name").selectOption("name");
  await page.getByLabel("Map Birth Year").selectOption("birth");
  await page.getByLabel("Map Parent IDs").selectOption("parents");
  await page.getByLabel("Map Generation").selectOption("generation");
  await page.getByRole("button", { name: "运行扫描" }).click();
  await expect(
    page.getByRole("heading", {
      name: /0 findings \/ 4 people \/ 3 relationships/,
    }),
  ).toBeVisible();
});

test("exports a real offline HTML report", async ({ page }) => {
  await page.goto("/");
  await uploadAndScan(page, invalidStructure);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "HTML ↓" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain("zupulint.html");
  const saved = await download.createReadStream();
  expect(saved).not.toBeNull();
});

test("switches the complete workbench heading to English", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch language" }).click();
  await expect(
    page.getByRole("heading", { name: "Make family-tree evidence auditable." }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Run scan" })).toBeVisible();
});

test("shows a useful message for a real API parse error", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("选择文件").setInputFiles({
    name: "broken.json",
    mimeType: "application/json",
    buffer: Buffer.from("{not-json"),
  });
  await expect(page.getByRole("alert")).toContainText("Invalid ZupuLint JSON");
});

test("clears uploaded data and all person findings", async ({ page }) => {
  await page.goto("/");
  await uploadAndScan(page, invalidStructure);
  await expect(page.getByText("@I1@").first()).toBeVisible();
  await page.getByRole("button", { name: "清除数据" }).click();
  await expect(page.getByText("SCAN COMPLETE")).toHaveCount(0);
  await expect(page.getByText("@I1@")).toHaveCount(0);
  await expect(page.getByText("invalid-structure.ged")).toHaveCount(0);
});
