import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";

const preview = {
  name: "family.csv",
  size: 42,
  format: "csv",
  sheets: [],
  requires_sheet: false,
  headers: ["Ancestor ID", "Full Name"],
  rows: [{ "Ancestor ID": "P1", "Full Name": "合成人物" }],
  warnings: [],
  suggested_mapping: { "Ancestor ID": "id", "Full Name": "name" },
};
const result = {
  version: "0.1.0",
  scan: { time: "2026-01-01T00:00:00Z", input: {} },
  summary: {
    people: 2,
    relationships: 1,
    issues: 2,
    by_severity: { error: 1, warning: 1 },
    by_rule: { ZP601: 1, ZP103: 1 },
  },
  issues: [
    {
      rule_id: "ZP601",
      severity: "error",
      category: "quality",
      message: "Name missing",
      person_ids: ["P1"],
      relationship_ids: [],
      source_location: null,
      evidence: { fields: ["name"] },
      suggestion: "Add a name",
      confidence: 1,
    },
    {
      rule_id: "ZP103",
      severity: "warning",
      category: "chronology",
      message: "Unusual parent age",
      person_ids: ["P2"],
      relationship_ids: ["R1"],
      source_location: null,
      evidence: { age: 8 },
      suggestion: "Check dates",
      confidence: 0.8,
    },
  ],
};

function ok(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function mockHappyFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/api/preview")) return ok(preview);
    if (url.includes("/api/scan")) return ok(result);
    if (url.includes("/api/report"))
      return new Response("report", { status: 200 });
    return new Response("not found", { status: 404 });
  });
}

function renderApp(route = "/") {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

async function uploadCsv() {
  const input = screen.getByLabelText(/选择文件/i, { selector: "input" });
  fireEvent.change(input, {
    target: {
      files: [
        new File(["Ancestor ID,Full Name\nP1,合成人物"], "family.csv", {
          type: "text/csv",
        }),
      ],
    },
  });
  await screen.findByText("合成人物");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ZupuLint workbench", () => {
  it("selects a file, identifies it, and renders a real preview", async () => {
    const fetchMock = mockHappyFetch();
    renderApp();
    await uploadCsv();
    expect(screen.getByText("CSV")).toBeInTheDocument();
    expect(screen.getAllByText("Ancestor ID").length).toBeGreaterThan(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/preview"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("changes column mapping and submits it to the scan API", async () => {
    const fetchMock = mockHappyFetch();
    renderApp();
    await uploadCsv();
    await userEvent.selectOptions(
      screen.getByLabelText("Map Full Name"),
      "surname",
    );
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    await screen.findByText("Name missing");
    const scanCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes("/api/scan"),
    );
    const body = (scanCall?.[1] as RequestInit).body as FormData;
    expect(String(body.get("column_mapping"))).toContain(
      '"Full Name":"surname"',
    );
  });

  it("runs a scan and shows severity totals from the API", async () => {
    mockHappyFetch();
    renderApp();
    await uploadCsv();
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    expect(
      await screen.findByRole("heading", {
        name: /2 findings.*2 people.*1 relationships/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Name missing")).toBeInTheDocument();
  });

  it("filters findings by severity, category, rule, and person", async () => {
    mockHappyFetch();
    renderApp();
    await uploadCsv();
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    await screen.findByText("Name missing");
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "warning");
    expect(screen.queryByText("Name missing")).not.toBeInTheDocument();
    expect(screen.getByText("Unusual parent age")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Category"), "quality");
    expect(screen.getByText("当前筛选没有问题。")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Severity"), "all");
    await userEvent.selectOptions(screen.getByLabelText("Category"), "all");
    await userEvent.selectOptions(screen.getByLabelText("Rule"), "ZP601");
    await userEvent.type(screen.getByLabelText("Person"), "P1");
    expect(screen.getByText("Name missing")).toBeInTheDocument();
  });

  it("expands issue details with related records, evidence, and suggestion", async () => {
    mockHappyFetch();
    renderApp();
    await uploadCsv();
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    const summary = await screen.findByText("Name missing");
    await userEvent.click(summary);
    const details = summary.closest("details");
    expect(
      within(details!).getByText(
        (_, element) =>
          element?.tagName === "P" &&
          element.textContent === "Related people: P1",
      ),
    ).toBeInTheDocument();
    expect(within(details!).getByText(/Add a name/)).toBeInTheDocument();
  });

  it("downloads a report through the real report endpoint", async () => {
    const fetchMock = mockHappyFetch();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:report"),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    renderApp();
    await uploadCsv();
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    await screen.findByText("Name missing");
    await userEvent.click(screen.getByRole("button", { name: "HTML ↓" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/report?format=html"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("shows a comprehensible API error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Malformed GEDCOM at line 3" }), {
        status: 422,
        headers: { "content-type": "application/json" },
      }),
    );
    renderApp();
    const input = screen.getByLabelText(/选择文件/i, { selector: "input" });
    fireEvent.change(input, {
      target: { files: [new File(["bad"], "bad.ged")] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Malformed GEDCOM at line 3",
    );
  });

  it("clears all uploaded and person-result state", async () => {
    mockHappyFetch();
    renderApp();
    await uploadCsv();
    await userEvent.click(screen.getByRole("button", { name: "运行扫描" }));
    await screen.findByText("Name missing");
    await userEvent.click(screen.getByRole("button", { name: "清除数据" }));
    expect(screen.queryByText("family.csv")).not.toBeInTheDocument();
    expect(screen.queryByText("Name missing")).not.toBeInTheDocument();
  });

  it("switches language and exposes the routed privacy explanation", async () => {
    renderApp();
    await userEvent.click(
      screen.getByRole("button", { name: "Switch language" }),
    );
    expect(
      screen.getByRole("heading", {
        name: "Make family-tree evidence auditable.",
      }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Privacy" }));
    expect(
      screen.getByRole("heading", { name: "Privacy and data handling" }),
    ).toBeInTheDocument();
  });
});
