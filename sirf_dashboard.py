#!/usr/bin/env python3
"""
SIRF Dashboard v2 - Beautiful UI + Real Claude AI Assistant
Run: python sirf_dashboard_v2.py
"""
import json, base64, socket, os
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

LOCAL_IP = get_local_ip()
PORT     = int(os.environ.get("PORT", 8050))

DATA_SOURCE = os.environ.get("DATA_SOURCE", "excel")
EXCEL_PATH  = os.environ.get("EXCEL_PATH", "SIRF_Inspection_Report.xlsx")
GSHEET_URL  = os.environ.get("GSHEET_URL", "")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── DATA PROCESSING ───────────────────────────────────────────────────────────
def norm_status_row(r):
    s  = str(r.get("Current Status", "")).strip()
    ig = str(r.get("INSPECTION GRADE", "")).strip()
    if s in ["Denied By Instituye", "NO INSPECTION"] or ig in ["", "nan"]:
        return "DENIED FOR INSPECTION"
    return s if s else "INSPECTED"

def process_df(raw_df):
    raw_df = raw_df.fillna("")
    def eff_grade(row):
        try:
            s  = str(row.get("Current Status", "")).strip()
            ig = str(row.get("INSPECTION GRADE", "")).strip()
            if s in ["Denied By Instituye", "NO INSPECTION"] or ig in ["", "nan"]:
                return "D"
            return ig
        except: return "D"
    def norm_status(s):
        s = str(s).strip()
        if s in ["Denied By Instituye", "NO INSPECTION"]:
            return "DENIED FOR INSPECTION"
        return s
    go_map = {"A": 1, "B": 2, "C": 3, "D": 4}
    def direction(b, a):
        if go_map.get(a, 0) > go_map.get(b, 0):   return "DOWNGRADE"
        elif go_map.get(a, 0) < go_map.get(b, 0): return "UPGRADE"
        return "NO CHANGE"
    def cs(v):
        if isinstance(v, str):
            v = "".join(c for c in v if 32 <= ord(c) < 127)
            v = v.replace("'", "").replace('"', "")
        return v

    if "INSTITUTE NAME" in raw_df.columns:
        raw_df["after"]  = raw_df.apply(eff_grade, axis=1)
        raw_df["before"] = raw_df["GRADE"].astype(str).str.strip()
        recs = []
        for _, r in raw_df.iterrows():
            b  = r["before"]
            a  = r["after"]
            tm = float(r["Total Marks"]) if isinstance(r.get("Total Marks", 0), (int, float)) else 0
            im = float(r["Inspection Total Marks"]) if isinstance(r.get("Inspection Total Marks", 0), (int, float)) else 0
            recs.append({
                "inst_code": int(r["INST Code"]) if r.get("INST Code", "") != "" else 0,
                "zone":      cs(str(r.get("Zone", ""))),
                "district":  cs(str(r.get("District", ""))),
                "inst_type": cs(str(r.get("INST ", "")).strip()),
                "name":      cs(str(r.get("INSTITUTE NAME", "")).strip()),
                "before": b, "sirf_marks": round(tm, 2),
                "after":  a, "insp_marks": round(im, 2),
                "delta":  round(im - tm, 2),
                "direction": direction(b, a),
                "path":   f"{b}->{a}",
                "status": cs(norm_status_row(r))
            })
        print(f"✓ Processed {len(recs)} institutes from Excel")
        return pd.DataFrame(recs)
    else:
        return raw_df

def load_data():
    try:
        if DATA_SOURCE == "gsheets" and GSHEET_URL:
            raw = pd.read_csv(GSHEET_URL)
            return process_df(raw)
        elif DATA_SOURCE == "excel" and os.path.exists(EXCEL_PATH):
            print(f"📊 Loading from Excel: {EXCEL_PATH}")
            raw = pd.read_excel(EXCEL_PATH)
            return process_df(raw)
        else:
            raise Exception("No data source available")
    except Exception as e:
        print(f"⚠ Data load error: {e}")
        raise

print("\n" + "="*60)
print("SIRF DASHBOARD v2 - LOADING DATA")
print("="*60)
df = load_data()
print(f"✓ Total institutes loaded: {len(df)}")
print("="*60 + "\n")

ZONES = sorted(df["zone"].unique())
TYPES = sorted(df["inst_type"].unique())
DISTS = sorted(df["district"].unique())

GC  = {"A": "#00f5a0", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
PLT = dict(
    plot_bgcolor  = "rgba(0,0,0,0)",
    paper_bgcolor = "rgba(0,0,0,0)",
    font          = dict(color="#94a3b8", family="'Space Mono', monospace"),
    margin        = dict(l=10, r=10, t=40, b=10)
)

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
def get_filtered(zone="ALL", dist="ALL", itype="ALL", status_f="ALL", search=""):
    f = df.copy()
    if zone    != "ALL": f = f[f["zone"]      == zone]
    if dist    != "ALL": f = f[f["district"]  == dist]
    if itype   != "ALL": f = f[f["inst_type"] == itype]
    if status_f!= "ALL": f = f[f["status"]    == status_f]
    if search:           f = f[f["name"].str.contains(search, case=False, na=False)]
    return f

def kpi_card(title, val, color, icon):
    return html.Div([
        html.Div(icon, style={"fontSize": "1.6rem", "marginBottom": "4px"}),
        html.Div(str(val), style={
            "fontSize": "2.4rem", "fontWeight": "900",
            "color": color, "lineHeight": "1",
            "fontFamily": "'Space Mono', monospace",
            "textShadow": f"0 0 20px {color}60"
        }),
        html.Div(title, style={
            "fontSize": "0.6rem", "color": "#475569",
            "textTransform": "uppercase", "letterSpacing": ".12em",
            "marginTop": "4px", "fontWeight": "600"
        }),
    ], style={
        "background": "linear-gradient(135deg, #0d1117 0%, #161b22 100%)",
        "border": f"1px solid {color}30",
        "borderRadius": "16px", "padding": "20px 16px",
        "textAlign": "center", "position": "relative", "overflow": "hidden",
        "boxShadow": f"0 4px 24px {color}15, inset 0 1px 0 rgba(255,255,255,0.05)"
    })

def fig_bar(bc, ac):
    g   = ["A", "B", "C", "D"]
    col = [GC[x] for x in g]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Before (SIRF)", x=g, y=[bc.get(x, 0) for x in g],
        marker_color=["rgba(0,245,160,0.15)", "rgba(59,130,246,0.15)",
                      "rgba(245,158,11,0.15)", "rgba(239,68,68,0.15)"],
        marker_line_color=col, marker_line_width=2,
        text=[bc.get(x, 0) for x in g], textposition="outside",
        textfont=dict(color=col, size=12, family="Space Mono")))
    fig.add_trace(go.Bar(
        name="After (Inspection)", x=g, y=[ac.get(x, 0) for x in g],
        marker_color=col, opacity=0.85,
        text=[ac.get(x, 0) for x in g], textposition="outside",
        textfont=dict(color="#fff", size=12, family="Space Mono")))
    fig.update_layout(**PLT,
        title=dict(text="Grade Comparison: Before vs After", font=dict(size=13, color="#64748b")),
        barmode="group",
        xaxis=dict(gridcolor="#1e293b", tickfont=dict(size=14, family="Space Mono")),
        yaxis=dict(gridcolor="#1e293b"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)))
    return fig

def fig_pie(fdf):
    dn = len(fdf[fdf["direction"] == "DOWNGRADE"])
    up = len(fdf[fdf["direction"] == "UPGRADE"])
    sm = len(fdf[fdf["direction"] == "NO CHANGE"])
    de = len(fdf[fdf["status"]    == "DENIED FOR INSPECTION"])
    fig = go.Figure(go.Pie(
        labels=["Downgrade", "Upgrade", "No Change", "Not Ranked"],
        values=[dn, up, sm, de], hole=0.62,
        marker_colors=["#ef4444", "#00f5a0", "#475569", "#f97316"],
        textfont=dict(size=10, family="Space Mono"),
        hovertemplate="%{label}<br><b>%{value}</b> institutes<br>%{percent}<extra></extra>"))
    fig.add_annotation(
        text=f"<b>{len(fdf)}</b><br><span style='font-size:10px'>TOTAL</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=18, color="#e2e8f0", family="Space Mono"))
    fig.update_layout(**PLT,
        title=dict(text="Grade Direction Overview", font=dict(size=13, color="#64748b")),
        height=320, showlegend=True,
        legend=dict(orientation="h", y=-0.15, font=dict(size=9), bgcolor="rgba(0,0,0,0)"))
    return fig

def fig_grade_a(fdf):
    a  = fdf[fdf["before"] == "A"]
    t  = len(a)
    if t == 0:
        return go.Figure().update_layout(**PLT, title="Grade A Changes (no data)")
    aa = len(a[a["after"] == "A"])
    ab = len(a[a["after"] == "B"])
    ac2= len(a[a["after"] == "C"])
    ad = len(a[a["after"] == "D"])
    fig = go.Figure(go.Pie(
        labels=[f"Retained A ({aa})", f"A→B ({ab})", f"A→C ({ac2})", f"A→D ({ad})"],
        values=[aa, ab, ac2, ad], hole=0.62,
        marker_colors=["#00f5a0", "#f59e0b", "#ef4444", "#dc2626"],
        textinfo="percent", textfont=dict(size=10, color="#fff", family="Space Mono"),
        hovertemplate="%{label}<br>Count: %{value}<extra></extra>"))
    fig.add_annotation(text=f"<b>{t}</b><br>A Grade",
        x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#00f5a0", family="Space Mono"))
    fig.update_layout(**PLT, title=dict(text="Grade A — What Changed?", font=dict(size=13, color="#64748b")),
        height=300, showlegend=True,
        legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=9), bgcolor="rgba(0,0,0,0)"))
    return fig

def fig_grade_d(fdf):
    d  = fdf[fdf["before"] == "D"]
    t  = len(d)
    if t == 0:
        return go.Figure().update_layout(**PLT, title="Grade D Changes (no data)")
    dd = len(d[d["after"] == "D"])
    dc = len(d[d["after"] == "C"])
    db = len(d[d["after"] == "B"])
    fig = go.Figure(go.Pie(
        labels=[f"Stayed D ({dd})", f"D→C ({dc})", f"D→B ({db})"],
        values=[dd, dc, db], hole=0.62,
        marker_colors=["#ef4444", "#f59e0b", "#3b82f6"],
        textinfo="percent", textfont=dict(size=10, color="#fff", family="Space Mono"),
        hovertemplate="%{label}<br>Count: %{value}<extra></extra>"))
    fig.add_annotation(text=f"<b>{t}</b><br>D Grade",
        x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#ef4444", family="Space Mono"))
    fig.update_layout(**PLT, title=dict(text="Grade D — What Changed?", font=dict(size=13, color="#64748b")),
        height=300, showlegend=True,
        legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=9), bgcolor="rgba(0,0,0,0)"))
    return fig

# ── DASH APP ──────────────────────────────────────────────────────────────────
app = dash.Dash(__name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap"
    ])
app.title = "SIRF Inspection Dashboard | UP 2026"

# ── CUSTOM CSS ────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
* { box-sizing: border-box; }
body {
    background: #060a0f !important;
    font-family: 'Syne', sans-serif;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 2px; }

.dash-dropdown .Select-control {
    background: #0d1117 !important;
    border: 1px solid #1e293b !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
.dash-dropdown .Select-menu-outer {
    background: #0d1117 !important;
    border: 1px solid #1e293b !important;
}
.dash-dropdown .Select-option {
    background: #0d1117 !important;
    color: #94a3b8 !important;
    font-size: 0.8rem;
}
.dash-dropdown .Select-option:hover,
.dash-dropdown .Select-option.is-focused {
    background: #161b22 !important;
    color: #e2e8f0 !important;
}
.dash-dropdown .Select-value-label { color: #e2e8f0 !important; }
.dash-dropdown .Select-arrow { border-top-color: #475569 !important; }

.glow-border {
    box-shadow: 0 0 0 1px rgba(0,245,160,0.1), 0 8px 32px rgba(0,0,0,0.4);
}
.ai-panel {
    background: linear-gradient(135deg, #060a0f 0%, #0d1117 50%, #060a0f 100%);
    border: 1px solid rgba(0,245,160,0.15);
    border-radius: 20px;
    position: relative;
    overflow: hidden;
}
.ai-panel::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 30%, rgba(0,245,160,0.03) 0%, transparent 60%);
    pointer-events: none;
}
.ai-input {
    background: rgba(13,17,23,0.8) !important;
    border: 1px solid #1e293b !important;
    color: #e2e8f0 !important;
    border-radius: 12px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
    transition: border-color 0.2s;
}
.ai-input:focus {
    border-color: rgba(0,245,160,0.4) !important;
    box-shadow: 0 0 0 3px rgba(0,245,160,0.08) !important;
    outline: none !important;
}
.voice-btn {
    background: linear-gradient(135deg, #00f5a0, #00d4aa) !important;
    border: none !important;
    border-radius: 12px !important;
    color: #060a0f !important;
    font-weight: 700 !important;
    transition: all 0.2s !important;
}
.voice-btn:hover {
    transform: scale(1.05) !important;
    box-shadow: 0 4px 20px rgba(0,245,160,0.4) !important;
}
.ask-btn {
    background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
    transition: all 0.2s !important;
}
.ask-btn:hover {
    transform: scale(1.03) !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.4) !important;
}
.data-card {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    border: 1px solid #1e293b;
    border-radius: 16px;
    overflow: hidden;
}
.data-card-header {
    background: rgba(30,41,59,0.5);
    border-bottom: 1px solid #1e293b;
    padding: 12px 16px;
}
.inst-table tr:hover td { background: rgba(30,41,59,0.5) !important; transition: 0.15s; }
.inst-table td, .inst-table th {
    padding: 8px 12px !important;
    border-bottom: 1px solid rgba(30,41,59,0.5) !important;
}
.badge-A { background: rgba(0,245,160,0.15); color: #00f5a0; padding: 2px 8px; border-radius: 6px; font-family: Space Mono; font-size: 0.75rem; }
.badge-B { background: rgba(59,130,246,0.15); color: #3b82f6; padding: 2px 8px; border-radius: 6px; font-family: Space Mono; font-size: 0.75rem; }
.badge-C { background: rgba(245,158,11,0.15); color: #f59e0b; padding: 2px 8px; border-radius: 6px; font-family: Space Mono; font-size: 0.75rem; }
.badge-D { background: rgba(239,68,68,0.15); color: #ef4444; padding: 2px 8px; border-radius: 6px; font-family: Space Mono; font-size: 0.75rem; }
.dir-UP { color: #00f5a0; font-size: 0.7rem; }
.dir-DOWN { color: #ef4444; font-size: 0.7rem; }
.dir-NO { color: #475569; font-size: 0.7rem; }
"""

# ── LAYOUT ────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    html.Style(CUSTOM_CSS),
    dbc.Container([

        # ── HEADER ──────────────────────────────────────────────────────────
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("SIRF", style={
                            "fontSize": "2.8rem", "fontWeight": "800",
                            "color": "#00f5a0", "fontFamily": "Syne",
                            "letterSpacing": "-1px",
                            "textShadow": "0 0 40px rgba(0,245,160,0.5)"
                        }),
                        html.Span(" INSPECTION", style={
                            "fontSize": "2.8rem", "fontWeight": "800",
                            "color": "#e2e8f0", "fontFamily": "Syne",
                            "letterSpacing": "-1px"
                        }),
                    ]),
                    html.Div([
                        html.Span("DASHBOARD", style={
                            "fontSize": "2.8rem", "fontWeight": "800",
                            "color": "#e2e8f0", "fontFamily": "Syne",
                            "letterSpacing": "-1px"
                        }),
                    ]),
                    html.Div([
                        html.Span("◆ ", style={"color": "#00f5a0", "fontSize": "0.6rem"}),
                        html.Span("2079 Institutes", style={"color": "#475569", "fontSize": "0.72rem", "fontFamily": "Space Mono"}),
                        html.Span("  ◆  ", style={"color": "#1e293b", "fontSize": "0.6rem"}),
                        html.Span("Uttar Pradesh", style={"color": "#475569", "fontSize": "0.72rem", "fontFamily": "Space Mono"}),
                        html.Span("  ◆  ", style={"color": "#1e293b", "fontSize": "0.6rem"}),
                        html.Span("April 2026", style={"color": "#475569", "fontSize": "0.72rem", "fontFamily": "Space Mono"}),
                    ], style={"marginTop": "6px"}),
                ], md=5),

                # ── AI ASSISTANT PANEL ───────────────────────────────────────
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.Div([
                                html.Span("⬡", style={"color": "#00f5a0", "fontSize": "0.8rem", "marginRight": "6px"}),
                                html.Span("AI ASSISTANT", style={
                                    "fontSize": "0.6rem", "color": "#00f5a0",
                                    "fontFamily": "Space Mono", "letterSpacing": ".15em",
                                    "fontWeight": "700"
                                }),
                                html.Span(" — Powered by Claude", style={
                                    "fontSize": "0.55rem", "color": "#334155",
                                    "fontFamily": "Space Mono"
                                }),
                            ], style={"marginBottom": "10px"}),

                            dbc.Row([
                                dbc.Col(
                                    dbc.Button("🎤", id="voice-btn", size="sm", className="voice-btn w-100"),
                                    xs=2),
                                dbc.Col(
                                    dbc.Input(id="q-inp",
                                        placeholder="Ask about institutes, grades, zones...",
                                        className="ai-input", style={"height": "38px"}),
                                    xs=7),
                                dbc.Col(
                                    dbc.Button("ASK", id="ask-btn", size="sm", className="ask-btn w-100"),
                                    xs=3),
                            ], className="g-2"),

                            html.Div(id="ai-out", style={"marginTop": "10px", "minHeight": "20px"}),
                        ], style={"padding": "16px"}),
                    ], className="ai-panel"),
                ], md=7),
            ], className="g-3", align="center"),
        ], style={"padding": "24px 0 20px 0"}),

        # ── FILTERS ─────────────────────────────────────────────────────────
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Label("ZONE", style={"fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="f-zone",
                        options=[{"label": "All Zones", "value": "ALL"}] + [{"label": z, "value": z} for z in ZONES],
                        value="ALL", clearable=False, style={"fontSize": "0.78rem"}),
                ], md=2, xs=6),
                dbc.Col([
                    html.Label("DISTRICT", style={"fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="f-dist",
                        options=[{"label": "All Districts", "value": "ALL"}] + [{"label": d, "value": d} for d in DISTS],
                        value="ALL", clearable=False, style={"fontSize": "0.78rem"}),
                ], md=2, xs=6),
                dbc.Col([
                    html.Label("TYPE", style={"fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="f-type",
                        options=[{"label": "All Types", "value": "ALL"}] + [{"label": t, "value": t} for t in TYPES],
                        value="ALL", clearable=False, style={"fontSize": "0.78rem"}),
                ], md=2, xs=6),
                dbc.Col([
                    html.Label("STATUS", style={"fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700", "display": "block", "marginBottom": "4px"}),
                    dcc.Dropdown(id="f-status",
                        options=[
                            {"label": "All", "value": "ALL"},
                            {"label": "Denied / Not Ranked", "value": "DENIED FOR INSPECTION"},
                            {"label": "No Change", "value": "NO CHANGE"},
                        ],
                        value="ALL", clearable=False, style={"fontSize": "0.78rem"}),
                ], md=2, xs=6),
                dbc.Col([
                    html.Label("SEARCH", style={"fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700", "display": "block", "marginBottom": "4px"}),
                    dbc.Input(id="srch", placeholder="Institute name...", className="ai-input",
                        style={"height": "38px"}),
                ], md=3, xs=9),
                dbc.Col([
                    html.Label(".", style={"fontSize": "0.58rem", "color": "transparent", "display": "block", "marginBottom": "4px"}),
                    dbc.Button("↺ Reset", id="reset-btn", className="w-100",
                        style={"background": "#1e293b", "border": "none", "borderRadius": "10px",
                               "color": "#94a3b8", "fontFamily": "Space Mono", "fontSize": "0.72rem",
                               "height": "38px"}),
                ], md=1, xs=3),
            ], className="g-2"),
        ], style={
            "background": "linear-gradient(135deg, #0d1117 0%, #161b22 100%)",
            "border": "1px solid #1e293b", "borderRadius": "16px",
            "padding": "16px", "marginBottom": "20px"
        }),

        # ── KPI STRIP ───────────────────────────────────────────────────────
        html.Div(id="kpi-strip", className="mb-4"),

        # ── CHARTS ROW 1 ────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(html.Div([
                html.Div([
                    html.Span("GRADE SUMMARY", style={
                        "fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700"
                    }),
                ], className="data-card-header"),
                html.Div(id="ba-table", style={"padding": "16px"}),
            ], className="data-card"), md=5, className="mb-4"),

            dbc.Col(html.Div([
                dcc.Graph(id="fig-pie", config={"displayModeBar": False},
                    style={"background": "transparent"})
            ], className="data-card", style={"padding": "8px"}), md=7, className="mb-4"),
        ]),

        # ── BAR CHART ───────────────────────────────────────────────────────
        html.Div([
            dcc.Graph(id="fig-bar", config={"displayModeBar": False})
        ], className="data-card mb-4", style={"padding": "8px"}),

        # ── GRADE A & D BREAKDOWN ────────────────────────────────────────────
        html.Div([
            html.Div([
                html.Span("GRADE A & D — CHANGE BREAKDOWN", style={
                    "fontSize": "0.58rem", "color": "#334155",
                    "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700"
                }),
            ], className="data-card-header"),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span(id="grade-a-count", style={
                            "fontSize": "1.8rem", "fontWeight": "900",
                            "color": "#00f5a0", "fontFamily": "Space Mono",
                            "textShadow": "0 0 20px rgba(0,245,160,0.5)"
                        }),
                        html.Span(" institutes — Grade A before", style={
                            "color": "#334155", "fontSize": "0.72rem", "fontFamily": "Space Mono"
                        }),
                    ], style={"textAlign": "center", "padding": "12px 0 0 0"}),
                    dcc.Graph(id="fig-grade-a", config={"displayModeBar": False}),
                ], md=6),
                dbc.Col([
                    html.Div([
                        html.Span(id="grade-d-count", style={
                            "fontSize": "1.8rem", "fontWeight": "900",
                            "color": "#ef4444", "fontFamily": "Space Mono",
                            "textShadow": "0 0 20px rgba(239,68,68,0.5)"
                        }),
                        html.Span(" institutes — Grade D before", style={
                            "color": "#334155", "fontSize": "0.72rem", "fontFamily": "Space Mono"
                        }),
                    ], style={"textAlign": "center", "padding": "12px 0 0 0"}),
                    dcc.Graph(id="fig-grade-d", config={"displayModeBar": False}),
                ], md=6),
            ]),
        ], className="data-card mb-4"),

        # ── NOT RANKED SECTION ───────────────────────────────────────────────
        html.Div(id="denied-section"),

        # ── INSTITUTE TABLE ──────────────────────────────────────────────────
        html.Div([
            html.Div([
                dbc.Row([
                    dbc.Col(html.Span("INSTITUTE-WISE DETAIL", style={
                        "fontSize": "0.58rem", "color": "#334155",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700"
                    }), md=4),
                    dbc.Col(dbc.Input(id="tbl-srch", placeholder="Search institute...",
                        className="ai-input", style={"height": "30px", "fontSize": "0.72rem"}), md=8),
                ], align="center"),
            ], className="data-card-header"),
            html.Div([
                html.Div(id="inst-count", style={
                    "color": "#334155", "fontSize": "0.65rem",
                    "fontFamily": "Space Mono", "marginBottom": "10px"
                }),
                html.Div(id="inst-table", style={
                    "overflowX": "auto", "overflowY": "auto", "maxHeight": "480px"
                }),
            ], style={"padding": "14px"}),
        ], className="data-card mb-4"),

        # ── FOOTER ──────────────────────────────────────────────────────────
        html.Div([
            html.Span("◆ ", style={"color": "#1e293b"}),
            html.Span("SIRF Inspection Report · UP · 2079 Institutes · April 2026 · Python Dash + Claude AI",
                style={"color": "#1e293b", "fontSize": "0.62rem", "fontFamily": "Space Mono"}),
        ], style={"textAlign": "center", "padding": "20px 0 10px 0"}),

    ], fluid=True),
], style={"background": "#060a0f", "minHeight": "100vh"})

# ── VOICE JS ──────────────────────────────────────────────────────────────────
VOICE_JS = """
function(n){
    if(!n) return "";
    var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){alert("Voice only works in Chrome!");return "";}
    var r=new SR(); r.lang="hi-IN"; r.interimResults=false;
    r.onresult=function(e){
        var t=e.results[0][0].transcript;
        var el=document.getElementById("q-inp");
        var s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,"value").set;
        s.call(el,t); el.dispatchEvent(new Event("input",{bubbles:true}));
        document.getElementById("ask-btn").click();
    };
    r.onerror=function(e){console.log("Speech error:",e.error);}; r.start(); return "";
}
"""
app.clientside_callback(VOICE_JS, Output("ai-out", "children"), Input("voice-btn", "n_clicks"), prevent_initial_call=True)

# ── MAIN CALLBACK ─────────────────────────────────────────────────────────────
@app.callback(
    Output("ba-table",     "children"),
    Output("fig-pie",      "figure"),
    Output("fig-bar",      "figure"),
    Output("fig-grade-a",  "figure"),
    Output("fig-grade-d",  "figure"),
    Output("grade-a-count","children"),
    Output("grade-d-count","children"),
    Output("kpi-strip",    "children"),
    Output("denied-section","children"),
    Output("inst-count",   "children"),
    Output("inst-table",   "children"),
    Input("f-zone",   "value"),
    Input("f-dist",   "value"),
    Input("f-type",   "value"),
    Input("f-status", "value"),
    Input("srch",     "value"),
    Input("tbl-srch", "value"),
    Input("reset-btn","n_clicks"),
    Input("ask-btn",  "n_clicks"),
    State("q-inp",    "value"),
)
def update_dashboard(fzone, fdist, ftype, fstat, srch, tbl_srch, reset_n, ask_n, q):
    ctx = callback_context
    if ctx.triggered and ctx.triggered[0]["prop_id"] == "reset-btn.n_clicks":
        fzone = fdist = ftype = fstat = srch = tbl_srch = q = ""

    f = get_filtered(fzone, fdist, ftype, fstat, srch)

    total = len(f)
    dn    = len(f[f["direction"] == "DOWNGRADE"])
    up    = len(f[f["direction"] == "UPGRADE"])
    sm    = len(f[f["direction"] == "NO CHANGE"])
    de    = len(f[f["status"]    == "DENIED FOR INSPECTION"])

    # KPI STRIP
    kpis = dbc.Row([
        dbc.Col(kpi_card("Total Institutes", total, "#818cf8", "🏛️"), md=2, xs=6, className="mb-3"),
        dbc.Col(kpi_card("Downgraded",       dn,    "#ef4444", "📉"), md=2, xs=6, className="mb-3"),
        dbc.Col(kpi_card("Upgraded",         up,    "#00f5a0", "📈"), md=2, xs=6, className="mb-3"),
        dbc.Col(kpi_card("No Change",        sm,    "#475569", "➡️"), md=2, xs=6, className="mb-3"),
        dbc.Col(kpi_card("Not Ranked",       de,    "#f97316", "⚠️"), md=2, xs=6, className="mb-3"),
    ], className="g-3")

    # GRADE SUMMARY TABLE
    bc = f["before"].value_counts().to_dict()
    ac = f["after"].value_counts().to_dict()

    def grade_row(g, color):
        b_val = bc.get(g, 0)
        a_val = ac.get(g, 0)
        diff  = a_val - b_val
        diff_color = "#00f5a0" if diff > 0 else ("#ef4444" if diff < 0 else "#475569")
        diff_str   = f"+{diff}" if diff > 0 else str(diff)
        return html.Tr([
            html.Td(html.Span(f"Grade {g}", className=f"badge-{g}"), style={"padding": "10px 12px"}),
            html.Td(str(b_val), style={"textAlign": "center", "color": "#64748b", "fontFamily": "Space Mono", "fontSize": "0.85rem"}),
            html.Td(str(a_val), style={"textAlign": "center", "color": color, "fontFamily": "Space Mono", "fontSize": "0.85rem", "fontWeight": "700"}),
            html.Td(diff_str,   style={"textAlign": "center", "color": diff_color, "fontFamily": "Space Mono", "fontSize": "0.8rem"}),
        ])

    ba = html.Table([
        html.Thead(html.Tr([
            html.Th("Grade",    style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "padding": "8px 12px", "borderBottom": "1px solid #1e293b"}),
            html.Th("Before",   style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
            html.Th("After",    style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
            html.Th("Change",   style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
        ])),
        html.Tbody([
            grade_row("A", "#00f5a0"),
            grade_row("B", "#3b82f6"),
            grade_row("C", "#f59e0b"),
            grade_row("D", "#ef4444"),
        ])
    ], style={"width": "100%", "borderCollapse": "collapse"})

    # GRADE A/D COUNTS
    gac = len(f[f["before"] == "A"])
    gdc = len(f[f["before"] == "D"])

    # NOT RANKED SECTION
    denied_f = f[f["status"] == "DENIED FOR INSPECTION"]
    if len(denied_f) > 0:
        denied_rows = [
            html.Tr([
                html.Td(r["name"][:40], style={"color": "#818cf8", "fontSize": "0.78rem", "fontFamily": "Space Mono", "padding": "7px 12px"}),
                html.Td(r["zone"],      style={"fontSize": "0.72rem", "color": "#475569", "padding": "7px 8px"}),
                html.Td(r["district"],  style={"fontSize": "0.72rem", "color": "#475569", "padding": "7px 8px"}),
            ]) for _, r in denied_f.head(20).iterrows()
        ]
        denied_sec = html.Div([
            html.Div([
                html.Span("⚠ ", style={"color": "#f97316"}),
                html.Span(f"NOT RANKED / DENIED — {len(denied_f)} institutes", style={
                    "fontSize": "0.6rem", "color": "#f97316",
                    "fontFamily": "Space Mono", "letterSpacing": ".1em", "fontWeight": "700"
                }),
            ], className="data-card-header"),
            html.Div(
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Institute", style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "padding": "6px 12px", "borderBottom": "1px solid #1e293b"}),
                        html.Th("Zone",      style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "borderBottom": "1px solid #1e293b"}),
                        html.Th("District",  style={"color": "#334155", "fontSize": "0.6rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "borderBottom": "1px solid #1e293b"}),
                    ])),
                    html.Tbody(denied_rows),
                ], style={"width": "100%", "borderCollapse": "collapse"}),
                style={"padding": "12px", "overflowX": "auto"}
            ),
        ], className="data-card mb-4")
    else:
        denied_sec = html.Div()

    # INSTITUTE TABLE
    t_f = f[f["name"].str.contains(tbl_srch, case=False, na=False)] if tbl_srch else f

    def dir_badge(d):
        if d == "DOWNGRADE": return html.Span("▼ DOWN", className="dir-DOWN")
        if d == "UPGRADE":   return html.Span("▲ UP",   className="dir-UP")
        return html.Span("— SAME", className="dir-NO")

    if len(t_f) > 0:
        inst_rows = [
            html.Tr([
                html.Td(r["name"][:38], style={"color": "#94a3b8", "fontSize": "0.75rem", "fontFamily": "Space Mono", "padding": "7px 12px"}),
                html.Td(r["zone"],      style={"fontSize": "0.7rem",  "color": "#475569"}),
                html.Td(r["district"],  style={"fontSize": "0.7rem",  "color": "#475569"}),
                html.Td(html.Span(r["before"], className=f"badge-{r['before']}"), style={"textAlign": "center"}),
                html.Td(html.Span(r["after"],  className=f"badge-{r['after']}"),  style={"textAlign": "center"}),
                html.Td(dir_badge(r["direction"]), style={"textAlign": "center"}),
            ]) for _, r in t_f.head(150).iterrows()
        ]
        inst_tbl = html.Table([
            html.Thead(html.Tr([
                html.Th("Institute", style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "padding": "6px 12px", "borderBottom": "1px solid #1e293b"}),
                html.Th("Zone",     style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "borderBottom": "1px solid #1e293b"}),
                html.Th("District", style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "borderBottom": "1px solid #1e293b"}),
                html.Th("Before",   style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
                html.Th("After",    style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
                html.Th("Status",   style={"color": "#334155", "fontSize": "0.58rem", "fontFamily": "Space Mono", "letterSpacing": ".1em", "textAlign": "center", "borderBottom": "1px solid #1e293b"}),
            ])),
            html.Tbody(inst_rows, className="inst-table"),
        ], style={"width": "100%", "borderCollapse": "collapse"})
        inst_cnt = html.Span(f"SHOWING {min(150, len(t_f))} OF {len(f)} INSTITUTES",
            style={"color": "#334155", "fontSize": "0.62rem", "fontFamily": "Space Mono", "letterSpacing": ".08em"})
    else:
        inst_tbl = html.Div("No institutes found", style={"color": "#334155", "textAlign": "center", "padding": "30px", "fontFamily": "Space Mono", "fontSize": "0.8rem"})
        inst_cnt = html.Span("")

    # AI ANSWER (with Claude API if key set, else local)
    if ctx.triggered and ctx.triggered[0]["prop_id"] == "ask-btn.n_clicks" and q:
        ai_out = get_ai_answer(q, f)
    else:
        ai_out = html.Div()

    return (ba, fig_pie(f), fig_bar(bc, ac), fig_grade_a(f), fig_grade_d(f),
            str(gac), str(gdc), kpis, denied_sec, inst_cnt, inst_tbl)


def get_ai_answer(q, fdf):
    """Use Claude API if key available, else local logic."""
    total = len(fdf)
    dn    = len(fdf[fdf["direction"] == "DOWNGRADE"])
    up    = len(fdf[fdf["direction"] == "UPGRADE"])
    sm    = len(fdf[fdf["direction"] == "NO CHANGE"])
    de    = len(fdf[fdf["status"]    == "DENIED FOR INSPECTION"])
    bc    = fdf["before"].value_counts().to_dict()
    ac    = fdf["after"].value_counts().to_dict()

    # Try Claude API
    if CLAUDE_API_KEY:
        try:
            import urllib.request
            context = f"""You are a SIRF (State Inspection and Ranking Framework) data assistant for UP polytechnic institutes.
Current filtered data summary:
- Total institutes: {total}
- Downgraded: {dn}, Upgraded: {up}, No Change: {sm}, Not Ranked (denied): {de}
- Before grades: A={bc.get('A',0)}, B={bc.get('B',0)}, C={bc.get('C',0)}, D={bc.get('D',0)}
- After grades:  A={ac.get('A',0)}, B={ac.get('B',0)}, C={ac.get('C',0)}, D={ac.get('D',0)}
Answer in 2-4 lines. Use numbers. Be direct and helpful."""

            payload = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": context,
                "messages": [{"role": "user", "content": q}]
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "x-api-key": CLAUDE_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result  = json.loads(resp.read().decode())
                ai_text = result["content"][0]["text"]

            return html.Div([
                html.Div([
                    html.Span("⬡ ", style={"color": "#00f5a0", "fontSize": "0.7rem"}),
                    html.Span("CLAUDE AI", style={"fontSize": "0.55rem", "color": "#00f5a0",
                        "fontFamily": "Space Mono", "letterSpacing": ".12em", "fontWeight": "700"}),
                ], style={"marginBottom": "4px"}),
                dcc.Markdown(ai_text, style={
                    "color": "#94a3b8", "fontSize": "0.75rem",
                    "fontFamily": "Space Mono", "lineHeight": "1.6",
                    "margin": "0"
                }),
            ], style={
                "background": "rgba(0,245,160,0.05)",
                "border": "1px solid rgba(0,245,160,0.15)",
                "borderRadius": "10px", "padding": "10px 14px"
            })
        except Exception as e:
            print(f"Claude API error: {e}")

    # Local fallback
    q_low = q.lower()
    if any(w in q_low for w in ["total", "how many", "kitne"]):
        ans = f"Total **{total}** institutes. Grades before: A={bc.get('A',0)}, B={bc.get('B',0)}, C={bc.get('C',0)}, D={bc.get('D',0)}. After: A={ac.get('A',0)}, B={ac.get('B',0)}, C={ac.get('C',0)}, D={ac.get('D',0)}."
    elif any(w in q_low for w in ["downgrade", "fell", "worse", "gira"]):
        ans = f"**{dn} institutes downgraded** ({round(dn/total*100) if total else 0}% of total). These were Grade A institutes that fell after inspection."
    elif any(w in q_low for w in ["upgrade", "improve", "better", "badha"]):
        ans = f"**{up} institutes upgraded** ({round(up/total*100) if total else 0}%). These were Grade D institutes that improved after inspection."
    elif any(w in q_low for w in ["denied", "not ranked", "refused"]):
        ans = f"**{de} institutes are NOT RANKED** — they denied or skipped inspection. Grade A/D without inspection lose ranking; Grade B/C retain SIRF grade."
    elif any(w in q_low for w in ["zone", "district"]):
        zc  = fdf["zone"].value_counts().head(3)
        ans = "Top zones: " + ", ".join([f"{z}: {c}" for z, c in zc.items()])
    else:
        ans = f"Current view: **{total} institutes** — {dn} downgraded, {up} upgraded, {sm} unchanged, {de} not ranked. Try asking about upgrades, downgrades, zones, or not-ranked institutes."

    return html.Div([
        html.Div([
            html.Span("⬡ ", style={"color": "#475569", "fontSize": "0.7rem"}),
            html.Span("LOCAL AI", style={"fontSize": "0.55rem", "color": "#475569",
                "fontFamily": "Space Mono", "letterSpacing": ".12em"}),
        ], style={"marginBottom": "4px"}),
        dcc.Markdown(ans, style={
            "color": "#94a3b8", "fontSize": "0.75rem",
            "fontFamily": "Space Mono", "lineHeight": "1.6", "margin": "0"
        }),
    ], style={
        "background": "rgba(71,85,105,0.08)",
        "border": "1px solid #1e293b",
        "borderRadius": "10px", "padding": "10px 14px"
    })


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("  SIRF DASHBOARD v2 — BEAUTIFUL EDITION")
    print(f"  Local  : http://127.0.0.1:{PORT}")
    print(f"  Mobile : http://{LOCAL_IP}:{PORT}")
    print(f"  Claude API: {'✓ Enabled' if CLAUDE_API_KEY else '✗ Not set (using local AI)'}")
    print(f"{'='*60}\n")
    app.run(debug=False, host="0.0.0.0", port=PORT)
