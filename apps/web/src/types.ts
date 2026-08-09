export type Severity = "error" | "warning" | "info";

export type Issue = {
  rule_id: string;
  severity: Severity;
  category: string;
  message: string;
  person_ids: string[];
  relationship_ids: string[];
  source_location: string | null;
  evidence: Record<string, unknown>;
  suggestion: string;
  confidence: number;
};

export type ScanResult = {
  version: string;
  scan: { time: string; input: Record<string, unknown> };
  summary: {
    people: number;
    relationships: number;
    issues: number;
    by_severity: Record<string, number>;
    by_rule: Record<string, number>;
  };
  issues: Issue[];
};

export type Preview = {
  name: string;
  size: number;
  format: string;
  sheets: string[];
  requires_sheet: boolean;
  headers: string[];
  rows: Record<string, string>[];
  people?: number;
  relationships?: number;
  warnings: string[];
  suggested_mapping: Record<string, string>;
};

export type ImportOptions = {
  sheet: string;
  delimiter: string;
  encoding: string;
  columnMapping: Record<string, string>;
  configFile: File | null;
};
