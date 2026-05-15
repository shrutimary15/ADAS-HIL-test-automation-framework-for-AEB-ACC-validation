# =============================================================================
# report_generator.py — HTML Test Report Generator
# =============================================================================
# After running tests, this module generates a professional HTML report.
#
# In real projects, reports go to:
#   - Jira/Xray (test management)
#   - Polarion (requirements & test traceability)
#   - Confluence (team visibility)
#   - Email to stakeholders
#
# This generates a standalone HTML file — open in any browser, share anywhere.
# The format mimics what you'd see from tools like pytest-html or Allure.
# =============================================================================

import json
import os
from datetime import datetime


def generate_report(results: list, config: dict, output_path: str):
    """
    Generate a professional HTML test report.

    Args:
        results:     List of test result dicts from run_tests.py
        config:      Test bench configuration
        output_path: Where to write the HTML file
    """
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    pass_rate = (passed / total * 100) if total > 0 else 0

    overall = "PASS" if pass_rate >= config["environment"]["pass_threshold_percent"] else "FAIL"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build test rows HTML
    rows_html = ""
    for r in results:
        status_class = r["status"].lower()
        status_icon = {"PASS": "✓", "FAIL": "✗", "ERROR": "⚠"}.get(r["status"], "?")
        duration = f"{r.get('duration_ms', 0):.0f} ms"
        error_detail = ""
        if r.get("message"):
            error_detail = f'<div class="error-msg">{r["message"]}</div>'

        rows_html += f"""
        <tr class="row-{status_class}">
            <td class="status-cell {status_class}">{status_icon} {r["status"]}</td>
            <td class="req-cell"><code>{r.get("req_id", "—")}</code></td>
            <td class="name-cell">{r["test_name"]}{error_detail}</td>
            <td>{r.get("module", "—")}</td>
            <td class="duration">{duration}</td>
        </tr>"""

    # Build chart data for sparkline
    chart_data = json.dumps([
        {"label": r["test_name"].replace("test_", "").replace("_", " "),
         "status": r["status"]}
        for r in results
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAS HIL Test Report — {timestamp}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;600;800&display=swap');

  :root {{
    --pass: #00c896;
    --fail: #ff4757;
    --error: #ffa502;
    --bg: #0a0e1a;
    --surface: #111827;
    --surface2: #1a2236;
    --border: #1e2d45;
    --text: #e2e8f0;
    --text-dim: #64748b;
    --accent: #3b82f6;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Syne', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 0 0 60px;
  }}

  /* ── HEADER ── */
  .header {{
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 32px 48px;
    position: relative;
    overflow: hidden;
  }}
  .header::before {{
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at center, rgba(59,130,246,0.08) 0%, transparent 60%);
  }}
  .header-grid {{
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: start;
    gap: 24px;
    position: relative;
  }}
  .brand {{
    font-size: 11px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 8px;
  }}
  h1 {{
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.2;
  }}
  .meta {{
    margin-top: 12px;
    font-size: 12px;
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }}
  .meta span {{ display: flex; align-items: center; gap: 6px; }}

  .overall-badge {{
    padding: 16px 28px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    border: 2px solid;
    text-align: center;
    white-space: nowrap;
  }}
  .overall-badge.pass {{ color: var(--pass); border-color: var(--pass); background: rgba(0,200,150,0.08); }}
  .overall-badge.fail {{ color: var(--fail); border-color: var(--fail); background: rgba(255,71,87,0.08); }}

  /* ── STATS ── */
  .stats-bar {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .stat {{
    background: var(--surface);
    padding: 24px 32px;
    text-align: center;
  }}
  .stat-value {{
    font-size: 36px;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 4px;
  }}
  .stat-label {{
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
  }}
  .stat.pass .stat-value {{ color: var(--pass); }}
  .stat.fail .stat-value {{ color: var(--fail); }}
  .stat.error .stat-value {{ color: var(--error); }}
  .stat.total .stat-value {{ color: var(--accent); }}

  /* ── PROGRESS BAR ── */
  .progress-section {{
    padding: 24px 48px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }}
  .progress-label {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 12px;
    color: var(--text-dim);
  }}
  .progress-bar {{
    height: 8px;
    background: var(--surface2);
    border-radius: 4px;
    overflow: hidden;
  }}
  .progress-fill {{
    height: 100%;
    border-radius: 4px;
    background: {"var(--pass)" if overall == "PASS" else "var(--fail)"};
    width: {pass_rate:.1f}%;
    transition: width 1s ease;
  }}

  /* ── TABLE ── */
  .table-section {{ padding: 32px 48px; }}
  .section-title {{
    font-size: 11px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  thead tr {{
    background: var(--surface2);
  }}
  th {{
    padding: 12px 16px;
    text-align: left;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
  }}
  td {{
    padding: 14px 16px;
    border-bottom: 1px solid rgba(30,45,69,0.5);
    vertical-align: top;
  }}
  tr:hover td {{ background: rgba(59,130,246,0.04); }}

  .status-cell {{ font-weight: 700; font-family: 'JetBrains Mono', monospace; white-space: nowrap; }}
  .status-cell.pass {{ color: var(--pass); }}
  .status-cell.fail {{ color: var(--fail); }}
  .status-cell.error {{ color: var(--error); }}

  .req-cell code {{
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    color: var(--accent);
    font-family: 'JetBrains Mono', monospace;
    white-space: nowrap;
  }}

  .name-cell {{ font-weight: 500; }}
  .error-msg {{
    margin-top: 6px;
    font-size: 11px;
    color: var(--fail);
    font-family: 'JetBrains Mono', monospace;
    background: rgba(255,71,87,0.08);
    padding: 8px 12px;
    border-radius: 4px;
    border-left: 2px solid var(--fail);
    white-space: pre-wrap;
    word-break: break-word;
  }}
  .duration {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-dim);
    white-space: nowrap;
  }}

  /* ── FOOTER ── */
  .footer {{
    padding: 24px 48px;
    border-top: 1px solid var(--border);
    font-size: 11px;
    color: var(--text-dim);
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-grid">
    <div>
      <div class="brand">ADAS Validation · HIL Test Suite</div>
      <h1>AEB / ACC System Test Report</h1>
      <div class="meta">
        <span>📅 {timestamp}</span>
        <span>🔧 {config["bench"]["dut"]}</span>
        <span>🖥 {config["bench"]["name"]}</span>
        <span>⏱ {config["bench"]["sample_rate_ms"]}ms sample rate</span>
      </div>
    </div>
    <div class="overall-badge {'pass' if overall == 'PASS' else 'fail'}">
      {'SUITE PASS' if overall == 'PASS' else 'SUITE FAIL'}
      <br><small style="font-size:11px;font-weight:400;">{pass_rate:.0f}% pass rate</small>
    </div>
  </div>
</div>

<div class="stats-bar">
  <div class="stat total">
    <div class="stat-value">{total}</div>
    <div class="stat-label">Total Tests</div>
  </div>
  <div class="stat pass">
    <div class="stat-value">{passed}</div>
    <div class="stat-label">Passed</div>
  </div>
  <div class="stat fail">
    <div class="stat-value">{failed}</div>
    <div class="stat-label">Failed</div>
  </div>
  <div class="stat error">
    <div class="stat-value">{errors}</div>
    <div class="stat-label">Errors</div>
  </div>
</div>

<div class="progress-section">
  <div class="progress-label">
    <span>Pass Rate</span>
    <span>{pass_rate:.1f}% (threshold: {config["environment"]["pass_threshold_percent"]}%)</span>
  </div>
  <div class="progress-bar">
    <div class="progress-fill"></div>
  </div>
</div>

<div class="table-section">
  <div class="section-title">Test Results — ISO 26262 Requirement Traceability</div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Requirement ID</th>
        <th>Test Name</th>
        <th>Module</th>
        <th>Duration</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>

<div class="footer">
  <span>Generated by ADAS HIL Test Framework v1.0</span>
  <span>ISO 26262 · Euro NCAP · ASIL-B Compliant</span>
  <span>DUT: {config["bench"]["dut"]}</span>
</div>

</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n📊 Report written to: {output_path}")
    return output_path
