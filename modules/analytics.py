# modules/analytics.py
from __future__ import annotations
import pandas as pd
import numpy as np

# ---------- Basics ----------
def tenor_to_years(tenor: str) -> float | None:
    if not isinstance(tenor, str):
        return None
    s = tenor.strip().upper()
    if s.endswith("Y"):
        return float(s[:-1])
    if s.endswith("M"):
        return float(s[:-1]) / 12.0
    return None

def ensure_years(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "years" not in d.columns and "tenor" in d.columns:
        d["years"] = d["tenor"].map(tenor_to_years)
    return d

# ---------- Spreads & Flies ----------
def two_leg_spreads(df_country: pd.DataFrame) -> dict[str, float | None]:
    d = ensure_years(df_country).set_index("tenor")
    out = {}
    def val(t): 
        return None if t not in d.index or "yield" not in d.columns else d.loc[t, "yield"]
    try:
        out["2s10s_bp"] = (val("2Y") - val("10Y")) * 100 if val("2Y") is not None and val("10Y") is not None else None
        out["5s30s_bp"] = (val("5Y") - val("30Y")) * 100 if val("5Y") is not None and val("30Y") is not None else None
        out["2s5s_bp"]  = (val("2Y") - val("5Y"))  * 100 if val("2Y") is not None and val("5Y")  is not None else None
    except Exception:
        pass
    return out

def fly_2_5_10(df_country: pd.DataFrame) -> float | None:
    """Simple 2s/5s/10s fly: 2*5Y - (2Y+10Y) (in bp)."""
    d = ensure_years(df_country).set_index("tenor")
    need = {"2Y","5Y","10Y"}
    if not need.issubset(set(d.index)) or "yield" not in d.columns:
        return None
    y2, y5, y10 = d.loc["2Y","yield"], d.loc["5Y","yield"], d.loc["10Y","yield"]
    return (2*y5 - (y2 + y10)) * 100

# ---------- Carry & Roll (quick approximations) ----------
def carry_roll_table(df_country: pd.DataFrame) -> pd.DataFrame:
    """
    Approx carry/roll:
      - slope local ~ dY/dT (bp per year)
      - roll_1m ~ slope/12 (bp)
      - carry_1m: here equal to roll_1m as a simple proxy (no coupon model)
    """
    d = ensure_years(df_country).sort_values("years")[["years","tenor","yield"]].dropna()
    if d.empty:
        return d.assign(roll_1m_bp=np.nan, carry_1m_bp=np.nan, roll_3m_bp=np.nan, carry_3m_bp=np.nan)
    # slope local (finite diff)
    d["slope_bp_per_y"] = d["yield"].diff() / d["years"].diff() * 100
    d["roll_1m_bp"] = d["slope_bp_per_y"] / 12.0
    d["roll_3m_bp"] = d["slope_bp_per_y"] / 4.0
    d["carry_1m_bp"] = d["roll_1m_bp"]   # proxy simple
    d["carry_3m_bp"] = d["roll_3m_bp"]   # proxy simple
    return d

# ---------- G10 Matrix vs Bund ----------
def g10_matrix_spreads_vs_ref(df_all: pd.DataFrame, tenors=("2Y","5Y","10Y","30Y"),
                              ref_country="Germany") -> pd.DataFrame:
    """
    Returns wide matrix: rows=countries, columns=tenors, values=spread vs ref (bp).
    """
    d = df_all.copy()
    d = d[d["tenor"].isin(tenors)][["country","tenor","yield"]]
    if d.empty:
        return pd.DataFrame(columns=["country", *tenors])

    ref = d[d["country"].str.lower()==ref_country.lower()][["tenor","yield"]].rename(columns={"yield":"ref"})
    m = d.merge(ref, on="tenor", how="left")
    m["spread_bp"] = (m["yield"] - m["ref"]) * 100
    wide = m.pivot(index="country", columns="tenor", values="spread_bp").reset_index()
    # order columns
    cols = ["country"] + [t for t in tenors if t in wide.columns]
    wide = wide[cols]
    return wide
