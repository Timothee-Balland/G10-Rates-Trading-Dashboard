# modules/plots.py
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from .analytics import ensure_years
from .calculations import (
    bootstrap_zero_from_par,
    bootstrap_zero_from_par_swaps,
)

# --- Config
TENOR_ORDER = ["1Y","2Y","3Y","4Y","5Y","7Y","10Y","15Y","20Y","30Y","40Y","50Y"]

def _sort_tenors_like(series):
    known = [t for t in TENOR_ORDER if t in set(series)]
    unknown = sorted([t for t in series if t not in TENOR_ORDER],
                     key=lambda x: (len(str(x)), str(x)))
    return known + unknown

SWAP_FREQ_BY_CCY = {
    "EUR": 1,  # EUR fixed leg souvent annuel
    "USD": 2,  # semi-annuel
    "GBP": 2,
    "AUD": 2,
    "CAD": 2,
    "JPY": 2,
    "NZD": 2,
    "SEK": 1,  # parfois 1
}

def _swap_freq_for(currency: str) -> int:
    return SWAP_FREQ_BY_CCY.get((currency or "").upper(), 2)

# ---- Yield curve (bonds) ----
def plot_yield_curve(df: pd.DataFrame, curve_type: str = "par", freq: int = 2, comp: str = "cont", theme: str = "bbg"):
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(title="Yield Curve — (aucune donnée)", template=theme)
        return fig

    d = ensure_years(df).dropna(subset=["years"]).sort_values("years").copy()
    # En cas de multi-pays (défensif), ne garder que le premier
    if "country" in d.columns and d["country"].nunique() > 1:
        main_cty = d["country"].iloc[0]
        d = d[d["country"] == main_cty]
    country = d["country"].iloc[0] if "country" in d.columns and not d.empty else "—"

    fig = go.Figure()
    if curve_type == "zero":
        z = bootstrap_zero_from_par(d, freq=freq, comp=comp)
        if not z.empty:
            z = z.sort_values("years")
            fig.add_trace(go.Scatter(
                x=z["years"], y=z["zero_yield"], mode="lines+markers",
                name="Zero-coupon (bootstrapped)",
                hovertemplate="t=%{x:.2f}y<br>z=%{y:.3f}%<extra></extra>"
            ))
        else:
            fig.update_layout(title=f"Yield Curve — {country} (Zero) — (aucune donnée)", template=theme)
            return fig
    else:
        ycol = "yield"
        if ycol not in d.columns or d[ycol].isna().all():
            fig.update_layout(title=f"Yield Curve — {country} (pas de '{ycol}')", template=theme)
            return fig
        fig.add_trace(go.Scatter(
            x=d["years"], y=d[ycol], mode="lines+markers", name="Par Yield",
            hovertemplate="t=%{x:.2f}y<br>y=%{y:.3f}%<extra></extra>"
        ))

    fig.update_layout(
        title=f"Yield Curve — {country}  ({'Zero' if curve_type=='zero' else 'Par'})",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template=theme
    )
    fig.update_xaxes(title="Maturity (years)")
    fig.update_yaxes(title="Yield (%)", tickformat=".2f")  # <- ajout
    return fig

# ---- Spreads vs ref (bp) ----
def plot_spread(df_spread: pd.DataFrame, ref_country: str = "Germany", theme: str = "bbg"):
    fig = go.Figure()
    if df_spread is None or df_spread.empty:
        fig.update_layout(title=f"Spreads vs {ref_country} — (aucune donnée)", template=theme)
        return fig

    # On évite de toucher aux colonnes (notamment spread_bp). ensure_years seulement si 'years' absent.
    d = df_spread.copy()
    if "years" not in d.columns:
        d = ensure_years(d)

    # Un seul pays pour le titre
    if "country" in d.columns and d["country"].nunique() > 1:
        d = d[d["country"] == d["country"].iloc[0]]

    # spread_bp: numérique et non-NaN
    if "spread_bp" not in d.columns:
        fig.update_layout(title=f"Spreads vs {ref_country} — (pas de 'spread_bp')", template=theme)
        return fig
    d["spread_bp"] = pd.to_numeric(d["spread_bp"], errors="coerce")
    d = d.dropna(subset=["spread_bp"])
    if d.empty:
        fig.update_layout(title=f"Spreads vs {ref_country} — (spreads vides)", template=theme)
        return fig

    # Ordonner les tenors si on va les utiliser
    use_tenor = ("tenor" in d.columns) and d["tenor"].notna().sum() >= max(1, int(0.6 * len(d)))
    if use_tenor:
        order = _sort_tenors_like(list(d["tenor"].dropna().unique()))
        d["tenor"] = pd.Categorical(d["tenor"], categories=order, ordered=True)
        x_vals = d["tenor"]
        # tri stable : par years puis tenor si dispo
        if "years" in d.columns:
            d = d.sort_values(["years","tenor"])
        else:
            d = d.sort_values("tenor")
    else:
        # fallback robuste sur years
        if "years" not in d.columns:
            fig.update_layout(title=f"Spreads vs {ref_country} — (pas de 'years' ni de 'tenor' exploitable)", template=theme)
            return fig
        d = d.dropna(subset=["years"]).sort_values("years")
        x_vals = d["years"]

    target = d["country"].iloc[0] if "country" in d.columns else "—"

    fig.add_bar(x=x_vals, y=d["spread_bp"], name="Spread (bp)")
    fig.update_layout(
        title=f"Spreads vs {ref_country} — {target}",
        margin=dict(l=20, r=20, t=40, b=20),
        template=theme
    )
    fig.update_yaxes(title="Spread (bp)", zeroline=True, zerolinewidth=1, tickformat=".0f")
    fig.update_xaxes(title="Maturity")
    return fig


# ---- Generic bonds/swaps plot ----
def plot_curve(df_par: pd.DataFrame, curve_type: str, label: str, freq: int = 2, comp: str = "cont", is_swap: bool = False, theme: str = "bbg"):
    fig = go.Figure()
    if df_par is None or df_par.empty:
        fig.update_layout(title=f"{label} — (aucune donnée)", template=theme)
        return fig

    d = df_par.dropna(subset=["years"]).sort_values("years").copy()
    if curve_type == "par":
        ycol = "rate" if is_swap else "yield"
        if ycol not in d.columns or d[ycol].isna().all():
            fig.update_layout(title=f"{label} — Par (pas de {ycol})", template=theme)
            return fig
        fig.add_trace(go.Scatter(
            x=d["years"], y=d[ycol], mode="lines+markers", name=f"{label} — Par",
            hovertemplate="t=%{x:.2f}y<br>{val:.3f}%<extra></extra>".replace("{val}", "r" if is_swap else "y")
        ))
    else:
        z = bootstrap_zero_from_par_swaps(d, freq=freq, comp=comp) if is_swap else bootstrap_zero_from_par(d, freq=freq, comp=comp)
        if z is None or z.empty:
            fig.update_layout(title=f"{label} — Zero (aucune donnée)", template=theme)
            return fig
        z = z.sort_values("years")
        fig.add_trace(go.Scatter(
            x=z["years"], y=z["zero_yield"], mode="lines+markers", name=f"{label} — Zero",
            hovertemplate="t=%{x:.2f}y<br>z=%{y:.3f}%<extra></extra>"
        ))

    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), template=theme)
    fig.update_xaxes(title="Maturity (years)")
    fig.update_yaxes(title="Rate / Yield (%)", tickformat=".2f")  # <- ajout
    return fig

# ---- Heatmap G10 spreads ----
def plot_matrix_heatmap(df_matrix: pd.DataFrame, title="G10 Spreads vs Bund (bp)", theme: str = "bbg"):
    fig = go.Figure()
    if df_matrix is None or df_matrix.empty or df_matrix.shape[1] <= 1:
        fig.update_layout(title=title, template=theme)
        return fig

    d = df_matrix.copy()
    # assurer l'ordre de lecture des lignes/colonnes
    rows = list(d["country"]) if "country" in d.columns else list(d.index)
    if "country" in d.columns:
        d = d.set_index("country")
    cols = list(d.columns)

    # heatmap centrée sur 0 pour lecture instantanée
    z_vals = d.values
    fig = go.Figure(data=go.Heatmap(
        z=z_vals, x=cols, y=rows,
        colorscale="RdBu", reversescale=True, zmid=0,
        colorbar=dict(title="bp")
    ))
    fig.update_layout(title=title, margin=dict(l=20, r=20, t=40, b=20), template=theme)
    return fig

# ---- ZC swap curve ----
def plot_ZC_swap(df_swaps: pd.DataFrame, currency: str, comp: str = "cont", theme: str = "bbg"):
    fig = go.Figure()
    if df_swaps is None or df_swaps.empty:
        fig.update_layout(title=f"{currency} Swaps — Zero (aucune donnée)", template=theme)
        return fig

    freq = _swap_freq_for(currency)
    z = bootstrap_zero_from_par_swaps(df_swaps, freq=freq, comp=comp)
    if z is None or z.empty:
        fig.update_layout(title=f"{currency} Swaps — Zero (aucune donnée)", template=theme)
        return fig

    z = z.sort_values("years")
    fig.add_trace(go.Scatter(
        x=z["years"], y=z["zero_yield"], mode="lines+markers",
        name=f"{currency} Swaps — Zero",
        hovertemplate="t=%{x:.2f}y<br>z=%{y:.3f}%<extra></extra>"
    ))
    fig.update_layout(
        title=f"{currency} Swaps — Zero",
        margin=dict(l=20, r=20, t=40, b=20),
        template=theme
    )
    fig.update_xaxes(title="Maturity (years)")
    fig.update_yaxes(title="Zero rate (%)", tickformat=".2f")  # <- ajout
    return fig
