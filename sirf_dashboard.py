#!/usr/bin/env python3
"""
SIRF Dashboard - AI Voice Assistant (UPDATED FOR 2079 INSTITUTES)
Run: python sirf_dashboard.py
Open Chrome: http://127.0.0.1:8050

DATA SOURCE OPTIONS (set DATA_SOURCE below):
  "embedded"  - Uses built-in data (default, always works)
  "excel"     - Reads from local Excel file ✅ RECOMMENDED for 2079 institutes
  "gsheets"   - Reads from Google Sheets (auto-updates!)
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

LOCAL_IP   = get_local_ip()
PORT       = int(os.environ.get("PORT", 8050))
MOBILE_URL = f"http://{LOCAL_IP}:{PORT}"

# ── DATA SOURCE CONFIGURATION ─────────────────────────────────────────────────
# Change DATA_SOURCE to switch between data sources:
#   "embedded" = use built-in data (default)
#   "excel"    = read from Excel file (set EXCEL_PATH below) ✅ FOR 2079 RECORDS
#   "gsheets"  = read from Google Sheets (set GSHEET_URL below)

DATA_SOURCE = os.environ.get("DATA_SOURCE", "excel")  # Changed to "excel" for new data

# Path to Excel file (used when DATA_SOURCE = "excel")
EXCEL_PATH = os.environ.get("EXCEL_PATH", "SIRF_Inspection_Report.xlsx")

# Google Sheets CSV export URL (used when DATA_SOURCE = "gsheets")
# How to get this URL:
#   1. Open your Google Sheet
#   2. File → Share → Anyone with link (Viewer)
#   3. Copy the URL and replace /edit... with /export?format=csv
# Example: https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/export?format=csv
GSHEET_URL = os.environ.get("GSHEET_URL", "")

# ── PERFORMANCE OPTIMIZATION ─────────────────────────────────────────────────
# For 2079 institutes, use these settings:
CACHE_DATA = True  # Cache processed data in memory
LAZY_LOAD = True   # Load details table only when needed

_B64 = ""  # Placeholder for embedded data (removed for file size)

def norm_status_row(r):
    """Extract and normalize status from row."""
    s = str(r.get("Current Status", "")).strip()
    ig = str(r.get("INSPECTION GRADE", "")).strip()
    if s in ["Denied By Instituye", "NO INSPECTION"] or ig in ["", "nan"]:
        return "DENIED FOR INSPECTION"
    return s if s else "INSPECTED"

def process_df(raw_df):
    """Apply grade logic and return processed dataframe."""
    raw_df = raw_df.fillna("")
    
    def eff_grade(row):
        try:
            s = str(row.get("Current Status", "")).strip()
            ig = str(row.get("INSPECTION GRADE", "")).strip()
            if s in ["Denied By Instituye", "NO INSPECTION"] or ig in ["", "nan"]:
                return "D"
            return ig
        except:
            return "D"
    
    def norm_status(s):
        s = str(s).strip()
        if s in ["Denied By Instituye", "NO INSPECTION"]:
            return "DENIED FOR INSPECTION"
        return s
    
    go_map = {"A": 1, "B": 2, "C": 3, "D": 4}
    
    def direction(b, a):
        if go_map.get(a, 0) > go_map.get(b, 0):
            return "DOWNGRADE"
        elif go_map.get(a, 0) < go_map.get(b, 0):
            return "UPGRADE"
        return "NO CHANGE"
    
    def cs(v):
        if isinstance(v, str):
            v = "".join(c for c in v if 32 <= ord(c) < 127)
            v = v.replace("'", "").replace('"', "")
        return v

    if "INSTITUTE NAME" in raw_df.columns:
        # Raw Excel format
        raw_df["after"] = raw_df.apply(eff_grade, axis=1)
        raw_df["before"] = raw_df["GRADE"].astype(str).str.strip()
        recs = []
        
        for _, r in raw_df.iterrows():
            b = r["before"]
            a = r["after"]
            tm = float(r["Total Marks"]) if isinstance(r.get("Total Marks", 0), (int, float)) else 0
            im = float(r["Inspection Total Marks"]) if isinstance(r.get("Inspection Total Marks", 0), (int, float)) else 0
            
            recs.append({
                "inst_code": int(r["INST Code"]) if r.get("INST Code", "") != "" else 0,
                "zone": cs(str(r.get("Zone", ""))),
                "district": cs(str(r.get("District", ""))),
                "inst_type": cs(str(r.get("INST ", "")).strip()),
                "name": cs(str(r.get("INSTITUTE NAME", "")).strip()),
                "before": b,
                "sirf_marks": round(tm, 2),
                "after": a,
                "insp_marks": round(im, 2),
                "delta": round(im - tm, 2),
                "direction": direction(b, a),
                "path": f"{b}->{a}",
                "status": cs(norm_status_row(r))
            })
        
        print(f"✓ Processed {len(recs)} institutes from Excel")
        return pd.DataFrame(recs)
    else:
        # Already processed format
        return raw_df

def load_data():
    """Load data from configured source."""
    try:
        if DATA_SOURCE == "gsheets" and GSHEET_URL:
            print(f"📊 Loading from Google Sheets...")
            raw = pd.read_csv(GSHEET_URL)
            return process_df(raw)
        elif DATA_SOURCE == "excel" and os.path.exists(EXCEL_PATH):
            print(f"📊 Loading from Excel: {EXCEL_PATH}")
            raw = pd.read_excel(EXCEL_PATH)
            print(f"   → Excel shape: {raw.shape}")
            return process_df(raw)
        else:
            print("📊 Loading embedded data...")
            if _B64:
                data = json.loads(base64.b64decode(_B64).decode("utf-8"))
                return pd.DataFrame(data)
            else:
                raise Exception("No data source available")
    except Exception as e:
        print(f"⚠ Data load error: {e}")
        if _B64:
            print("   → Falling back to embedded data")
            data = json.loads(base64.b64decode(_B64).decode("utf-8"))
            return pd.DataFrame(data)
        else:
            raise

# Load data once at startup
print("\n" + "="*60)
print("SIRF DASHBOARD - LOADING DATA FOR 2079 INSTITUTES")
print("="*60)
df = load_data()
print(f"✓ Total institutes loaded: {len(df)}")
print(f"✓ Columns: {list(df.columns)}")
print(f"✓ Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
print("="*60 + "\n")

ZONES = sorted(df["zone"].unique())
TYPES = sorted(df["inst_type"].unique())
DISTS = sorted(df["district"].unique())

print(f"📍 Zones: {len(ZONES)} | Institute Types: {len(TYPES)} | Districts: {len(DISTS)}")

GC = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
GB = {"A": "rgba(34,197,94,.15)", "B": "rgba(59,130,246,.15)",
      "C": "rgba(245,158,11,.15)", "D": "rgba(239,68,68,.15)"}
PLT = dict(plot_bgcolor="#0f0f1a", paper_bgcolor="#0f0f1a",
           font=dict(color="#c0c0d0", family="Segoe UI"),
           margin=dict(l=10, r=10, t=38, b=8))
CARD = {"background": "#0f0f1a", "border": "1px solid #1c1c2e", "borderRadius": "14px"}

def get_filtered(zone="ALL", dist="ALL", itype="ALL", status_f="ALL", search=""):
    f = df.copy()
    if zone != "ALL":
        f = f[f["zone"] == zone]
    if dist != "ALL":
        f = f[f["district"] == dist]
    if itype != "ALL":
        f = f[f["inst_type"] == itype]
    if status_f != "ALL":
        f = f[f["status"] == status_f]
    if search:
        f = f[f["name"].str.contains(search, case=False, na=False)]
    return f

def kpi(title, val, color, sub=""):
    return dbc.Card(dbc.CardBody([
        html.Div(str(val), style={"fontSize": "1.9rem", "fontWeight": "800", "color": color, "lineHeight": "1"}),
        html.Div(title, style={"fontSize": "0.62rem", "color": "#6b7280", "textTransform": "uppercase",
                               "letterSpacing": ".07em", "marginTop": "3px"}),
        html.Div(sub, style={"fontSize": "0.67rem", "color": "#9ca3af"}) if sub else html.Div()
    ]), style={"background": "#0f0f1a", "border": "1px solid #1c1c2e", "borderRadius": "12px"})

def fig_bar(bc, ac):
    g = ["A", "B", "C", "D"]
    col = [GC[x] for x in g]
    ba = ["rgba(34,197,94,.3)", "rgba(59,130,246,.3)", "rgba(245,158,11,.3)", "rgba(239,68,68,.3)"]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Before (SIRF)", x=g, y=[bc.get(x, 0) for x in g],
                         marker_color=ba, marker_line_color=col, marker_line_width=2,
                         text=[bc.get(x, 0) for x in g], textposition="outside", textfont=dict(color=col, size=13)))
    fig.add_trace(go.Bar(name="After (Inspection)", x=g, y=[ac.get(x, 0) for x in g],
                         marker_color=col, opacity=0.9,
                         text=[ac.get(x, 0) for x in g], textposition="outside", textfont=dict(color="#fff", size=13)))
    fig.update_layout(**PLT, title="Before vs After - Grade Count", barmode="group",
                      xaxis=dict(gridcolor="#1a1a2e", tickfont=dict(size=14)), yaxis=dict(gridcolor="#1a1a2e"))
    return fig

def fig_pie(fdf):
    dn = len(fdf[fdf["direction"] == "DOWNGRADE"])
    up = len(fdf[fdf["direction"] == "UPGRADE"])
    sm = len(fdf[fdf["direction"] == "NO CHANGE"])
    de = len(fdf[fdf["status"] == "DENIED FOR INSPECTION"])
    fig = go.Figure(go.Pie(
        labels=["Downgrade", "Upgrade", "No Change", "Denied For Inspection"],
        values=[dn, up, sm, de], hole=0.55,
        marker_colors=["#ef4444", "#22c55e", "#6b7280", "#f97316"], textfont_size=11))
    fig.update_layout(**PLT, title="Grade Direction + Denied", height=300, showlegend=True,
                      legend=dict(orientation="h", y=-0.1, font=dict(size=10)))
    return fig

def fig_grade_a(fdf):
    a = fdf[fdf["before"] == "A"]
    t = len(a)
    if t == 0:
        return go.Figure().update_layout(**PLT, title="Grade A Changes (no data)")
    aa = len(a[a["after"] == "A"])
    ab = len(a[a["after"] == "B"])
    ac2 = len(a[a["after"] == "C"])
    ad = len(a[a["after"] == "D"])
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=[f"A to A  Retained ({aa})", f"A to B  Fell ({ab})",
                f"A to C  Fell ({ac2})", f"A to D  Fell ({ad})"],
        values=[aa, ab, ac2, ad], hole=0.6,
        marker_colors=["#22c55e", "#f97316", "#ef4444", "#dc2626"],
        textinfo="percent", textfont=dict(size=11, color="#fff"),
        hovertemplate="%{label}<br>Count: %{value}<extra></extra>"))
    fig.add_annotation(text=f"<b>{t}</b><br>A Grade", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=15, color="#22c55e"))
    fig.update_layout(**PLT, title="Grade A Institutes - What Changed?", height=320,
                      showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5,
                                                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"))
    return fig

def fig_grade_d(fdf):
    d = fdf[fdf["before"] == "D"]
    t = len(d)
    if t == 0:
        return go.Figure().update_layout(**PLT, title="Grade D Changes (no data)")
    dd = len(d[d["after"] == "D"])
    dc = len(d[d["after"] == "C"])
    db = len(d[d["after"] == "B"])
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=[f"D to D  Stayed ({dd})", f"D to C  Improved ({dc})", f"D to B  Improved ({db})"],
        values=[dd, dc, db], hole=0.6,
        marker_colors=["#ef4444", "#f59e0b", "#3b82f6"],
        textinfo="percent", textfont=dict(size=11, color="#fff"),
        hovertemplate="%{label}<br>Count: %{value}<extra></extra>"))
    fig.add_annotation(text=f"<b>{t}</b><br>D Grade", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=15, color="#ef4444"))
    fig.update_layout(**PLT, title="Grade D Institutes - What Changed?", height=320,
                      showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5,
                                                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"))
    return fig

def ai_answer(q, fdf):
    q = q.lower().strip()
    total = len(fdf)
    if total == 0:
        return "No institutes found for current filter selection."
    
    dn = len(fdf[fdf["direction"] == "DOWNGRADE"])
    up = len(fdf[fdf["direction"] == "UPGRADE"])
    sm = len(fdf[fdf["direction"] == "NO CHANGE"])
    nr = len(fdf[fdf["direction"] == "NOT RANKED"])
    de = len(fdf[fdf["status"] == "DENIED FOR INSPECTION"])
    bc = fdf["before"].value_counts().to_dict()
    ac = fdf["after"].value_counts().to_dict()
    
    if any(w in q for w in ["hello", "hi", "hey"]):
        return "Hello! I am the SIRF Inspection AI Assistant. Ask me anything about the inspection results."
    
    if any(w in q for w in ["denied", "refuse", "no inspection", "not ranked"]):
        _dn = fdf[fdf["status"] == "DENIED FOR INSPECTION"]
        _br = len(fdf[(fdf["before"] == "B") & (fdf["after"] == "B")])
        _cr = len(fdf[(fdf["before"] == "C") & (fdf["after"] == "C")])
        _nm = ", ".join([r["name"][:30] for _, r in _dn.head(5).iterrows()])
        return (f"**{len(_dn)} NOT RANKED** (Grade A/D denied/no inspection).\n\n{_nm}..."
                f"\n\n**Note:** {_br} Grade-B + {_cr} Grade-C had no inspection but **keep SIRF grade** (B/C optional).")
    
    if any(w in q for w in ["total", "how many", "count"]):
        return (f"**Total {total} institutes** in current view\n\n"
                f"| Grade | Before | After |\n|---|---|---|\n"
                f"| **A** | {bc.get('A', 0)} | {ac.get('A', 0)} |\n"
                f"| **B** | {bc.get('B', 0)} | {ac.get('B', 0)} |\n"
                f"| **C** | {bc.get('C', 0)} | {ac.get('C', 0)} |\n"
                f"| **D** | {bc.get('D', 0)} | {ac.get('D', 0)} |")
    
    if any(w in q for w in ["downgrade", "fell", "worse", "drop"]):
        ab = len(fdf[fdf["path"] == "A->B"])
        ac2 = len(fdf[fdf["path"] == "A->C"])
        ad = len(fdf[fdf["path"] == "A->D"])
        pct = round(dn / total * 100) if total else 0
        return (f"**{dn} institutes downgraded** ({pct}%)\n\n"
                f"| Path | Count |\n|---|---|\n"
                f"| A to B | {ab} |\n| A to C | {ac2} |\n| A to D | {ad} |\n\n"
                f"All downgraded institutes were **Grade A** before inspection.")
    
    if any(w in q for w in ["upgrade", "improve", "better", "rise"]):
        db = len(fdf[fdf["path"] == "D->B"])
        dc2 = len(fdf[fdf["path"] == "D->C"])
        pct = round(up / total * 100) if total else 0
        return (f"**{up} institutes upgraded** ({pct}%)\n\n"
                f"| Path | Count |\n|---|---|\n"
                f"| D to B | {db} |\n| D to C | {dc2} |\n\n"
                f"All upgraded institutes were **Grade D** before inspection.")
    
    if any(w in q for w in ["stable", "no change", "unchanged"]):
        aa = len(fdf[fdf["path"] == "A->A"])
        bb = len(fdf[fdf["path"] == "B->B"])
        cc = len(fdf[fdf["path"] == "C->C"])
        dd = len(fdf[fdf["path"] == "D->D"])
        pct = round(sm / total * 100) if total else 0
        return (f"**{sm} institutes had no change** ({pct}%)\n\n"
                f"| Grade | Count |\n|---|---|\n"
                f"| A → A | {aa} |\n| B → B | {bb} |\n| C → C | {cc} |\n| D → D | {dd} |")
    
    if any(w in q for w in ["zone", "district"]):
        zc = fdf["zone"].value_counts().head(3)
        return f"**Top zones:**\n\n" + "\n".join([f"• {z}: {c}" for z, c in zc.items()])
    
    return (f"I found **{total}** institutes matching your filter.\n\n"
            f"**Summary:**\n"
            f"• Downgraded: {dn}\n"
            f"• Upgraded: {up}\n"
            f"• No Change: {sm}\n"
            f"• Not Ranked: {de}\n\n"
            f"Try asking about: downgrades, upgrades, total count, denied institutes, or specific zones!")

# ── DASH APP ──────────────────────────────────────────────────────────────────

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "SIRF Inspection Dashboard | 2079 Institutes"

app.layout = dbc.Container([
    dcc.Store(id="filter-state"),
    
    # HEADER WITH VOICE
    dbc.Card([
        dbc.CardBody(dbc.Row([
            dbc.Col([
                html.H2("SIRF INSPECTION DASHBOARD", style={"color": "#818cf8", "marginBottom": "2px", "fontSize": "1.6rem"}),
                html.P("2079 Institutes | AI Voice Assistant", style={"color": "#6b7280", "fontSize": "0.75rem", "margin": "0"})
            ], md=7),
            dbc.Col([
                dbc.Row([
                    dbc.Col(dbc.Button("🎤", id="voice-btn", color="info", size="sm", 
                             style={"borderRadius": "8px", "fontWeight": "bold"}), md=2, xs=4),
                    dbc.Col(dbc.Input(id="q-inp", placeholder="Ask anything or type your question...",
                             style={"background": "#141428", "border": "1px solid #1c1c2e", "color": "#e0e0f0",
                                    "borderRadius": "8px", "fontSize": "0.79rem"}), md=7, xs=8),
                    dbc.Col(dbc.Button("Ask", id="ask-btn", color="info", size="sm",
                             style={"borderRadius": "8px"}), md=3, xs=4),
                ], className="g-2"),
                html.Div(id="ai-out", style={"marginTop": "8px", "color": "#10b981", "fontSize": "0.73rem"})
            ], md=5)
        ], className="g-3"))
    ], style={**CARD, "marginBottom": "14px"}),
    
    # FILTERS
    dbc.Card([
        dbc.CardBody(dbc.Row([
            dbc.Col([html.Label("Zone", style={"fontSize": "0.71rem", "color": "#6b7280", "fontWeight": "600"}),
                dcc.Dropdown(id="f-zone", options=[{"label": "All Zones", "value": "ALL"}] +
                    [{"label": z, "value": z} for z in ZONES], value="ALL", clearable=False)], md=2, xs=6),
            dbc.Col([html.Label("District", style={"fontSize": "0.71rem", "color": "#6b7280", "fontWeight": "600"}),
                dcc.Dropdown(id="f-dist", options=[{"label": "All Districts", "value": "ALL"}] +
                    [{"label": d, "value": d} for d in DISTS], value="ALL", clearable=False)], md=2, xs=6),
            dbc.Col([html.Label("Type", style={"fontSize": "0.71rem", "color": "#6b7280", "fontWeight": "600"}),
                dcc.Dropdown(id="f-type", options=[{"label": "All Types", "value": "ALL"}] +
                    [{"label": t, "value": t} for t in TYPES], value="ALL", clearable=False)], md=2, xs=6),
            dbc.Col([html.Label("Status", style={"fontSize": "0.71rem", "color": "#6b7280", "fontWeight": "600"}),
                dcc.Dropdown(id="f-status", options=[
                    {"label": "All", "value": "ALL"},
                    {"label": "Denied For Inspection", "value": "DENIED FOR INSPECTION"},
                    {"label": "CHANGE", "value": "CHANGE"},
                    {"label": "NO CHANGE", "value": "NO CHANGE"}],
                    value="ALL", clearable=False)], md=2, xs=6),
            dbc.Col([html.Label("Search", style={"fontSize": "0.71rem", "color": "#6b7280", "fontWeight": "600"}),
                dbc.Input(id="srch", placeholder="Institute name...",
                    style={"background": "#141428", "border": "1px solid #1c1c2e", "color": "#e0e0f0",
                           "borderRadius": "8px", "fontSize": "0.79rem", "padding": "6px 10px"})], md=2, xs=9),
            dbc.Col([html.Label(".", style={"fontSize": "0.71rem", "color": "transparent"}),
                dbc.Button("Reset", id="reset-btn", color="secondary", className="w-100",
                    style={"borderRadius": "8px"})], md=1, xs=3),
        ]))], style={**CARD, "marginBottom": "14px"}),
    
    # KPI STRIP
    html.Div(id="kpi-strip", className="mb-3"),
    
    # BEFORE vs AFTER + PIE
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader(html.B("Before vs After - Grade Count Summary",
                style={"color": "#818cf8", "fontSize": "0.88rem"}),
                style={"background": "#0a0a18", "borderColor": "#1c1c2e"}),
            dbc.CardBody(html.Div(id="ba-table"))
        ], style=CARD), md=7, className="mb-3"),
        dbc.Col(dbc.Card(dbc.CardBody(
            dcc.Graph(id="fig-pie", config={"displayModeBar": False})),
            style=CARD), md=5, className="mb-3"),
    ]),
    
    # BAR CHART
    dbc.Row(dbc.Col(dbc.Card(dbc.CardBody(
        dcc.Graph(id="fig-bar", config={"displayModeBar": False})), style=CARD), className="mb-3")),
    
    # GRADE A and D CHANGE CHARTS
    dbc.Card([
        dbc.CardHeader(html.B("Grade A and Grade D - Institute Change Breakdown",
            style={"color": "#818cf8", "fontSize": "0.88rem"}),
            style={"background": "#0a0a18", "borderColor": "#1c1c2e"}),
        dbc.CardBody(dbc.Row([
            dbc.Col([
                html.Div([
                    html.Span("", id="grade-a-count", style={"fontSize": "1.4rem", "fontWeight": "800", "color": "#22c55e", "marginRight": "6px"}),
                    html.Span("institutes had Grade A before inspection", style={"color": "#9ca3af", "fontSize": "0.78rem"}),
                ], style={"marginBottom": "6px", "textAlign": "center"}),
                dcc.Graph(id="fig-grade-a", config={"displayModeBar": False})
            ], md=6, xs=12),
            dbc.Col([
                html.Div([
                    html.Span("", id="grade-d-count", style={"fontSize": "1.4rem", "fontWeight": "800", "color": "#ef4444", "marginRight": "6px"}),
                    html.Span("institutes had Grade D before inspection", style={"color": "#9ca3af", "fontSize": "0.78rem"}),
                ], style={"marginBottom": "6px", "textAlign": "center"}),
                dcc.Graph(id="fig-grade-d", config={"displayModeBar": False})
            ], md=6, xs=12),
        ]))
    ], style={**CARD, "marginBottom": "14px"}),
    
    # DENIED TABLE (conditional)
    html.Div(id="denied-section"),
    
    # INSTITUTE-WISE DETAIL TABLE
    dbc.Card([
        dbc.CardHeader(dbc.Row([
            dbc.Col(html.B("Institute-wise Detail", style={"color": "#818cf8", "fontSize": "0.88rem"}), md=4),
            dbc.Col(dbc.Input(id="tbl-srch", placeholder="Search institute name...",
                style={"background": "#141428", "border": "1px solid #2a2a4e", "color": "#e0e0f0",
                       "borderRadius": "8px", "fontSize": "0.8rem"}), md=8)
        ]), style={"background": "#0a0a18", "borderColor": "#1c1c2e"}),
        dbc.CardBody([
            html.Div(id="inst-count", style={"color": "#6b7280", "fontSize": "0.73rem",
                "fontFamily": "monospace", "marginBottom": "8px"}),
            html.Div(id="inst-table", style={"overflowX": "auto", "overflowY": "auto", "maxHeight": "500px"})
        ])
    ], style={**CARD, "marginBottom": "14px"}),
    
    html.P("SIRF Inspection Report | UP | 2079 Institutes | Pharmacy & Engineering | April 2026 | "
           "Python Dash + Plotly | AI Voice | Grade A/D: no insp=NOT RANKED | Grade B/C: no insp=retains SIRF grade",
        style={"textAlign": "center", "color": "#374151", "fontSize": "0.68rem", "fontFamily": "monospace", "padding": "10px"}),
    
], fluid=True, style={"background": "#08080e", "minHeight": "100vh", "padding": "14px"})

# VOICE JS
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
    r.onerror=function(e){console.log("Speech error:",e.error);}; r.start(); return "Listening...";
}
"""

app.clientside_callback(VOICE_JS, Output("ai-out", "children"), Input("voice-btn", "n_clicks"), prevent_initial_call=True)

@app.callback(
    Output("ba-table", "children"),
    Output("fig-pie", "figure"),
    Output("fig-bar", "figure"),
    Output("fig-grade-a", "figure"),
    Output("fig-grade-d", "figure"),
    Output("grade-a-count", "children"),
    Output("grade-d-count", "children"),
    Output("kpi-strip", "children"),
    Output("denied-section", "children"),
    Output("inst-count", "children"),
    Output("inst-table", "children"),
    Input("f-zone", "value"),
    Input("f-dist", "value"),
    Input("f-type", "value"),
    Input("f-status", "value"),
    Input("srch", "value"),
    Input("tbl-srch", "value"),
    Input("reset-btn", "n_clicks"),
    Input("ask-btn", "n_clicks"),
    State("q-inp", "value"),
)
def update_dashboard(fzone, fdist, ftype, fstat, srch, tbl_srch, reset_n, ask_n, q):
    ctx = callback_context
    
    if ctx.triggered and ctx.triggered[0]["prop_id"] == "reset-btn.n_clicks":
        fzone = fdist = ftype = fstat = srch = tbl_srch = q = ""
    
    f = get_filtered(fzone, fdist, ftype, fstat, srch)
    
    # KPIs
    total = len(f)
    dn = len(f[f["direction"] == "DOWNGRADE"])
    up = len(f[f["direction"] == "UPGRADE"])
    sm = len(f[f["direction"] == "NO CHANGE"])
    de = len(f[f["status"] == "DENIED FOR INSPECTION"])
    
    kpis = dbc.Row([
        dbc.Col(kpi("Total Institutes", total, "#818cf8"), md=2, xs=6, className="mb-2"),
        dbc.Col(kpi("Downgraded", dn, "#ef4444"), md=2, xs=6, className="mb-2"),
        dbc.Col(kpi("Upgraded", up, "#22c55e"), md=2, xs=6, className="mb-2"),
        dbc.Col(kpi("No Change", sm, "#6b7280"), md=2, xs=6, className="mb-2"),
        dbc.Col(kpi("Not Ranked", de, "#f97316"), md=2, xs=6, className="mb-2"),
    ], className="g-2")
    
    # Before/After Table
    bc = f["before"].value_counts().to_dict()
    ac = f["after"].value_counts().to_dict()
    ba_rows = [
        html.Tr([html.Td("Grade A", style={"fontWeight": "600"}), html.Td(bc.get("A", 0)), html.Td(ac.get("A", 0))])
        for _ in [1]
    ] + [
        html.Tr([html.Td("Grade B", style={"fontWeight": "600"}), html.Td(bc.get("B", 0)), html.Td(ac.get("B", 0))]),
        html.Tr([html.Td("Grade C", style={"fontWeight": "600"}), html.Td(bc.get("C", 0)), html.Td(ac.get("C", 0))]),
        html.Tr([html.Td("Grade D", style={"fontWeight": "600"}), html.Td(bc.get("D", 0)), html.Td(ac.get("D", 0))]),
    ]
    ba = html.Table(
        [html.Thead(html.Tr([html.Th("Grade"), html.Th("Before (SIRF)", style={"textAlign": "center"}),
                             html.Th("After (Inspection)", style={"textAlign": "center"})],
                            style={"borderBottom": "1px solid #1c1c2e"}))] +
        [html.Tbody(ba_rows, style={"fontSize": "0.85rem", "color": "#c0c0d0"})],
        style={"width": "100%", "borderCollapse": "collapse"})
    
    # Grade A/D counts
    gac = len(f[f["before"] == "A"])
    gdc = len(f[f["before"] == "D"])
    
    # Denied section
    denied_f = f[f["status"] == "DENIED FOR INSPECTION"]
    if len(denied_f) > 0:
        denied_rows = [
            html.Tr([
                html.Td(r["name"][:40], style={"color": "#818cf8"}),
                html.Td(r["zone"], style={"fontSize": "0.8rem", "color": "#9ca3af"}),
                html.Td(r["district"], style={"fontSize": "0.8rem", "color": "#9ca3af"}),
            ]) for _, r in denied_f.head(20).iterrows()
        ]
        denied_tbl = html.Table(
            [html.Thead(html.Tr([html.Th("Institute"), html.Th("Zone"), html.Th("District")],
                                style={"borderBottom": "1px solid #1c1c2e", "fontSize": "0.75rem"}))]+
            [html.Tbody(denied_rows, style={"fontSize": "0.8rem"})],
            style={"width": "100%", "borderCollapse": "collapse"})
        denied_sec = dbc.Card([
            dbc.CardHeader(html.B(f"Not Ranked / Denied ({len(denied_f)})",
                style={"color": "#f97316", "fontSize": "0.88rem"}),
                style={"background": "#0a0a18", "borderColor": "#1c1c2e"}),
            dbc.CardBody(denied_tbl)
        ], style={**CARD, "marginBottom": "14px"})
    else:
        denied_sec = html.Div()
    
    # Institute detail table
    if tbl_srch:
        t_f = f[f["name"].str.contains(tbl_srch, case=False, na=False)]
    else:
        t_f = f
    
    if len(t_f) > 0:
        inst_rows = [
            html.Tr([
                html.Td(r["name"][:35], style={"color": "#818cf8", "fontSize": "0.8rem"}),
                html.Td(r["zone"], style={"fontSize": "0.75rem", "color": "#9ca3af"}),
                html.Td(r["district"], style={"fontSize": "0.75rem", "color": "#9ca3af"}),
                html.Td(r["before"], style={"textAlign": "center", "color": GC.get(r["before"], "#ccc")}),
                html.Td(r["after"], style={"textAlign": "center", "color": GC.get(r["after"], "#ccc")}),
                html.Td(r["direction"][:3], style={"fontSize": "0.75rem", "color": "#9ca3af", "textAlign": "center"}),
            ]) for _, r in t_f.head(100).iterrows()
        ]
        inst_tbl = html.Table(
            [html.Thead(html.Tr([html.Th("Institute"), html.Th("Zone"), html.Th("Dist"), html.Th("Before"),
                                 html.Th("After"), html.Th("Dir")],
                                style={"borderBottom": "1px solid #1c1c2e", "fontSize": "0.75rem",
                                       "color": "#818cf8", "textAlign": "left"}))]+
            [html.Tbody(inst_rows, style={"fontSize": "0.78rem"})],
            style={"width": "100%", "borderCollapse": "collapse"})
        inst_cnt = html.Span(f"Showing {len(t_f)} of {len(f)} institutes",
                             style={"color": "#6b7280", "fontSize": "0.73rem"})
    else:
        inst_tbl = html.Div("No institutes found", style={"color": "#6b7280", "textAlign": "center", "padding": "20px"})
        inst_cnt = html.Span("")
    
    # AI answer
    if ctx.triggered and ctx.triggered[0]["prop_id"] == "ask-btn.n_clicks" and q:
        ai_ans = ai_answer(q, f)
        ai_out = dcc.Markdown(ai_ans, style={"color": "#10b981", "fontSize": "0.75rem", "lineHeight": "1.5"})
    else:
        ai_out = html.Div()
    
    return (ba, fig_pie(f), fig_bar(bc, ac), fig_grade_a(f), fig_grade_d(f), str(gac), str(gdc),
            kpis, denied_sec, inst_cnt, inst_tbl)

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  SIRF DASHBOARD - 2079 INSTITUTES")
    print(f"  Local  : http://127.0.0.1:{PORT}")
    print(f"  Mobile : {MOBILE_URL}")
    print("  Scan QR on dashboard to open on phone!")
    print("  Use Google Chrome for Voice feature")
    print("=" * 60)
    print()
    app.run(debug=False, host="0.0.0.0", port=PORT)
