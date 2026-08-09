import type { ImportOptions, Preview, ScanResult } from "./types";

export const API_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

export function detectFileType(name: string): string {
  const extension = name.toLowerCase().split(".").pop();
  if (extension === "ged" || extension === "gedcom") return "GEDCOM";
  if (extension === "csv") return "CSV";
  if (extension === "xlsx") return "Excel";
  if (extension === "json") return "JSON";
  return "Unsupported";
}

function appendOptions(
  body: FormData,
  options: ImportOptions,
  includeConfig = true,
): void {
  if (options.sheet) body.append("sheet", options.sheet);
  if (options.delimiter) body.append("delimiter", options.delimiter);
  if (options.encoding) body.append("encoding", options.encoding);
  if (Object.keys(options.columnMapping).length) {
    body.append("column_mapping", JSON.stringify(options.columnMapping));
  }
  if (includeConfig && options.configFile)
    body.append("config_file", options.configFile);
}

async function detail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function requestPreview(
  file: File,
  options: ImportOptions,
): Promise<Preview> {
  const body = new FormData();
  body.append("file", file);
  appendOptions(body, options, false);
  const response = await fetch(`${API_URL}/api/preview`, {
    method: "POST",
    body,
  });
  if (!response.ok) throw new Error(await detail(response));
  return (await response.json()) as Preview;
}

export async function requestScan(
  file: File,
  options: ImportOptions,
): Promise<ScanResult> {
  const body = new FormData();
  body.append("file", file);
  appendOptions(body, options);
  const response = await fetch(`${API_URL}/api/scan`, { method: "POST", body });
  if (!response.ok) throw new Error(await detail(response));
  return (await response.json()) as ScanResult;
}

export async function requestReport(
  file: File,
  options: ImportOptions,
  format: "html" | "json" | "sarif",
): Promise<Blob> {
  const body = new FormData();
  body.append("file", file);
  appendOptions(body, options);
  const response = await fetch(`${API_URL}/api/report?format=${format}`, {
    method: "POST",
    body,
  });
  if (!response.ok) throw new Error(await detail(response));
  return await response.blob();
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
