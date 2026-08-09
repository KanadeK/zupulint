"""Safe, self-contained HTML, JSON, and SARIF report output."""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, select_autoescape

from zupulint import __version__
from zupulint.rules import RULE_BY_ID, ScanResult

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ZupuLint report · {{ input_name }}</title>
  <style>
    :root{color-scheme:light dark;--paper:#f7f6f2;--ink:#202523;--panel:#fff;--line:#d6d7d2;--red:#9c2924;--amber:#8a5600;--blue:#285f86}
    @media(prefers-color-scheme:dark){:root{--paper:#171a19;--ink:#edf0ed;--panel:#202422;--line:#3a403d;--red:#ff8a82;--amber:#ffc56f;--blue:#8bc8ed}}
    *{box-sizing:border-box}body{font-family:Inter,ui-sans-serif,system-ui,sans-serif;max-width:1080px;margin:0 auto;padding:2rem;color:var(--ink);background:var(--paper);line-height:1.5}header{border-top:6px solid var(--red);padding-top:1rem}h1{margin:.2rem 0;font-size:clamp(1.8rem,5vw,3rem)}h2{margin-top:2rem}.lede{max-width:72ch}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:.75rem}.stat,.panel{background:var(--panel);border:1px solid var(--line);padding:.85rem;border-radius:.5rem}.stat strong{font-size:1.55rem;display:block}.error{color:var(--red)}.warning{color:var(--amber)}.info{color:var(--blue)}table{width:100%;border-collapse:collapse;background:var(--panel)}th,td{padding:.55rem;text-align:left;border-bottom:1px solid var(--line)}label{display:inline-flex;gap:.45rem;align-items:center;margin:.25rem 1rem .5rem 0}select{font:inherit;padding:.35rem}details.issue{margin:.65rem 0;background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--blue);border-radius:.35rem;padding:.7rem}.issue[data-severity="error"]{border-left-color:var(--red)}.issue[data-severity="warning"]{border-left-color:var(--amber)}summary{cursor:pointer;font-weight:650}.tag{font:600 .8rem ui-monospace,monospace;border:1px solid currentColor;border-radius:99px;padding:.15rem .4rem;margin-right:.4rem}code,pre{white-space:pre-wrap;overflow-wrap:anywhere}.privacy{border-left:5px solid var(--red)}footer{margin-top:2rem;border-top:1px solid var(--line);padding-top:1rem;font-size:.9rem}.empty{display:none}
    @media(max-width:620px){body{padding:1rem}table{font-size:.84rem}.wide{overflow-x:auto}}
    @media print{body{max-width:none;background:#fff;color:#000;padding:0}.filters{display:none}details{break-inside:avoid}details>*{display:block!important}}
  </style>
</head>
<body>
  <header><p>ZUPULINT / 谱校</p><h1>Genealogy audit report</h1><p class="lede">A local, offline report. The source file was not uploaded to a third party and ZupuLint never modifies or automatically merges source records.</p></header>
  <section aria-labelledby="summary"><h2 id="summary">Scan summary</h2><div class="grid">
    <div class="stat"><strong>{{ summary.people }}</strong>People</div><div class="stat"><strong>{{ summary.relationships }}</strong>Relationships</div><div class="stat"><strong>{{ summary.issues }}</strong>Findings</div>
    <div class="stat"><strong class="error">{{ summary.by_severity.get('error',0) }}</strong>Errors</div><div class="stat"><strong class="warning">{{ summary.by_severity.get('warning',0) }}</strong>Warnings</div><div class="stat"><strong class="info">{{ summary.by_severity.get('info',0) }}</strong>Info</div>
  </div></section>
  <section aria-labelledby="input"><h2 id="input">Input</h2><div class="panel"><dl><dt>File</dt><dd>{{ input_name }}</dd><dt>Format</dt><dd>{{ input_info.get('format','unknown') }}</dd><dt>Size</dt><dd>{{ input_info.get('size','not recorded') }}</dd><dt>Scan time (UTC)</dt><dd>{{ scanned_at }}</dd><dt>Tool version</dt><dd>{{ version }}</dd></dl></div></section>
  <section aria-labelledby="statistics"><h2 id="statistics">Rule statistics</h2><div class="wide"><table><thead><tr><th>Rule</th><th>Category</th><th>Severity</th><th>Count</th></tr></thead><tbody>{% for row in rule_rows %}<tr><td>{{ row.id }}</td><td>{{ row.category }}</td><td>{{ row.severity }}</td><td>{{ row.count }}</td></tr>{% endfor %}{% if not rule_rows %}<tr><td colspan="4">No findings.</td></tr>{% endif %}</tbody></table></div></section>
  <section aria-labelledby="findings"><h2 id="findings">Findings</h2><div class="filters"><label>Severity <select id="severity"><option value="all">All</option><option value="error">Error</option><option value="warning">Warning</option><option value="info">Info</option></select></label><label>Rule <select id="rule"><option value="all">All</option>{% for rule in used_rules %}<option value="{{ rule }}">{{ rule }}</option>{% endfor %}</select></label><span id="visible-count" aria-live="polite"></span></div>
  <div id="issues">{% for issue in issues %}<details class="issue" data-severity="{{ issue.severity }}" data-rule="{{ issue.rule_id }}"><summary><span class="tag">{{ issue.rule_id }}</span><span class="{{ issue.severity }}">{{ severity_symbols[issue.severity] }} {{ issue.severity|upper }}</span> / {{ issue.message }}</summary><dl><dt>Category / confidence</dt><dd>{{ issue.category }} / {{ '%.2f'|format(issue.confidence) }}</dd><dt>People</dt><dd>{{ issue.person_ids|join(', ') or 'None' }}</dd><dt>Relationships</dt><dd>{{ issue.relationship_ids|join(', ') or 'None' }}</dd><dt>Source location</dt><dd>{{ issue.source_location or 'None' }}</dd>{% if include_evidence %}<dt>Evidence</dt><dd><code>{{ issue.evidence|tojson }}</code></dd>{% endif %}{% if include_suggestions %}<dt>Suggestion</dt><dd>{{ issue.suggestion }}</dd>{% endif %}</dl></details>{% endfor %}<p id="empty" class="empty">No findings match the selected filters.</p></div></section>
  <section class="panel privacy" aria-labelledby="privacy"><h2 id="privacy">Privacy handling</h2><p>Living-person redaction is <strong>{{ 'enabled' if config.privacy.redact_living_people else 'disabled' }}</strong>. Findings contain field categories and record identifiers, not full phone numbers, national IDs, addresses, medical text, or DNA values. Review configuration before sharing a report.</p></section>
  <section aria-labelledby="configuration"><h2 id="configuration">Configuration summary</h2><pre class="panel"><code>{{ config_json }}</code></pre></section>
  <footer>Generated by ZupuLint {{ version }} at {{ scanned_at }}. This report is self-contained and can be opened offline.</footer>
  <script>
  (()=>{const severity=document.getElementById('severity'),rule=document.getElementById('rule'),items=[...document.querySelectorAll('.issue')],empty=document.getElementById('empty'),count=document.getElementById('visible-count');const apply=()=>{let shown=0;for(const item of items){const visible=(severity.value==='all'||item.dataset.severity===severity.value)&&(rule.value==='all'||item.dataset.rule===rule.value);item.hidden=!visible;if(visible)shown++}empty.style.display=shown?'none':'block';count.textContent=`${shown} visible`};severity.addEventListener('change',apply);rule.addEventListener('change',apply);apply()})();
  </script>
</body></html>"""

ENVIRONMENT = Environment(autoescape=select_autoescape(default_for_string=True))
ENVIRONMENT.filters["tojson"] = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_json(result: ScanResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_sarif(result: ScanResult) -> str:
    rules = [
        {
            "id": rule.rule_id,
            "name": rule.title,
            "shortDescription": {"text": rule.description},
            "helpUri": rule.documentation_url,
            "properties": {"category": rule.category, "configSchema": rule.config_schema},
            "defaultConfiguration": {
                "level": {"error": "error", "warning": "warning", "info": "note"}[
                    rule.default_severity
                ]
            },
        }
        for rule in sorted(RULE_BY_ID.values(), key=lambda item: item.rule_id)
    ]
    records: list[dict[str, Any]] = []
    for issue in result.issues:
        record: dict[str, Any] = {
            "ruleId": issue.rule_id,
            "level": {"error": "error", "warning": "warning", "info": "note"}[issue.severity],
            "message": {"text": issue.message},
            "properties": {
                "category": issue.category,
                "person_ids": list(issue.person_ids),
                "relationship_ids": list(issue.relationship_ids),
                "evidence": issue.evidence,
                "suggestion": issue.suggestion,
                "confidence": issue.confidence,
            },
        }
        if issue.source_location:
            record["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(result.input_info.get("name", "local-input"))
                        },
                        "region": {"snippet": {"text": issue.source_location}},
                    }
                }
            ]
        records.append(record)
    return (
        json.dumps(
            {
                "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {
                            "driver": {"name": "ZupuLint", "version": __version__, "rules": rules}
                        },
                        "results": records,
                        "invocations": [
                            {"executionSuccessful": True, "endTimeUtc": result.scanned_at}
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render_html(result: ScanResult, input_name: str = "local input") -> str:
    summary = result.summary
    rule_rows = [
        {
            "id": rule_id,
            "category": RULE_BY_ID[rule_id].category,
            "severity": next(issue.severity for issue in result.issues if issue.rule_id == rule_id),
            "count": count,
        }
        for rule_id, count in summary["by_rule"].items()
    ]
    template = ENVIRONMENT.from_string(HTML_TEMPLATE)
    return template.render(
        summary=summary,
        input_name=input_name,
        input_info=result.input_info,
        scanned_at=result.scanned_at,
        version=__version__,
        rule_rows=rule_rows,
        used_rules=sorted(summary["by_rule"]),
        issues=[issue.to_dict() for issue in result.issues],
        severity_symbols={"error": "×", "warning": "!", "info": "i"},
        config=result.config,
        config_json=json.dumps(result.config, ensure_ascii=False, indent=2, sort_keys=True),
        include_evidence=result.config["report"].get("include_evidence", True),
        include_suggestions=result.config["report"].get("include_suggestions", True),
    )
