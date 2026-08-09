import { useMutation } from "@tanstack/react-query";
import { useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import {
  detectFileType,
  requestPreview,
  requestReport,
  requestScan,
  saveBlob,
} from "./api";
import type { ImportOptions, Preview, ScanResult, Severity } from "./types";

const canonicalColumns = [
  "",
  "id",
  "name",
  "surname",
  "given_name",
  "birth",
  "death",
  "living",
  "sex",
  "parents",
  "adoptive_parents",
  "spouse",
  "generation",
  "generation_name",
  "branch",
  "place",
  "notes",
  "source",
  "privacy_level",
  "heir_to",
  "chu_si_to",
  "cheng_si_to",
  "jian_tiao_to",
];

const copy = {
  zh: {
    title: "让族谱证据，经得起校验。",
    intro: "在本机真实解析 GEDCOM、CSV、XLSX 或 JSON；原始文件只进入本地 API。",
    choose: "选择文件",
    drop: "或拖放到这里",
    scan: "运行扫描",
    clear: "清除数据",
    preview: "导入预览",
    config: "可选配置文件",
    mapping: "列映射",
    filters: "筛选问题",
    all: "全部",
    export: "导出报告",
    privacy: "隐私提醒：报告默认只输出敏感字段类型，不输出检测到的敏感原文。",
    ready: "可以扫描",
    loadingPreview: "正在读取真实预览…",
    scanning: "本地 API 正在解析并运行规则…",
    noFindings: "当前筛选没有问题。",
    none: "无",
    error: "操作失败",
    privacyPage: "隐私说明",
  },
  en: {
    title: "Make family-tree evidence auditable.",
    intro:
      "Parse GEDCOM, CSV, XLSX, or JSON through the real local API. Source data stays here.",
    choose: "Choose a file",
    drop: "or drop it here",
    scan: "Run scan",
    clear: "Clear data",
    preview: "Import preview",
    config: "Optional config file",
    mapping: "Column mapping",
    filters: "Filter findings",
    all: "All",
    export: "Export report",
    privacy:
      "Privacy note: reports include sensitive field types, not detected sensitive values.",
    ready: "Ready to scan",
    loadingPreview: "Loading a real preview…",
    scanning: "The local API is parsing and running rules…",
    noFindings: "No findings match the filters.",
    none: "None",
    error: "Operation failed",
    privacyPage: "Privacy",
  },
} as const;

const emptyOptions: ImportOptions = {
  sheet: "",
  delimiter: ",",
  encoding: "",
  columnMapping: {},
  configFile: null,
};

const severitySymbols: Record<Severity, string> = {
  error: "×",
  warning: "!",
  info: "i",
};

function Workbench() {
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [options, setOptions] = useState<ImportOptions>(emptyOptions);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [rule, setRule] = useState("all");
  const [person, setPerson] = useState("");
  const [category, setCategory] = useState("all");
  const [downloadError, setDownloadError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const configRef = useRef<HTMLInputElement>(null);
  const t = copy[language];

  const previewMutation = useMutation({
    mutationFn: ({
      selected,
      active,
    }: {
      selected: File;
      active: ImportOptions;
    }) => requestPreview(selected, active),
    onSuccess: (payload) => {
      setPreview(payload);
      setOptions((current) => ({
        ...current,
        columnMapping: payload.suggested_mapping,
      }));
    },
  });
  const scanMutation = useMutation({
    mutationFn: ({
      selected,
      active,
    }: {
      selected: File;
      active: ImportOptions;
    }) => requestScan(selected, active),
    onSuccess: setResult,
  });

  const selectFile = (selected?: File) => {
    if (!selected) return;
    const fresh = { ...emptyOptions, columnMapping: {} };
    setFile(selected);
    setResult(null);
    setPreview(null);
    setOptions(fresh);
    previewMutation.reset();
    scanMutation.reset();
    previewMutation.mutate({ selected, active: fresh });
  };
  const refreshPreview = () => {
    if (file) previewMutation.mutate({ selected: file, active: options });
  };
  const runScan = () => {
    if (file) scanMutation.mutate({ selected: file, active: options });
  };
  const clear = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setOptions(emptyOptions);
    setSeverity("all");
    setRule("all");
    setPerson("");
    setCategory("all");
    setDownloadError("");
    previewMutation.reset();
    scanMutation.reset();
    if (inputRef.current) inputRef.current.value = "";
    if (configRef.current) configRef.current.value = "";
  };

  const filtered = useMemo(
    () =>
      result?.issues.filter(
        (issue) =>
          (severity === "all" || issue.severity === severity) &&
          (rule === "all" || issue.rule_id === rule) &&
          (category === "all" || issue.category === category) &&
          (!person ||
            issue.person_ids.some((id) =>
              id.toLowerCase().includes(person.toLowerCase()),
            )),
      ) ?? [],
    [result, severity, rule, category, person],
  );
  const rules = [
    ...new Set(result?.issues.map((issue) => issue.rule_id) ?? []),
  ].sort();
  const categories = [
    ...new Set(result?.issues.map((issue) => issue.category) ?? []),
  ].sort();

  const download = async (format: "html" | "json" | "sarif") => {
    if (!file) return;
    setDownloadError("");
    try {
      const blob = await requestReport(file, options, format);
      saveBlob(blob, `${file.name}.zupulint.${format}`);
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error.message : "Unknown error",
      );
    }
  };

  const stage = scanMutation.isPending
    ? t.scanning
    : previewMutation.isPending
      ? t.loadingPreview
      : result
        ? "SCAN COMPLETE"
        : file
          ? t.ready
          : "IDLE";
  const activeError = previewMutation.error ?? scanMutation.error;

  return (
    <main className="shell">
      <nav className="nav">
        <span className="mark">
          谱校 <small>ZUPULINT</small>
        </span>
        <div className="nav-actions">
          <Link to="/privacy">{t.privacyPage}</Link>
          <button
            className="quiet"
            onClick={() => setLanguage(language === "zh" ? "en" : "zh")}
            aria-label="Switch language"
          >
            {language === "zh" ? "EN" : "中文"}
          </button>
          <a
            href="https://github.com/KanadeK/zupulint"
            target="_blank"
            rel="noreferrer"
          >
            GitHub ↗
          </a>
        </div>
      </nav>
      <header className="hero">
        <p className="eyebrow">LOCAL GENEALOGY QUALITY WORKBENCH</p>
        <h1 lang={language === "zh" ? "zh-CN" : "en"}>{t.title}</h1>
        <p className="intro">{t.intro}</p>
      </header>

      <section className="workspace" aria-label="Genealogy scanner">
        <div
          className="upload-panel"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            selectFile(event.dataTransfer.files[0]);
          }}
        >
          <input
            aria-label={t.choose}
            ref={inputRef}
            type="file"
            accept=".ged,.gedcom,.csv,.xlsx,.json"
            hidden
            onChange={(event) => selectFile(event.target.files?.[0])}
          />
          <div className="upload-icon" aria-hidden="true">
            ↥
          </div>
          <h2>{t.choose}</h2>
          <p>{t.drop}</p>
          <button className="primary" onClick={() => inputRef.current?.click()}>
            {t.choose}
          </button>
          <p className="formats">GEDCOM / CSV / XLSX / JSON</p>
          {file && (
            <div className="file-chip">
              <span>{detectFileType(file.name)}</span>
              <strong>{file.name}</strong>
              <small>{Math.ceil(file.size / 1024)} KB</small>
            </div>
          )}
        </div>
        <div className="control-panel">
          <div className="section-label">{t.preview}</div>
          <p className="stage" aria-live="polite">
            {stage}
          </p>
          {preview?.requires_sheet && (
            <label>
              Worksheet
              <select
                aria-label="Worksheet"
                value={options.sheet}
                onChange={(event) =>
                  setOptions({ ...options, sheet: event.target.value })
                }
              >
                <option value="">Select…</option>
                {preview.sheets.map((sheet) => (
                  <option key={sheet}>{sheet}</option>
                ))}
              </select>
            </label>
          )}
          {file && detectFileType(file.name) === "CSV" && (
            <div className="option-row">
              <label>
                Delimiter
                <input
                  aria-label="Delimiter"
                  maxLength={1}
                  value={options.delimiter}
                  onChange={(event) =>
                    setOptions({ ...options, delimiter: event.target.value })
                  }
                />
              </label>
              <label>
                Encoding
                <select
                  aria-label="Encoding"
                  value={options.encoding}
                  onChange={(event) =>
                    setOptions({ ...options, encoding: event.target.value })
                  }
                >
                  <option value="">Auto</option>
                  <option value="utf-8-sig">UTF-8/BOM</option>
                  <option value="gb18030">GB18030</option>
                </select>
              </label>
              <button className="link-button" onClick={refreshPreview}>
                Refresh preview
              </button>
            </div>
          )}
          {preview?.requires_sheet && options.sheet && (
            <button className="link-button" onClick={refreshPreview}>
              Load worksheet
            </button>
          )}
          {preview && !preview.requires_sheet && (
            <PreviewTable preview={preview} />
          )}
          {preview?.headers.length ? (
            <div className="mapping">
              <h3>{t.mapping}</h3>
              {preview.headers.map((header) => (
                <label key={header}>
                  <span>{header}</span>
                  <select
                    aria-label={`Map ${header}`}
                    value={options.columnMapping[header] ?? ""}
                    onChange={(event) =>
                      setOptions({
                        ...options,
                        columnMapping: {
                          ...options.columnMapping,
                          [header]: event.target.value,
                        },
                      })
                    }
                  >
                    {canonicalColumns.map((column) => (
                      <option key={column} value={column}>
                        {column || "Ignore"}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          ) : null}
          <label className="config-input">
            {t.config}
            <input
              ref={configRef}
              type="file"
              accept=".yml,.yaml"
              onChange={(event) =>
                setOptions({
                  ...options,
                  configFile: event.target.files?.[0] ?? null,
                })
              }
            />
          </label>
          <div className="privacy">
            <span aria-hidden="true">◈</span>
            <span>{t.privacy}</span>
          </div>
          <div className="button-row">
            <button
              className="primary"
              disabled={
                !file ||
                previewMutation.isPending ||
                scanMutation.isPending ||
                preview?.requires_sheet
              }
              onClick={runScan}
            >
              {t.scan}
            </button>
            <button
              className="secondary"
              onClick={clear}
              disabled={!file && !result}
            >
              {t.clear}
            </button>
          </div>
          {activeError && (
            <p className="error" role="alert">
              <b>{t.error}:</b> {activeError.message}
            </p>
          )}
        </div>
      </section>

      {result && (
        <section className="results">
          <div className="results-head">
            <div>
              <p className="eyebrow">SCAN COMPLETE</p>
              <h2>
                {result.summary.issues} findings <span>/</span>{" "}
                {result.summary.people} people <span>/</span>{" "}
                {result.summary.relationships} relationships
              </h2>
            </div>
            <div className="exports">
              <span>{t.export}</span>
              {(["html", "json", "sarif"] as const).map((format) => (
                <button
                  key={format}
                  className="link-button"
                  onClick={() => void download(format)}
                >
                  {format.toUpperCase()} ↓
                </button>
              ))}
            </div>
          </div>
          {downloadError && (
            <p className="error" role="alert">
              {downloadError}
            </p>
          )}
          <div className="stats">
            <div>
              <strong>{result.summary.by_severity.error ?? 0}</strong>
              <span className="severity-icon error-icon" aria-hidden="true">
                {severitySymbols.error}
              </span>
              Errors
            </div>
            <div>
              <strong>{result.summary.by_severity.warning ?? 0}</strong>
              <span className="severity-icon warning-icon" aria-hidden="true">
                {severitySymbols.warning}
              </span>
              Warnings
            </div>
            <div>
              <strong>{result.summary.by_severity.info ?? 0}</strong>
              <span className="severity-icon info-icon" aria-hidden="true">
                {severitySymbols.info}
              </span>
              Info
            </div>
          </div>
          <div className="filters">
            <label>
              {t.filters}
              <select
                aria-label="Severity"
                value={severity}
                onChange={(event) =>
                  setSeverity(event.target.value as Severity | "all")
                }
              >
                <option value="all">{t.all}</option>
                <option value="error">Error</option>
                <option value="warning">Warning</option>
                <option value="info">Info</option>
              </select>
            </label>
            <label>
              Rule
              <select
                aria-label="Rule"
                value={rule}
                onChange={(event) => setRule(event.target.value)}
              >
                <option value="all">{t.all}</option>
                {rules.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              Category
              <select
                aria-label="Category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="all">{t.all}</option>
                {categories.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              Person
              <input
                aria-label="Person"
                value={person}
                onChange={(event) => setPerson(event.target.value)}
              />
            </label>
          </div>
          <div className="issue-list">
            {filtered.length ? (
              filtered.map((issue, index) => (
                <details
                  className={`issue ${issue.severity}`}
                  key={`${issue.rule_id}-${issue.message}-${index}`}
                >
                  <summary>
                    <span className="issue-code">{issue.rule_id}</span>
                    <span className="issue-title">{issue.message}</span>
                    <span className="severity-label">
                      <span aria-hidden="true">
                        {severitySymbols[issue.severity]}
                      </span>{" "}
                      {issue.severity} / {issue.category}
                    </span>
                  </summary>
                  <div className="issue-detail">
                    <p>
                      <b>Related people:</b>{" "}
                      {issue.person_ids.join(", ") || t.none}
                    </p>
                    <p>
                      <b>Related relationships:</b>{" "}
                      {issue.relationship_ids.join(", ") || t.none}
                    </p>
                    <p>
                      <b>Evidence:</b>{" "}
                      <code>{JSON.stringify(issue.evidence)}</code>
                    </p>
                    <p>
                      <b>Suggestion:</b> {issue.suggestion}
                    </p>
                    <p>
                      <b>Confidence:</b> {issue.confidence.toFixed(2)}
                    </p>
                  </div>
                </details>
              ))
            ) : (
              <p className="muted">{t.noFindings}</p>
            )}
          </div>
        </section>
      )}
    </main>
  );
}

function PreviewTable({ preview }: { preview: Preview }) {
  if (!preview.rows.length) return <p className="muted">No preview rows.</p>;
  const headers = preview.headers.length
    ? preview.headers
    : Object.keys(preview.rows[0]);
  return (
    <div className="preview-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => (
                <td key={header}>{row[header] ?? ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {preview.warnings.map((warning) => (
        <p className="warning-text" key={warning}>
          ⚠ {warning}
        </p>
      ))}
    </div>
  );
}

function PrivacyPage() {
  return (
    <main className="shell narrow">
      <nav className="nav">
        <span className="mark">
          谱校 <small>ZUPULINT</small>
        </span>
        <Link to="/">← Workbench</Link>
      </nav>
      <article className="privacy-page">
        <p className="eyebrow">LOCAL BY DESIGN</p>
        <h1>Privacy and data handling</h1>
        <p>
          Uploads go only to the FastAPI process on your own machine. Temporary
          files are deleted after each request. No genealogy content is
          persisted, sent to analytics, or sent to an AI service.
        </p>
        <p>
          Reports list sensitive field categories and stable record IDs; they do
          not include detected phone numbers, national IDs, addresses, medical
          text, or DNA values by default.
        </p>
      </article>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Workbench />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
