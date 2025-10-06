# modules/swap_loader.py
import pandas as pd
import numpy as np

def _compute_asw(df_bonds: pd.DataFrame, df_swaps: pd.DataFrame, ycol_bonds: str = "yield", ycol_swaps: str = "rate") -> pd.DataFrame:
    """
    Aligne bonds et swaps par 'years' (strict puis nearest) et calcule ASW = (bond - swap)*100 en bp.
    Retourne colonnes: tenor, years, spread_bp
    """
    def _prep_bonds(d):
        x = d.copy()
        if "years" not in x.columns and "tenor" in x.columns:
            x["years"] = pd.to_numeric(x["tenor"].str.replace("Y","", regex=False), errors="coerce")
        x["years"] = pd.to_numeric(x.get("years", np.nan), errors="coerce")
        x[ycol_bonds] = pd.to_numeric(x.get(ycol_bonds, np.nan), errors="coerce")
        x = x.dropna(subset=["years", ycol_bonds]).sort_values("years")
        x = x.groupby("years", as_index=False).agg({ycol_bonds:"mean", **({"tenor":"first"} if "tenor" in x.columns else {})})
        return x

    def _prep_swaps(d):
        x = d.copy()
        if "years" not in x.columns and "tenor" in x.columns:
            x["years"] = pd.to_numeric(x["tenor"].str.replace("Y","", regex=False), errors="coerce")
        x["years"] = pd.to_numeric(x.get("years", np.nan), errors="coerce")
        x[ycol_swaps] = pd.to_numeric(x.get(ycol_swaps, np.nan), errors="coerce")
        x = x.dropna(subset=["years", ycol_swaps]).sort_values("years")
        x = x.groupby("years", as_index=False).agg({ycol_swaps:"mean", **({"tenor":"first"} if "tenor" in x.columns else {})})
        return x

    a = _prep_bonds(df_bonds)
    b = _prep_swaps(df_swaps).rename(columns={ycol_swaps: "swap"})
    if a.empty or b.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp"])

    # Merge strict, puis fallback nearest
    m = a.merge(b[["years","swap"]], on="years", how="inner")
    if m.empty or len(m) < max(2, int(0.3 * min(len(a), len(b)))):
        a_sorted = a.sort_values("years")
        b_sorted = b.sort_values("years")
        m = pd.merge_asof(a_sorted, b_sorted[["years","swap"]], on="years", direction="nearest", tolerance=0.15)
        m = m.dropna(subset=["swap"])

    if m.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp"])

    m["spread_bp"] = (m[ycol_bonds] - m["swap"]) * 100.0
    # garder le tenor côté bonds si dispo
    if "tenor" not in m.columns and "tenor" in df_bonds.columns:
        # tentative douce de map via years
        tb = df_bonds.dropna(subset=["years"]).drop_duplicates("years").set_index("years")
        m["tenor"] = tb.reindex(m["years"]).get("tenor").values
    return m[["tenor","years","spread_bp"]].sort_values("years").reset_index(drop=True)

def load_swaps(currency: str) -> pd.DataFrame:
    """
    Retourne un DF avec colonnes: 'currency','tenor','years','rate' (en %).
    Stub de données pour G10. Remplace par tes vraies sources quand prêt.
    """
    data = {
        "EUR": {"1Y": 3.40, "2Y": 3.10, "3Y": 2.90, "5Y": 2.70, "7Y": 2.60, "10Y": 2.55, "15Y": 2.50, "20Y": 2.50, "30Y": 2.45},
        "USD": {"1Y": 4.80, "2Y": 4.30, "3Y": 4.10, "5Y": 3.90, "7Y": 3.80, "10Y": 3.75, "15Y": 3.70, "20Y": 3.65, "30Y": 3.60},
        "CAD": {"1Y": 4.30, "2Y": 3.90, "3Y": 3.75, "5Y": 3.55, "7Y": 3.45, "10Y": 3.40, "15Y": 3.35, "20Y": 3.30, "30Y": 3.25},
        "GBP": {"1Y": 5.10, "2Y": 4.60, "3Y": 4.30, "5Y": 4.05, "7Y": 3.95, "10Y": 3.85, "15Y": 3.80, "20Y": 3.75, "30Y": 3.70},
        "JPY": {"1Y": 0.35, "2Y": 0.40, "3Y": 0.45, "5Y": 0.55, "7Y": 0.65, "10Y": 0.75, "15Y": 0.90, "20Y": 1.00, "30Y": 1.10},
        "AUD": {"1Y": 4.10, "2Y": 3.95, "3Y": 3.90, "5Y": 3.85, "7Y": 3.90, "10Y": 3.95, "15Y": 4.00, "20Y": 4.00, "30Y": 4.05},
        "NZD": {"1Y": 4.50, "2Y": 4.10, "3Y": 3.95, "5Y": 3.80, "7Y": 3.80, "10Y": 3.80, "15Y": 3.85, "20Y": 3.85, "30Y": 3.90},
        "SEK": {"1Y": 3.70, "2Y": 3.35, "3Y": 3.20, "5Y": 3.05, "7Y": 2.95, "10Y": 2.90, "15Y": 2.85, "20Y": 2.85, "30Y": 2.80},
    }

    ccy = (currency or "").upper()
    curve = data.get(ccy)
    if not curve:
        # Fallback gentil: réutilise la forme EUR si devise absente
        base = data["EUR"]
        rows = [(ccy, t, _tenor_to_years(t), r) for t, r in base.items()]
        return pd.DataFrame(rows, columns=["currency","tenor","years","rate"]).sort_values("years")

    rows = [(ccy, t, _tenor_to_years(t), r) for t, r in curve.items()]
    return pd.DataFrame(rows, columns=["currency","tenor","years","rate"]).sort_values("years")

def _tenor_to_years(t: str) -> float:
    t = str(t).strip().upper()
    if t.endswith("Y"): return float(t[:-1])
    if t.endswith("M"): return float(t[:-1]) / 12.0
    return float("nan")