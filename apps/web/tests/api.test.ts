import { afterEach, describe, expect, it, vi } from "vitest";
import {
  detectFileType,
  requestPreview,
  requestReport,
  requestScan,
  saveBlob,
} from "../src/api";
import type { ImportOptions } from "../src/types";

const options: ImportOptions = {
  sheet: "People",
  delimiter: ";",
  encoding: "gb18030",
  columnMapping: { 编号: "id" },
  configFile: new File(["version: 1"], "zupulint.yml"),
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("web API client", () => {
  it.each([
    ["a.ged", "GEDCOM"],
    ["a.gedcom", "GEDCOM"],
    ["a.csv", "CSV"],
    ["a.xlsx", "Excel"],
    ["a.json", "JSON"],
    ["a.zip", "Unsupported"],
  ])("detects %s", (name, expected) =>
    expect(detectFileType(name)).toBe(expected),
  );

  it("sends all import options to preview and scan", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(JSON.stringify({ rows: [], headers: [] }), {
          status: 200,
        }),
    );
    const file = new File(["x"], "family.csv");
    await requestPreview(file, options);
    await requestScan(file, options);
    const previewBody = fetchMock.mock.calls[0][1]?.body as FormData;
    const scanBody = fetchMock.mock.calls[1][1]?.body as FormData;
    expect(previewBody.get("config_file")).toBeNull();
    expect(scanBody.get("config_file")).toBe(options.configFile);
    expect(scanBody.get("sheet")).toBe("People");
    expect(scanBody.get("delimiter")).toBe(";");
  });

  it("uses JSON and fallback error details", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "bad mapping" }), { status: 422 }),
    );
    await expect(
      requestScan(new File(["x"], "x.csv"), options),
    ).rejects.toThrow("bad mapping");
    fetchMock.mockResolvedValueOnce(new Response("not json", { status: 500 }));
    await expect(
      requestPreview(new File(["x"], "x.csv"), options),
    ).rejects.toThrow("Request failed (500)");
  });

  it("returns report blobs and saves them", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("html", { status: 200 }),
    );
    const blob = await requestReport(new File(["x"], "x.csv"), options, "html");
    expect(blob.size).toBeGreaterThan(0);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:x"),
      revokeObjectURL: vi.fn(),
    });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    saveBlob(blob, "report.html");
    expect(click).toHaveBeenCalled();
  });
});
