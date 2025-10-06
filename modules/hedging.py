# modules/hedging.py
from __future__ import annotations
import math
import pandas as pd
import numpy as np

def _y_to_per_period(y_pct: float, freq: int) -> float:
    return (y_pct/100.0) / freq

def bond_price_clean(face: float, coupon_pct: float, ytm_pct: float, T_years: float, freq: int = 2) -> float:
    # prix clean approx (sans accrued), rendement simple compounding
    c = coupon_pct/100.0 * face / freq
    y = _y_to_per_period(ytm_pct, freq)
    n = int(round(T_years*freq))
    if n <= 0: 
        return face
    pv = sum(c / ((1+y)**k) for k in range(1, n+1)) + face/((1+y)**n)
    return pv

def bond_dv01(face: float, coupon_pct: float, ytm_pct: float, T_years: float, freq: int = 2, bump_bp: float = 1.0) -> float:
    # DV01 ~ -dP/dy * 0.0001 ; on fait un bump up/down
    p0 = bond_price_clean(face, coupon_pct, ytm_pct, T_years, freq)
    p_up = bond_price_clean(face, coupon_pct, ytm_pct + bump_bp/100.0, T_years, freq)
    dv01 = (p_up - p0) / (bump_bp/10000.0)  # ΔP / Δy
    return abs(dv01)

def swap_dv01_from_par_curve(df_swaps: pd.DataFrame, tenor_years: float, freq: int = 2, bump_bp: float = 1.0) -> float:
    """
    Approx DV01 du payer-fix/receiver-float IRS de maturité 'tenor_years'
    en utilisant ta courbe 'par' locale (columns: years, rate(%)). On bump la courbe parallèle.
    """
    if df_swaps.empty:
        return np.nan
    # trouve la rate au plus proche
    df = df_swaps.dropna(subset=["years","rate"]).copy().sort_values("years")
    idx = (df["years"] - tenor_years).abs().idxmin()
    s0 = float(df.loc[idx,"rate"])
    # valuation simplifiée: prix ~ annuity * (par - s0) -> DV01 ~ annuity
    # approx annuity: somme des DF * α ; on l'approche via  tenor_years * α avec DF~1 (rapide)
    alpha = 1.0/freq
    annuity_guess = tenor_years * alpha * 100.0  # valeur notionnelle 100
    return annuity_guess  # en prix / 1bp

def futures_dv01_lookup(symbol: str) -> float:
    """
    Table rapide DV01 moyen par contrat (notionnel standard 100k/200k).
    À peaufiner avec CTD & conversion factor si tu as les données.
    """
    table = {
        "FGBL": 85.0,   # Bund 10Y (€/contrat par 1bp) ~ ordre de grandeur
        "ZN":   80.0,   # UST 10Y note
        "ZB":  120.0,   # UST Bond 30Y
        "FGBM": 55.0,   # Bobl 5Y
        "FGBS": 30.0,   # Schatz 2Y
    }
    return table.get(symbol.upper(), np.nan)

def pick_nearest_swap_tenor(df_swaps: pd.DataFrame, T_years: float) -> float:
    if df_swaps.empty:
        return np.nan
    y = df_swaps.dropna(subset=["years"]).sort_values("years")["years"]
    return float(y.iloc[(y - T_years).abs().idxmin()])

def liquidity_score(is_on_the_run: bool = True, bid_ask_bp: float | None = 1.0, est_daily_volume_mm: float | None = 50.0) -> float:
    """
    Score [0..1] très simple: OTR + bid-ask serré + volume élevé -> score ↑
    """
    s = 0.0
    if is_on_the_run: s += 0.4
    if bid_ask_bp is not None:
        s += max(0.0, min(0.3, 0.3*(2.0/max(0.5, bid_ask_bp))))  # 0.5bp -> ~0.3 ; 2bp -> ~0.075
    if est_daily_volume_mm is not None:
        s += max(0.0, min(0.3, 0.3*(est_daily_volume_mm/200.0))) # 200mm -> ~0.3
    return min(1.0, s)

def hedge_proposal(
    bond_country: str,
    face: float,
    coupon_pct: float,
    ytm_pct: float,
    T_years: float,
    df_swaps_ccy: pd.DataFrame,
    futures_symbol: str | None = None,
    swap_freq_by_ccy: int = 2
) -> dict:
    dv01_bond = bond_dv01(face, coupon_pct, ytm_pct, T_years, freq=2)
    out = {"dv01_bond": dv01_bond}

    # Hedge via futures (si symbole fourni)
    if futures_symbol:
        dv01_fut = futures_dv01_lookup(futures_symbol)
        if not math.isnan(dv01_fut) and dv01_fut > 0:
            n_fut = dv01_bond / dv01_fut
            out["futures"] = {"symbol": futures_symbol, "dv01_per_contract": dv01_fut, "contracts": round(n_fut, 2)}
        else:
            out["futures"] = {"symbol": futures_symbol, "note": "DV01 inconnu"}

    # Hedge via IRS (asset swap plain vanilla)
    tenor_swap = pick_nearest_swap_tenor(df_swaps_ccy, T_years)
    irs_dv01 = swap_dv01_from_par_curve(df_swaps_ccy, tenor_swap, freq=swap_freq_by_ccy)
    if not math.isnan(irs_dv01) and irs_dv01 > 0:
        notional_irs = dv01_bond / irs_dv01 * 100.0  # scale notionnel pour DV01 ~ match (bond notionnel=100)
        out["irs"] = {"tenor_years": tenor_swap, "dv01_per_100": irs_dv01, "receiver_fix_notional": round(notional_irs, 4)}
    else:
        out["irs"] = {"note": "Courbe swaps indisponible"}

    # Liquidity (placeholder)
    out["liquidity_score"] = round(liquidity_score(), 2)
    return out
