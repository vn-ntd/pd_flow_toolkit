"""
Interactive Physical Design Analytics Dashboard Generator.
Creates a self-contained, offline-compatible HTML5 dashboard with dark theme,
metrics cards, SVG charts, and detailed violation tables.
"""

from pathlib import Path
from ..parsers.base_parser import PDRunMetrics


def generate_html_dashboard(metrics: PDRunMetrics, output_file: str) -> str:
    """Generates an interactive, standalone HTML dashboard for a PD run."""

    # Compute status badges and colors
    status = metrics.overall_status
    setup_color = "#10b981" if metrics.timing.setup_passed else "#ef4444"
    hold_color = "#10b981" if metrics.timing.hold_passed else "#ef4444"
    drc_color = "#10b981" if metrics.drc.passed else "#ef4444"
    cong_color = "#10b981" if metrics.congestion.max_pct < 85 else ("#f59e0b" if metrics.congestion.max_pct < 98 else "#ef4444")

    # Format DRC rows
    drc_rows_html = ""
    if metrics.drc.violations_by_type:
        for vtype, count in sorted(metrics.drc.violations_by_type.items(), key=lambda x: x[1], reverse=True):
            drc_rows_html += f"""
            <tr>
                <td style="font-weight: 500;">{vtype}</td>
                <td><span class="badge badge-error">{count}</span></td>
                <td>Routing Geometry</td>
                <td><span style="color: #ef4444;">Needs ECO reroute</span></td>
            </tr>
            """
    else:
        drc_rows_html = """
        <tr>
            <td colspan="4" style="text-align: center; color: #10b981; padding: 1.5rem;">
                ✓ No DRC violations found! Clean physical design signoff.
            </td>
        </tr>
        """

    # Format DRC by layer
    drc_layer_bars_html = ""
    if metrics.drc.violations_by_layer:
        max_layer_cnt = max(metrics.drc.violations_by_layer.values()) or 1
        for layer, cnt in sorted(metrics.drc.violations_by_layer.items(), key=lambda x: x[1], reverse=True):
            pct = min(100, int((cnt / max_layer_cnt) * 100))
            drc_layer_bars_html += f"""
            <div style="margin-bottom: 0.8rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.2rem;">
                    <span>{layer}</span>
                    <span style="font-weight: bold; color: #f87171;">{cnt} violations</span>
                </div>
                <div style="background: #334155; border-radius: 4px; height: 10px; overflow: hidden;">
                    <div style="width: {pct}%; background: linear-gradient(90deg, #f59e0b, #ef4444); height: 100%;"></div>
                </div>
            </div>
            """
    else:
        drc_layer_bars_html = "<div style='color: #10b981; padding: 1rem;'>✓ All metal layers DRC clean.</div>"

    raw_files_items_html = ""
    if metrics.raw_files:
        for rf in metrics.raw_files:
            fname = Path(rf).name
            raw_files_items_html += f"<li style='padding: 0.35rem 0; border-bottom: 1px solid #334155; display: flex; justify-content: space-between;'><span>📄 {fname}</span><span style='font-size: 0.75rem; color: #64748b; font-family: monospace;'>{rf}</span></li>"
    else:
        raw_files_items_html = "<li style='padding: 0.5rem 0; color: #64748b;'>No raw files logged for this run.</li>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PD Signoff Dashboard - {metrics.design_name}</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 2rem;
            line-height: 1.5;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 2rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .header h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .header .meta {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 0.3rem;
        }}
        .badge {{
            display: inline-block;
            padding: 0.35rem 0.85rem;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        .badge-pass {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}
        .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }}
        .badge-fail {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
        .badge-error {{ background: rgba(239, 68, 68, 0.2); color: #f87171; font-weight: 600; padding: 0.2rem 0.5rem; border-radius: 4px; }}

        .btn {{
            background: #334155;
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            padding: 0.45rem 0.95rem;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
        }}
        .btn:hover {{
            background: #475569;
            border-color: #64748b;
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }}
        .kpi-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.25rem;
            position: relative;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}
        .kpi-title {{
            font-size: 0.8rem;
            text-transform: uppercase;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        .kpi-value {{
            font-size: 1.85rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}
        .kpi-subtext {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        @media (max-width: 900px) {{
            .dashboard-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}
        .card h2 {{
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th, td {{
            text-align: left;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            color: var(--text-secondary);
            font-weight: 600;
            background: rgba(15, 23, 42, 0.4);
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .bar-container {{
            margin-top: 1rem;
        }}
        .footer {{
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>

    <div class="header">
        <div>
            <h1>EDA Physical Design Signoff Report</h1>
            <div class="meta">
                Design: <strong>{metrics.design_name}</strong> | Tool: <strong>{metrics.tool_name}</strong> | Stage: <strong>{metrics.stage}</strong>
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 1rem;">
            <button id="copySummaryBtn" class="btn" onclick="copySignoffSummary()">📋 Copy Summary</button>
            <span class="badge badge-{'pass' if status == 'PASS' else ('warn' if status == 'WARN' else 'fail')}">
                {status} SIGNOFF
            </span>
        </div>
    </div>

    <!-- Top KPI Cards -->
    <div class="kpi-grid">
        <div class="kpi-card" style="border-top: 4px solid {setup_color};">
            <div class="kpi-title">Worst Setup Slack (WNS)</div>
            <div class="kpi-value" style="color: {setup_color};">{metrics.timing.setup_wns:+.3f} ns</div>
            <div class="kpi-subtext">Total Negative Slack: {metrics.timing.setup_tns:.2f} ns</div>
        </div>

        <div class="kpi-card" style="border-top: 4px solid {hold_color};">
            <div class="kpi-title">Worst Hold Slack</div>
            <div class="kpi-value" style="color: {hold_color};">{metrics.timing.hold_wns:+.3f} ns</div>
            <div class="kpi-subtext">Hold TNS: {metrics.timing.hold_tns:.2f} ns</div>
        </div>

        <div class="kpi-card" style="border-top: 4px solid {drc_color};">
            <div class="kpi-title">Total DRC Violations</div>
            <div class="kpi-value" style="color: {drc_color};">{metrics.drc.total_violations}</div>
            <div class="kpi-subtext">Across {len(metrics.drc.violations_by_type)} violation categories</div>
        </div>

        <div class="kpi-card" style="border-top: 4px solid {cong_color};">
            <div class="kpi-title">Peak Congestion</div>
            <div class="kpi-value" style="color: {cong_color};">{metrics.congestion.max_pct:.1f}%</div>
            <div class="kpi-subtext">H: {metrics.congestion.h_max_pct:.1f}% | V: {metrics.congestion.v_max_pct:.1f}%</div>
        </div>

        <div class="kpi-card" style="border-top: 4px solid #38bdf8;">
            <div class="kpi-title">Core Utilization</div>
            <div class="kpi-value" style="color: #38bdf8;">{metrics.area_power.utilization_pct:.1f}%</div>
            <div class="kpi-subtext">Std Cells: {metrics.area_power.std_cell_count:,}</div>
        </div>
    </div>

    <!-- Main Dashboard Body -->
    <div class="dashboard-grid">
        <!-- Left Column: Timing & DRC details -->
        <div>
            <div class="card">
                <h2>Timing Quality Summary</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Timing Metric</th>
                            <th>Value</th>
                            <th>Threshold / Constraint</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Setup WNS</td>
                            <td style="font-weight: 600; color: {setup_color};">{metrics.timing.setup_wns:+.3f} ns</td>
                            <td>&gt;= 0.000 ns</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.setup_passed else 'fail'}">{'PASS' if metrics.timing.setup_passed else 'VIOLATED'}</span></td>
                        </tr>
                        <tr>
                            <td>Setup TNS</td>
                            <td>{metrics.timing.setup_tns:.3f} ns</td>
                            <td>== 0.000 ns</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.setup_tns >= 0 else 'fail'}">{'CLEAN' if metrics.timing.setup_tns >= 0 else 'VIOLATED'}</span></td>
                        </tr>
                        <tr>
                            <td>Setup Failing Endpoints (FEP)</td>
                            <td>{metrics.timing.setup_fep} endpoints</td>
                            <td>0 paths</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.setup_fep == 0 else 'fail'}">{'CLEAN' if metrics.timing.setup_fep == 0 else 'VIOLATED'}</span></td>
                        </tr>
                        <tr>
                            <td>Hold WNS</td>
                            <td style="font-weight: 600; color: {hold_color};">{metrics.timing.hold_wns:+.3f} ns</td>
                            <td>&gt;= 0.000 ns</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.hold_passed else 'fail'}">{'PASS' if metrics.timing.hold_passed else 'VIOLATED'}</span></td>
                        </tr>
                        <tr>
                            <td>Max Transition (Slew) Violations</td>
                            <td>{metrics.timing.max_slew_violations}</td>
                            <td>0</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.max_slew_violations == 0 else 'warn'}">{'CLEAN' if metrics.timing.max_slew_violations == 0 else 'CHECK'}</span></td>
                        </tr>
                        <tr>
                            <td>Max Capacitance Violations</td>
                            <td>{metrics.timing.max_cap_violations}</td>
                            <td>0</td>
                            <td><span class="badge badge-{'pass' if metrics.timing.max_cap_violations == 0 else 'warn'}">{'CLEAN' if metrics.timing.max_cap_violations == 0 else 'CHECK'}</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <h2>DRC Violation Breakdown</h2>
                    <input type="text" id="drcSearchInput" placeholder="🔍 Search DRC rule..." onkeyup="filterDrcTable()" style="padding: 0.35rem 0.75rem; border-radius: 6px; border: 1px solid var(--border-color); background: #0f172a; color: var(--text-primary); font-size: 0.85rem;" />
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Violation Rule</th>
                            <th>Count</th>
                            <th>Category</th>
                            <th>Action Required</th>
                        </tr>
                    </thead>
                    <tbody id="drcTableBody">
                        {drc_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Right Column: Congestion & Layers -->
        <div>
            <div class="card">
                <h2>Routing & Congestion</h2>
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.3rem;">
                        <span>Horizontal Congestion</span>
                        <span style="font-weight: 600;">{metrics.congestion.h_max_pct:.1f}%</span>
                    </div>
                    <div style="background: #334155; border-radius: 4px; height: 12px; overflow: hidden;">
                        <div style="width: {min(100.0, metrics.congestion.h_max_pct)}%; background: {cong_color}; height: 100%;"></div>
                    </div>
                </div>

                <div style="margin-bottom: 1.5rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 0.3rem;">
                        <span>Vertical Congestion</span>
                        <span style="font-weight: 600;">{metrics.congestion.v_max_pct:.1f}%</span>
                    </div>
                    <div style="background: #334155; border-radius: 4px; height: 12px; overflow: hidden;">
                        <div style="width: {min(100.0, metrics.congestion.v_max_pct)}%; background: {cong_color}; height: 100%;"></div>
                    </div>
                </div>

                <table>
                    <tbody>
                        <tr>
                            <td>Total Overflows</td>
                            <td style="font-weight: 600;">{metrics.congestion.overflow_h + metrics.congestion.overflow_v}</td>
                        </tr>
                        <tr>
                            <td>Hotspot Bins</td>
                            <td style="font-weight: 600;">{metrics.congestion.hotspot_count}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <h2>Violations by Metal Layer</h2>
                {drc_layer_bars_html}
            </div>

            <div class="card">
                <h2>Area & Power</h2>
                <table>
                    <tbody>
                        <tr>
                            <td>Core Area</td>
                            <td>{metrics.area_power.core_area_um2:,.1f} µm²</td>
                        </tr>
                        <tr>
                            <td>Std Cell Instances</td>
                            <td>{metrics.area_power.std_cell_count:,}</td>
                        </tr>
                        <tr>
                            <td>Macros</td>
                            <td>{metrics.area_power.macro_count}</td>
                        </tr>
                        <tr>
                            <td>Total Power</td>
                            <td>{metrics.area_power.total_power_mw:.2f} mW</td>
                        </tr>
                        <tr>
                            <td>Internal Power</td>
                            <td>{metrics.area_power.internal_power_mw:.2f} mW</td>
                        </tr>
                        <tr>
                            <td>Switching Power</td>
                            <td>{metrics.area_power.switching_power_mw:.2f} mW</td>
                        </tr>
                        <tr>
                            <td>Leakage Power</td>
                            <td>{metrics.area_power.leakage_power_mw:.3f} mW</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="toggleRawFiles()">
                    <h2>Parsed Report Files ({len(metrics.raw_files)})</h2>
                    <span id="rawToggleIcon" style="font-size: 0.85rem; color: var(--text-secondary);">▼ Show</span>
                </div>
                <ul id="rawFilesList" style="display: none; margin-top: 1rem; list-style: none; font-size: 0.85rem;">
                    {raw_files_items_html}
                </ul>
            </div>
        </div>
    </div>

    <div class="footer">
        Generated by <strong>PD Flow Toolkit (EDA Automation Suite)</strong> | Physical Design Analytics & Linter
    </div>

    <script>
        function filterDrcTable() {{
            const query = document.getElementById("drcSearchInput").value.toLowerCase();
            const rows = document.querySelectorAll("#drcTableBody tr");
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? "" : "none";
            }});
        }}

        function copySignoffSummary() {{
            const text = `PD Signoff: {metrics.design_name} ({metrics.tool_name} {metrics.stage}) - {status}\\n` +
                         `Setup WNS: {metrics.timing.setup_wns:+.3f} ns | Hold WNS: {metrics.timing.hold_wns:+.3f} ns\\n` +
                         `Total DRC: {metrics.drc.total_violations} | Peak Congestion: {metrics.congestion.max_pct:.1f}% | Utilization: {metrics.area_power.utilization_pct:.1f}%`;
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(text).then(() => {{
                    showCopiedFeedback();
                }}).catch(() => {{
                    fallbackCopy(text);
                }});
            }} else {{
                fallbackCopy(text);
            }}
        }}

        function showCopiedFeedback() {{
            const btn = document.getElementById("copySummaryBtn");
            const orig = btn.innerText;
            btn.innerText = "✓ Copied!";
            btn.style.borderColor = "#10b981";
            btn.style.color = "#34d399";
            setTimeout(() => {{
                btn.innerText = orig;
                btn.style.borderColor = "";
                btn.style.color = "";
            }}, 2000);
        }}

        function fallbackCopy(text) {{
            const ta = document.createElement("textarea");
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
            showCopiedFeedback();
        }}

        function toggleRawFiles() {{
            const list = document.getElementById("rawFilesList");
            const icon = document.getElementById("rawToggleIcon");
            if (list.style.display === "none") {{
                list.style.display = "block";
                icon.innerText = "▲ Hide";
            }} else {{
                list.style.display = "none";
                icon.innerText = "▼ Show";
            }}
        }}
    </script>
</body>
</html>
"""

    out_p = Path(output_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(html_content, encoding="utf-8")
    return str(out_p.resolve())
