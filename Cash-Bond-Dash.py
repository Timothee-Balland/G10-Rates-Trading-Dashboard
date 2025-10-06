# Cash-Bond-Dash.py
from __future__ import annotations
from dash import Dash, html, dcc, dash_table, no_update
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
from datetime import datetime

from modules.data_loader import fetch_yields, DEFAULT_G10
from modules.swap_loader import load_swaps
from modules.calculations import add_spread_vs_ref, add_spread_vs_ref_par
from modules.plots import (
    plot_yield_curve, plot_spread, plot_curve, plot_matrix_heatmap, plot_ZC_swap
)
from modules.analytics import g10_matrix_spreads_vs_ref, carry_roll_table, two_leg_spreads, fly_2_5_10
from modules.hedging import hedge_proposal
import plotly.io as pio
import traceback

# --- Template unique + default APRÈS ---
if "bbg" not in pio.templates:
    pio.templates["bbg"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="#090b0e",
            plot_bgcolor="#0c0f14",
            font=dict(family="Inter, system-ui, -apple-system, Segoe UI, Roboto",
                      color="#e8eaef", size=13),
            margin=dict(l=40, r=20, t=50, b=30),
            colorway=["#ff9f0a","#2bd67d","#58a6ff","#b48cf2","#f25f5c","#f2cc8f","#7f8c8d"],
            xaxis=dict(
                gridcolor="#1a2029", zerolinecolor="#1a2029",
                linecolor="#2b3645", tickcolor="#2b3645",
                tickfont=dict(color="#cfd6e4"),
                title=dict(font=dict(color="#e8eaef"))
            ),
            yaxis=dict(
                gridcolor="#1a2029", zerolinecolor="#1a2029",
                linecolor="#2b3645", tickcolor="#2b3645",
                tickfont=dict(color="#cfd6e4"),
                title=dict(font=dict(color="#e8eaef"))
            ),
            legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#2b3645", borderwidth=0,
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(bgcolor="#101521", bordercolor="#2b3645", font=dict(color="#e8eaef")),
            bargap=0.18
        )
    )

pio.templates.default = "bbg"

# -------- Config --------
G10 = DEFAULT_G10
DEFAULT_COUNTRY = "France"
REFRESH_MS = 90 * 1000
REF_COUNTRY_FOR_SPREAD = "Germany"  # Bund

COUNTRY_TO_CCY = {
    "United States": "USD",
    "Canada": "CAD",
    "United Kingdom": "GBP",
    "Germany": "EUR",
    "France": "EUR",
    "Italy": "EUR",
    "Japan": "JPY",
    "Australia": "AUD",
    "New Zealand": "NZD",
    "Sweden": "SEK",
}

SWAP_FREQ_BY_CCY = {
    "EUR": 1,
    "USD": 2,
    "GBP": 2,
    "AUD": 2,
    "CAD": 2,
    "JPY": 2,
    "NZD": 2,
    "SEK": 1,
}

# -------- Plotly template: "bbg" (Bloomberg-like noir + orange) --------
pio.templates["bbg"] = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="#090b0e",   # fond global très sombre
        plot_bgcolor="#0c0f14",    # fond du graphe (ardoise/noir)
        font=dict(
            family="Inter, system-ui, -apple-system, Segoe UI, Roboto",
            color="#e8eaef", size=13
        ),
        margin=dict(l=40, r=20, t=50, b=30),
        colorway=[
            "#ff9f0a",  # orange principal
            "#2bd67d",  # vert
            "#58a6ff",  # bleu
            "#b48cf2",  # violet
            "#f25f5c",  # rouge
            "#f2cc8f",  # sable
            "#7f8c8d",  # gris
        ],

        # IMPORTANT: utiliser title={font={...}} et non titlefont
        xaxis=dict(
            gridcolor="#1a2029",
            zerolinecolor="#1a2029",
            linecolor="#2b3645",
            tickcolor="#2b3645",
            tickfont=dict(color="#cfd6e4"),
            title=dict(font=dict(color="#e8eaef"))
        ),
        yaxis=dict(
            gridcolor="#1a2029",
            zerolinecolor="#1a2029",
            linecolor="#2b3645",
            tickcolor="#2b3645",
            tickfont=dict(color="#cfd6e4"),
            title=dict(font=dict(color="#e8eaef"))
        ),

        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#2b3645",
            borderwidth=0,
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        hoverlabel=dict(
            bgcolor="#101521",
            bordercolor="#2b3645",
            font=dict(color="#e8eaef")
        ),
        bargap=0.18
    )
)

# --------- App ---------
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "G10 Rates Trading Dashboard"

app.layout = html.Div(  # root container themed by CSS class
    id="app-root",
    className="theme-bbg",  # bascule via callback
    children=[
        html.Div(
            style={"maxWidth": "1300px", "margin": "0 auto", "fontFamily": "Inter, system-ui, -apple-system"},
            children=[
                html.H1("G10 Rates Trading Dashboard", style={"textAlign": "center", "marginTop": "12px"}),

                # Controls row (wrap in a themed card)
                html.Div(
                    className="panel-card toolbar",
                    children=[
                        html.Div("Instrument :"),
                        dcc.RadioItems(
                            id="instrument",
                            options=[{"label":"Bonds","value":"bonds"},{"label":"Swaps","value":"swaps"}],
                            value="bonds", inline=True
                        ),
                        html.Div("Spread :"),
                        dcc.Dropdown(
                            id="spread-mode",
                            options=[
                                {"label":"Gov vs Bund","value":"gov_bund"},
                                {"label":"ASW (Gov - IRS)","value":"asw"},
                                {"label":"IRS vs EUR IRS","value":"irs_vs_eur"},
                            ],
                            value="gov_bund", clearable=False, style={"width":"220px"}
                        ),
                        html.Div("Courbe :"),
                        dcc.RadioItems(
                            id="curve-type",
                            options=[{"label":"Par","value":"par"},{"label":"Zéro","value":"zero"}],
                            value="par", inline=True
                        ),
                        html.Div("Pays (G10) :"),
                        dcc.Dropdown(
                            id="country-dd",
                            options=[{"label": c, "value": c} for c in G10],
                            value=DEFAULT_COUNTRY, clearable=False, style={"width": "260px"}
                        ),
                        html.Div("Thème :"),
                        dcc.Dropdown(
                            id="theme-dd",
                            options=[
                                {"label":"Bloomberg (noir/orange)","value":"bbg"},
                                {"label":"Clair","value":"plotly_white"},
                            ],
                            value="bbg",  # <- par défaut
                            clearable=False, style={"width":"240px"}
                        ),
                        dcc.Interval(id="interval", interval=REFRESH_MS, n_intervals=0),
                        html.Div(id="status-banner", style={"fontSize":"12px","opacity":0.8})
                    ],
                    style={"display": "flex", "gap": "16px", "alignItems": "center", "justifyContent": "center", "flexWrap": "wrap", "margin":"10px 0"}
                ),

                dcc.Tabs(
                    id="tabs", value="tab-overview",
                    className="app-tabs",
                    children=[
                        dcc.Tab(label="Overview",     value="tab-overview", className="app-tab", selected_className="app-tab--selected"),
                        dcc.Tab(label="Spreads & Flies", value="tab-spreads", className="app-tab", selected_className="app-tab--selected"),
                        dcc.Tab(label="Carry & Roll", value="tab-carry",    className="app-tab", selected_className="app-tab--selected"),
                        dcc.Tab(label="G10 Matrix",   value="tab-matrix",   className="app-tab", selected_className="app-tab--selected"),
                        dcc.Tab(label="Hedging",      value="tab-hedge",    className="app-tab", selected_className="app-tab--selected"),
                    ]
                ),

                html.Div(id="tab-content", style={"marginTop":"12px"}),
            ]
        )
    ]
)

# --------- Builders for each tab ---------
def layout_overview():
    return html.Div([
        html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"16px"}, children=[
            html.Div(className="graph-card", children=[dcc.Graph(id="yield-curve", style={"height":"420px"})]),
            html.Div(className="graph-card", children=[dcc.Graph(id="spread-bar",  style={"height":"420px"})]),
        ]),
        html.Hr(),
        html.H3("Tableau des taux — pays sélectionné", style={"marginBottom":"6px"}),
        dash_table.DataTable(
            id="yields-table", page_size=12, sort_action="native", filter_action="native",
            style_table={"overflowX":"auto", "backgroundColor":"var(--card-bg)", "border":"1px solid var(--border)"},
            style_cell={"padding":"8px","fontSize":"14px","backgroundColor":"var(--card-bg)","color":"var(--text)","border":"none"},
            style_header={"fontWeight":"700","backgroundColor":"var(--card-header-bg)","color":"var(--text)","borderBottom":"1px solid var(--border)"},
        )
    ])

def layout_spreads():
    return html.Div([
        html.Div(style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"16px"}, children=[
            html.Div(className="graph-card", children=[dcc.Graph(id="twolegs-line", style={"height":"380px"})]),
            html.Div(className="graph-card", children=[dcc.Graph(id="fly-bar",      style={"height":"380px"})]),
        ]),
        html.Div(id="spreads-values", style={"marginTop":"8px","display":"flex","gap":"18px","fontSize":"14px"})
    ])

def layout_carry():
    return html.Div([
        html.Div("Carry & Roll approximations (bp). Tri sur 1M pour idées rapides.", style={"opacity":0.9}),
        dash_table.DataTable(
            id="carry-table", page_size=20, sort_action="native", filter_action="native",
            style_table={"overflowX":"auto", "backgroundColor":"var(--card-bg)", "border":"1px solid var(--border)"},
            style_cell={"padding":"8px","fontSize":"14px","backgroundColor":"var(--card-bg)","color":"var(--text)","border":"none"},
            style_header={"fontWeight":"700","backgroundColor":"var(--card-header-bg)","color":"var(--text)","borderBottom":"1px solid var(--border)"},
        )
    ])

def layout_matrix():
    return html.Div([
        html.Div(className="graph-card", children=[dcc.Graph(id="g10-heatmap", style={"height":"520px"})]),
        html.Hr(),
        dash_table.DataTable(
            id="g10-table", page_size=20, sort_action="native", filter_action="native",
            style_table={"overflowX":"auto", "backgroundColor":"var(--card-bg)", "border":"1px solid var(--border)"},
            style_cell={"padding":"8px","fontSize":"14px","backgroundColor":"var(--card-bg)","color":"var(--text)","border":"none"},
            style_header={"fontWeight":"700","backgroundColor":"var(--card-header-bg)","color":"var(--text)","borderBottom":"1px solid var(--border)"},
        )
    ])

def layout_hedge():
    return html.Div([
        html.Div(style={"display":"grid","gridTemplateColumns":"1.1fr 0.9fr","gap":"16px"}, children=[
            # Left panel: inputs
            html.Div(className="panel-card", children=[
                html.H3("Bond inputs", style={"marginTop":"0"}),
                html.Div(style={"display":"grid","gridTemplateColumns":"repeat(2, minmax(160px, 1fr))","gap":"10px"}, children=[
                    html.Div([html.Label("Nominal"), dcc.Input(id="hedge-face", type="number", value=100.0, step=1, style={"width":"100%"})]),
                    html.Div([html.Label("Coupon (%)"), dcc.Input(id="hedge-coupon", type="number", value=3.0, step=0.01, style={"width":"100%"})]),
                    html.Div([html.Label("YTM (%)"), dcc.Input(id="hedge-ytm", type="number", value=3.2, step=0.01, style={"width":"100%"})]),
                    html.Div([html.Label("Maturity (years)"), dcc.Input(id="hedge-years", type="number", value=10.0, step=0.25, style={"width":"100%"})]),
                    html.Div([html.Label("Futures symbol (opt.)"), dcc.Dropdown(
                        id="hedge-fut",
                        options=[{"label":s,"value":s} for s in ["FGBS","FGBM","FGBL","ZN","ZB"]],
                        value="FGBL", clearable=True
                    )]),
                ]),
                html.Div(style={"marginTop":"8px","opacity":0.85}, children=[
                    html.Small("Hedge proposé contre le risque taux, sizing DV01 via futures / IRS (asset swap).")
                ])
            ]),
            # Right panel: outputs
            html.Div(style={"display":"grid","gridTemplateRows":"min-content 1fr","gap":"12px"}, children=[
                html.Div(className="graph-card", children=[dcc.Graph(id="hedge-dv01-fig", style={"height":"360px"})]),
                dash_table.DataTable(
                    id="hedge-table", page_size=10,
                    style_table={"overflowX":"auto", "backgroundColor":"var(--card-bg)", "border":"1px solid var(--border)"},
                    style_cell={"padding":"8px","fontSize":"14px","backgroundColor":"var(--card-bg)","color":"var(--text)","border":"none"},
                    style_header={"fontWeight":"700","backgroundColor":"var(--card-header-bg)","color":"var(--text)","borderBottom":"1px solid var(--border)"},
                ),
            ])
        ])
    ])


@app.callback(Output("tab-content", "children"), Input("tabs","value"))
def render_tab(tab):
    if tab == "tab-overview": return layout_overview()
    if tab == "tab-spreads":  return layout_spreads()
    if tab == "tab-carry":    return layout_carry()
    if tab == "tab-matrix":   return layout_matrix()
    if tab == "tab-hedge":    return layout_hedge()
    return html.Div()

# --------- Theming: apply class to root ---------
@app.callback(Output("app-root","className"), Input("theme-dd","value"))
def apply_theme_class(theme):
    return "theme-bbg" if theme == "bbg" else "theme-light"

# --------- Data fetch + banner ----------
def fmt_time(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S")

@app.callback(
    Output("status-banner","children"),
    Input("interval","n_intervals")
)
def update_banner(_):
    now = datetime.now()
    return f"Last update: {fmt_time(now)} | Refresh every {REFRESH_MS//1000}s"

# --------- Overview tab callback ----------
@app.callback(
    Output("yield-curve", "figure"),
    Output("spread-bar", "figure"),
    Output("yields-table", "data"),
    Output("yields-table", "columns"),
    Input("country-dd","value"),
    Input("curve-type","value"),
    Input("instrument","value"),
    Input("spread-mode","value"),
    Input("interval","n_intervals"),
    Input("theme-dd","value"),
)
def update_overview(country, curve_type, instrument, spread_mode, _, theme):
    try:
        if instrument == "bonds":
            df_all = fetch_yields(G10)
            dfx = df_all[df_all["country"].str.lower() == country.lower()].copy()

            # Courbe
            try:
                fig_curve = plot_yield_curve(dfx, curve_type=curve_type, freq=2, comp="cont", theme=theme)
                if not fig_curve.data:
                    fig_curve = plot_yield_curve(dfx, curve_type="par", freq=2, comp="cont", theme=theme)
            except Exception:
                traceback.print_exc()
                fig_curve = plot_yield_curve(dfx, curve_type="par", freq=2, comp="cont", theme=theme)

            # Spread selon spread_mode
            if spread_mode == "asw":
                ccy = COUNTRY_TO_CCY.get(country, "EUR")
                df_sw = load_swaps(ccy)
                from modules.calculations import asw_spread
                m = asw_spread(dfx, df_sw, country_label=country)
                fig_spread = plot_spread(m, ref_country=f"{ccy} Swaps", theme=theme)
            else:  # gov_bund par défaut
                df_spread = add_spread_vs_ref(df_all, target_country=country, ref_country=REF_COUNTRY_FOR_SPREAD)
                fig_spread = plot_spread(df_spread, ref_country=REF_COUNTRY_FOR_SPREAD, theme=theme)

            # Table
            desired = ["tenor","years","yield","prev.","high","low","chg.","chg. %","time"]
            cols = [c for c in desired if c in dfx.columns]
            table_df = dfx[cols].sort_values("years") if cols else dfx.head(0)
            return (fig_curve, fig_spread, table_df.to_dict("records"), [{"name":c,"id":c} for c in cols])

        else:
            ccy = COUNTRY_TO_CCY.get(country, "EUR")
            df_sw = load_swaps(ccy)

            # Courbe swaps
            if curve_type == "zero":
                fig_curve = plot_ZC_swap(df_sw, currency=ccy, comp="cont", theme=theme)
            else:
                fig_curve = plot_curve(df_sw, curve_type="par", label=f"{ccy} Swaps",
                                    freq=1, comp="cont", is_swap=True, theme=theme)

            # Spread selon spread_mode
            if spread_mode == "asw":
                # ASW utilise les Govs du pays
                df_all = fetch_yields(G10)
                dfx = df_all[df_all["country"].str.lower() == country.lower()].copy()
                from modules.calculations import asw_spread
                m = asw_spread(dfx, df_sw, country_label=country)
                fig_spread = plot_spread(m, ref_country=f"{ccy} Swaps", theme=theme)
            else:  # "irs_vs_eur"
                df_eur = load_swaps("EUR")
                from modules.calculations import swap_spread_vs_ref
                m = swap_spread_vs_ref(df_target_swaps=df_sw, df_ref_swaps=df_eur, country_label=country)
                fig_spread = plot_spread(m, ref_country="EUR Swaps", theme=theme)

            return fig_curve, fig_spread, no_update, no_update


    except Exception as e:
        print("update_overview error:", e)
        empty = go.Figure(); empty.update_layout(template=theme)
        return empty, empty, no_update, no_update

# --------- Spreads & Flies tab ----------
@app.callback(
    Output("twolegs-line","figure"),
    Output("fly-bar","figure"),
    Output("spreads-values","children"),
    Input("country-dd","value"),
    Input("interval","n_intervals"),
    Input("theme-dd","value"),
)
def update_spreads_tab(country, _, theme):
    try:
        df_all = fetch_yields(G10)
        dfx = df_all[df_all["country"].str.lower()==country.lower()].copy().sort_values("years")

        pairs = []
        def add_pair(a,b,name):
            A = dfx[dfx["tenor"]==a]["yield"]
            B = dfx[dfx["tenor"]==b]["yield"]
            if not A.empty and not B.empty:
                pairs.append((name,(A.iloc[0]-B.iloc[0])*100))
        add_pair("2Y","10Y","2s10s"); add_pair("5Y","30Y","5s30s"); add_pair("2Y","5Y","2s5s")

        fig_line = go.Figure()
        if pairs:
            fig_line.add_trace(go.Bar(x=[n for n,_ in pairs], y=[v for _,v in pairs], name="Spreads (bp)"))
        fig_line.update_layout(title=f"Two-leg spreads — {country}", margin=dict(l=20,r=20,t=40,b=20), yaxis_title="bp", template=theme)

        fly = fly_2_5_10(dfx)
        fig_fly = go.Figure()
        fig_fly.add_trace(go.Bar(x=["Fly 2/5/10"], y=[fly if fly is not None else 0]))
        fig_fly.update_layout(title=f"Butterfly 2s/5s/10s — {country}", margin=dict(l=20,r=20,t=40,b=20), yaxis_title="bp", template=theme)

        vals = two_leg_spreads(dfx)
        badges = []
        for k in ["2s10s_bp","5s30s_bp","2s5s_bp"]:
            v = vals.get(k)
            txt = f"{k}: {v:+.1f} bp" if v is not None else f"{k}: n/a"
            badges.append(html.Div(txt))
        bf = f"Fly(2/5/10): {fly:+.1f} bp" if fly is not None else "Fly(2/5/10): n/a"
        badges.append(html.Div(bf))
        return fig_line, fig_fly, badges
    except Exception as e:
        print("update_spreads_tab error:", e)
        empty = go.Figure(); empty.update_layout(template=theme)
        return empty, empty, [html.Div("n/a")]

# --------- Carry & Roll tab ----------
@app.callback(
    Output("carry-table","data"),
    Output("carry-table","columns"),
    Input("country-dd","value"),
    Input("interval","n_intervals"),
)
def update_carry_tab(country, _):
    try:
        df_all = fetch_yields(G10)
        dfx = df_all[df_all["country"].str.lower()==country.lower()].copy()
        t = carry_roll_table(dfx)
        cols = ["tenor","years","yield","slope_bp_per_y","roll_1m_bp","carry_1m_bp","roll_3m_bp","carry_3m_bp"]
        present = [c for c in cols if c in t.columns]
        t = t[present].sort_values("carry_1m_bp", ascending=False, na_position="last")
        return t.to_dict("records"), [{"name":c,"id":c} for c in present]
    except Exception as e:
        print("update_carry_tab error:", e)
        return [], []

# --------- Matrix tab ----------
@app.callback(
    Output("g10-heatmap","figure"),
    Output("g10-table","data"),
    Output("g10-table","columns"),
    Input("interval","n_intervals"),
    Input("theme-dd","value"),
)
def update_matrix(_, theme):
    try:
        df_all = fetch_yields(G10)
        wide = g10_matrix_spreads_vs_ref(df_all, tenors=("2Y","5Y","10Y","30Y"), ref_country=REF_COUNTRY_FOR_SPREAD)
        fig = plot_matrix_heatmap(wide, title=f"G10 Spreads vs {REF_COUNTRY_FOR_SPREAD} (bp)", theme=theme)
        return fig, wide.to_dict("records"), [{"name":c,"id":c} for c in wide.columns]
    except Exception as e:
        print("update_matrix error:", e)
        empty = go.Figure(); empty.update_layout(template=theme)
        return empty, [], []

# --------- Hedging tab ----------
@app.callback(
    Output("hedge-dv01-fig","figure"),
    Output("hedge-table","data"),
    Output("hedge-table","columns"),
    Input("country-dd","value"),
    Input("hedge-face","value"),
    Input("hedge-coupon","value"),
    Input("hedge-ytm","value"),
    Input("hedge-years","value"),
    Input("hedge-fut","value"),
    Input("theme-dd","value"),
)
def update_hedge(country, face, coupon, ytm, years, fut_symbol, theme):
    tpl = None if theme == "bbg" else "plotly_white"
    try:
        # Swaps pour la devise du pays
        ccy = COUNTRY_TO_CCY.get(country, "EUR")
        df_sw = load_swaps(ccy)
        freq = SWAP_FREQ_BY_CCY.get(ccy, 2)

        res = hedge_proposal(
            bond_country=country,
            face=face or 100.0,
            coupon_pct=coupon or 0.0,
            ytm_pct=ytm or 0.0,
            T_years=years or 1.0,
            df_swaps_ccy=df_sw,
            futures_symbol=fut_symbol,
            swap_freq_by_ccy=freq,
        )

        # Figure DV01
        fig = go.Figure()
        fig.add_bar(name="Bond DV01", x=["Bond"], y=[res.get("dv01_bond", 0)])
        # Futures
        fut = res.get("futures")
        if isinstance(fut, dict) and "contracts" in fut and "dv01_per_contract" in fut:
            fig.add_bar(name=f"Futures × {fut['contracts']}", x=["Hedge"], y=[fut["contracts"] * fut["dv01_per_contract"]])
        # IRS
        irs = res.get("irs")
        if isinstance(irs, dict) and "dv01_per_100" in irs and "receiver_fix_notional" in irs:
            # convertir notional en multiples de 100
            notional_units = (irs["receiver_fix_notional"] or 0) / 100.0
            fig.add_bar(name=f"IRS ({irs.get('tenor_years','?')}y)", x=["Hedge"], y=[notional_units * irs["dv01_per_100"]])

        fig.update_layout(barmode="group", title="DV01 comparison (bond vs hedges)", yaxis_title="DV01 (per 1bp, price units)",
                          margin=dict(l=20,r=20,t=40,b=20), template=theme)

        # Table récap
        rows = [
            {"Metric":"Bond DV01 (per 1bp)","Value":f"{res.get('dv01_bond', float('nan')):.2f}"},
            {"Metric":"Liquidity score (0..1)","Value":res.get("liquidity_score","n/a")},
        ]
        if fut:
            if "contracts" in fut:
                rows.append({"Metric":"Futures","Value":f"{fut['symbol']} | DV01/ctrt {fut['dv01_per_contract']:.1f} | N≈{fut['contracts']}"})
            else:
                rows.append({"Metric":"Futures","Value":f"{fut.get('symbol','?')} | {fut.get('note','n/a')}"})
        if irs:
            if "tenor_years" in irs:
                rows.append({"Metric":"IRS (asset swap)","Value":f"T≈{irs['tenor_years']}y | DV01/100 {irs['dv01_per_100']:.2f} | Notional recv-fix≈{irs['receiver_fix_notional']:.0f}"})
            else:
                rows.append({"Metric":"IRS (asset swap)","Value":irs.get("note","n/a")})

        cols = [{"name":"Metric","id":"Metric"}, {"name":"Value","id":"Value"}]
        return fig, rows, cols

    except Exception as e:
        print("update_hedge error:", e)
        empty = go.Figure(); empty.update_layout(template=theme)
        return empty, [], [{"name":"Metric","id":"Metric"},{"name":"Value","id":"Value"}]
    
@app.callback(
    Output("spread-mode","options"),
    Output("spread-mode","value"),
    Input("instrument","value"),
    State("spread-mode","value"),
    prevent_initial_call=False
)
def sync_spread_options(instrument, current):
    if instrument == "bonds":
        opts = [
            {"label":"Gov vs Bund","value":"gov_bund"},
            {"label":"ASW (Gov - IRS)","value":"asw"},
        ]
        default = "gov_bund" if current not in ("gov_bund","asw") else current
        return opts, default
    else:  # swaps
        opts = [
            {"label":"IRS vs EUR IRS","value":"irs_vs_eur"},
            {"label":"ASW (Gov - IRS)","value":"asw"},  # utile pour cross-check
        ]
        default = "irs_vs_eur" if current not in ("irs_vs_eur","asw") else current
        return opts, default


@app.callback(
    Output("curve-type","value"),
    Input("instrument","value"),
    State("curve-type","value"),
    prevent_initial_call=True
)
def reset_curve_when_bonds(instrument, current):
    return "par" if instrument == "bonds" else current

if __name__ == "__main__":
    app.run(debug=True)
