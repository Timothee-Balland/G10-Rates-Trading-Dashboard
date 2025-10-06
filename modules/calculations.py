#calculations.py
import pandas as pd
import math
import numpy as np

def _coerce_years_from_tenor(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "years" not in d.columns:
        if "tenor" in d.columns:
            d["years"] = d["tenor"].map(_tenor_to_years)
    d["years"] = pd.to_numeric(d.get("years", np.nan), errors="coerce")
    return d

def _pick_rate_col(df: pd.DataFrame, preferred: str | None = None) -> str | None:
    """Choisit une colonne de taux (en %) parmi les candidates."""
    if preferred and preferred in df.columns:
        return preferred
    candidates = ["rate", "yield", "par", "swap", "ois"]
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _clean_curve(df: pd.DataFrame, rate_col: str) -> pd.DataFrame:
    """Nettoie une courbe: garde tenor (si présent), years, et la colonne de taux."""
    if df is None or df.empty or rate_col not in df.columns:
        return pd.DataFrame(columns=["tenor","years",rate_col])
    d = _coerce_years_from_tenor(df)
    d[rate_col] = pd.to_numeric(d[rate_col], errors="coerce")
    d = d.dropna(subset=["years", rate_col]).copy()
    # dédoublonner sur years (moyenne si doublons)
    agg = {"years": "first", rate_col: "mean"}
    if "tenor" in d.columns:
        agg["tenor"] = "first"
    d = (
        d.sort_values("years")
         .groupby("years", as_index=False)
         .agg(agg)
         .sort_values("years")
    )
    return d

def add_spread_vs_ref(df_all: pd.DataFrame, target_country: str, ref_country: str = "Germany") -> pd.DataFrame:
    """
    Calcule le spread (en bp) du pays 'target_country' vs 'ref_country' (ex: vs Bund).
    Retourne un DF avec colonnes: country (target), tenor, years, spread_bp.
    """
    # Sélection par pays
    d_t = df_all[df_all["country"].str.lower() == target_country.lower()].copy()
    d_r = df_all[df_all["country"].str.lower() == ref_country.lower()].copy()
    if d_t.empty or d_r.empty:
        return pd.DataFrame(columns=["country", "tenor", "years", "spread_bp"])

    # Harmoniser years
    if "years" not in d_t.columns and "tenor" in d_t.columns:
        d_t["years"] = d_t["tenor"].map(_tenor_to_years)
    if "years" not in d_r.columns and "tenor" in d_r.columns:
        d_r["years"] = d_r["tenor"].map(_tenor_to_years)

    d_t = d_t.dropna(subset=["years", "yield"])
    d_r = d_r.dropna(subset=["years", "yield"])

    # Merge sur la maturité (on s'aligne par 'tenor' si dispo, sinon par 'years' arrondi)
    if "tenor" in d_t.columns and "tenor" in d_r.columns:
        m = d_t.merge(d_r[["tenor", "yield"]].rename(columns={"yield": "yield_ref"}), on="tenor", how="inner")
    else:
        d_t["__ky"] = d_t["years"].round(6)
        d_r["__ky"] = d_r["years"].round(6)
        m = d_t.merge(d_r[["__ky", "yield"]].rename(columns={"yield": "yield_ref"}), on="__ky", how="inner")
        m.drop(columns="__ky", inplace=True, errors="ignore")

    if m.empty:
        return pd.DataFrame(columns=["country", "tenor", "years", "spread_bp"])

    m["spread_bp"] = (m["yield"] - m["yield_ref"]) * 100.0
    return m[["country", "tenor", "years", "spread_bp"]].sort_values("years").reset_index(drop=True)

def _tenor_to_years(tenor: str | float | int | None) -> float | None:
    if tenor is None:
        return None
    if isinstance(tenor, (int, float)):
        return float(tenor)
    s = str(tenor).strip().upper()
    if s.endswith("Y"):
        return float(s[:-1])
    if s.endswith("M"):
        return float(s[:-1]) / 12.0
    return None

def bootstrap_zero_from_par(df_country: pd.DataFrame, freq: int = 2, comp: str = "cont") -> pd.DataFrame:
    d = df_country.copy()
    if "years" not in d.columns and "tenor" in d.columns:
        d["years"] = d["tenor"].map(_tenor_to_years)

    d = d.dropna(subset=["years", "yield"]).sort_values("years").reset_index(drop=True)
    d["N"] = (d["years"] * freq).round().astype(int)
    d = d[d["N"] > 0].drop_duplicates(subset=["N"]).reset_index(drop=True)

    DF = {}
    rows = []

    for _, row in d.iterrows():
        N = int(row["N"])
        y = float(row["yield"]) / 100.0
        c = (y / freq) * 100.0

        # somme des coupons actualisés jusque N-1 (si manque un DF_k, on saute)
        coupon_sum = 0.0
        if N > 1:
            for k in range(1, N):
                if k in DF:
                    coupon_sum += c * DF[k]

        # DF_N à parité
        denom = (100.0 + c)
        numer = (100.0 - coupon_sum)

        # garde-fous: si numer <= 0, forcer DF très petit mais positif pour éviter log <= 0
        if numer <= 1e-9:
            DF_N = 1e-12
        else:
            DF_N = numer / denom

        # clamp (évite >1 ou <=0 à cause du bruit)
        DF_N = max(min(DF_N, 1.0), 1e-12)
        DF[N] = DF_N

        t = N / freq
        if comp == "cont":
            zero = -math.log(DF_N) / max(t, 1e-12)
        else:
            zero = (DF_N ** (-1.0 / max(t, 1e-12))) - 1.0

        rows.append({"years": t, "zero_yield": zero * 100.0})

    return pd.DataFrame(rows).sort_values("years").reset_index(drop=True)

def bootstrap_zero_from_par_swaps(df_swaps: pd.DataFrame, freq: int = 2, comp: str = "cont") -> pd.DataFrame:
    """
    df_swaps: colonnes 'years' (float), 'rate' (en %) triées croissant.
    formule: DF_N = (1 - S*α*Σ DF_k) / (1 + S*α), α = 1/freq
    """
    if df_swaps is None or df_swaps.empty:
        return pd.DataFrame(columns=["years","zero_yield"])

    d = df_swaps.dropna(subset=["years","rate"]).copy().sort_values("years")
    d["N"] = (d["years"] * freq).round().astype(int)
    d = d[d["N"] > 0].drop_duplicates(subset=["N"]).reset_index(drop=True)

    DF = {}
    rows = []
    alpha = 1.0 / freq

    for _, row in d.iterrows():
        N = int(row["N"]); S = float(row["rate"]) / 100.0
        annuity = sum(alpha * DF[k] for k in range(1, N) if k in DF)
        DF_N = (1.0 - S * annuity) / (1.0 + S * alpha)
        DF_N = max(min(DF_N, 1.0), 1e-12)
        DF[N] = DF_N
        t = N / freq
        if comp == "cont":
            z = -math.log(DF_N) / max(t, 1e-12)
        else:
            z = DF_N ** (-1.0 / max(t, 1e-12)) - 1.0
        rows.append({"years": t, "zero_yield": z * 100.0})

    return pd.DataFrame(rows).sort_values("years").reset_index(drop=True)

def add_zero_curve(df_country: pd.DataFrame, freq: int = 2, comp: str = "cont") -> pd.DataFrame:
    """
    Ajoute les colonnes 'zero_years' et 'zero_yield' (en %) à un DF pays.
    Si plusieurs pays sont passés par erreur, on ne garde que le premier.
    """
    d = df_country.copy()
    if "country" in d.columns and d["country"].nunique() > 1:
        first = d["country"].iloc[0]
        d = d[d["country"] == first].copy()

    z = bootstrap_zero_from_par(d, freq=freq, comp=comp)
    d = d.copy()
    # merge par 'years' (arrondis pour robustesse)
    d["__key_years"] = d["years"].round(6)
    z["__key_years"] = z["years"].round(6)
    d = d.merge(z[["__key_years", "zero_yield"]], on="__key_years", how="left")
    d = d.drop(columns="__key_years")
    return d

def add_spread_vs_ref_par(df_target: pd.DataFrame, df_ref: pd.DataFrame,
                          ycol_target: str | None = None, ycol_ref: str | None = None,
                          country_label: str | None = None, ref_label: str | None = None,
                          nearest_tol_years: float = 0.15) -> pd.DataFrame:
    """
    Calcule un spread (bp) entre deux courbes 'par' (swaps/bonds) même si les grilles de maturités diffèrent.
    - Détecte automatiquement les colonnes de taux si non fournies.
    - Aligne d'abord par merge strict (years), puis fallback en merge_asof (nearest).
    - Retourne colonnes: tenor, years, spread_bp, country.
    """
    # Choix des colonnes de taux
    yt = _pick_rate_col(df_target, ycol_target)
    yr = _pick_rate_col(df_ref,    ycol_ref)
    if yt is None or yr is None:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    a = _clean_curve(df_target, yt)
    b = _clean_curve(df_ref,    yr).rename(columns={yr: "ref"})
    if a.empty or b.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    # 1) Merge strict sur years
    m = a.merge(b[["years","ref"]], on="years", how="inner")

    # 2) Fallback: nearest merge si rien ou trop peu (tolérance ~0.15y ~ 1.8 mois)
    if m.empty or len(m) < max(2, int(0.3 * min(len(a), len(b)))):
        a_sorted = a.sort_values("years")
        b_sorted = b.sort_values("years")
        m = pd.merge_asof(
            a_sorted, b_sorted[["years","ref"]], on="years",
            direction="nearest", tolerance=nearest_tol_years
        )
        m = m.dropna(subset=["ref"])

    if m is None or m.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    m["spread_bp"] = (m[yt] - m["ref"]) * 100.0
    m["country"] = country_label or (df_target["country"].iloc[0] if "country" in df_target.columns and not df_target.empty else "—")

    # Colonnes de sortie attendues par plot_spread
    if "tenor" not in m.columns and "tenor" in df_target.columns:
        m["tenor"] = df_target.set_index("years").reindex(m["years"]).reset_index().get("tenor")
    cols = [c for c in ["tenor","years","spread_bp","country"] if c in m.columns]
    # garantir les 4 colonnes (tenor peut manquer, ce n'est pas bloquant)
    out = m.reindex(columns=["tenor","years","spread_bp","country"])
    return out.sort_values("years").reset_index(drop=True)

# --- Relative Value helpers (robustes) ---

def _coerce_years_from_tenor_local(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "years" not in d.columns and "tenor" in d.columns:
        d["years"] = pd.to_numeric(d["tenor"].astype(str).str.upper().str.replace("Y","", regex=False),
                                   errors="coerce")
    d["years"] = pd.to_numeric(d.get("years", np.nan), errors="coerce")
    return d

def _clean_par_curve(df: pd.DataFrame, rate_col: str) -> pd.DataFrame:
    """Garde years + rate_col (+ tenor si dispo), enlève NaN, déduplique par years."""
    if df is None or df.empty or rate_col not in df.columns:
        return pd.DataFrame(columns=["tenor","years",rate_col])
    d = _coerce_years_from_tenor_local(df)
    d[rate_col] = pd.to_numeric(d.get(rate_col, np.nan), errors="coerce")
    d = d.dropna(subset=["years", rate_col]).sort_values("years")
    agg = {"years":"first", rate_col:"mean"}
    if "tenor" in d.columns:
        agg["tenor"] = "first"
    d = d.groupby("years", as_index=False).agg(agg).sort_values("years")
    return d

def swap_spread_vs_ref(df_target_swaps: pd.DataFrame,
                       df_ref_swaps: pd.DataFrame,
                       country_label: str,
                       tol_years: float = 0.15) -> pd.DataFrame:
    """
    Spread swaps classique : IRS(target) - IRS(ref), en bp.
    Aligne par years (strict puis nearest).
    Retour: tenor, years, spread_bp, country
    """
    a = _clean_par_curve(df_target_swaps, rate_col="rate")
    b = _clean_par_curve(df_ref_swaps,    rate_col="rate").rename(columns={"rate":"ref"})
    if a.empty or b.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    m = a.merge(b[["years","ref"]], on="years", how="inner")
    if m.empty or len(m) < max(2, int(0.3 * min(len(a), len(b)))):
        m = pd.merge_asof(a.sort_values("years"),
                          b.sort_values("years")[["years","ref"]],
                          on="years", direction="nearest", tolerance=tol_years).dropna(subset=["ref"])

    if m.empty:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    m["spread_bp"] = (m["rate"] - m["ref"]) * 100.0
    m["country"] = country_label

    # assurer tenor si dispo côté target
    if "tenor" not in m.columns and "tenor" in df_target_swaps.columns:
        base = _coerce_years_from_tenor_local(df_target_swaps).dropna(subset=["years"]).drop_duplicates("years").set_index("years")
        m["tenor"] = base.reindex(m["years"]).get("tenor").values

    return m.reindex(columns=["tenor","years","spread_bp","country"]).sort_values("years").reset_index(drop=True)

def asw_spread(df_bonds: pd.DataFrame,
               df_swaps_same_ccy: pd.DataFrame,
               country_label: str,
               ycol_bonds: str = "yield") -> pd.DataFrame:
    """
    ASW approx = Gov(yield) - IRS(rate), en bp.
    Méthode robuste : interpolation systématique de la courbe IRS sur les 'years' des govies.
    Retour: tenor, years, spread_bp, country
    """
    # Nettoyage / normalisation
    a = _clean_par_curve(df_bonds,  rate_col=ycol_bonds).rename(columns={ycol_bonds: "bond"})
    b = _clean_par_curve(df_swaps_same_ccy, rate_col="rate").rename(columns={"rate":"swap"})
    if a.empty or len(b) < 2:
        return pd.DataFrame(columns=["tenor","years","spread_bp","country"])

    # Vecteurs triés
    xa = a["years"].to_numpy()
    ya = a["bond"].to_numpy()
    xb = b["years"].to_numpy()
    yb = b["swap"].to_numpy()

    # Interpolation IRS sur les maturités bonds (clamp aux bornes)
    swap_interp = np.interp(xa, xb, yb, left=yb[0], right=yb[-1])

    m = pd.DataFrame({
        "years": xa,
        "bond":  ya,
        "swap":  swap_interp
    })
    m["spread_bp"] = (m["bond"] - m["swap"]) * 100.0
    m["country"] = country_label

    # Conserver tenor côté gov si dispo
    if "tenor" in a.columns:
        ten_map = a.drop_duplicates("years").set_index("years")["tenor"]
        m["tenor"] = m["years"].map(ten_map)

    return m.reindex(columns=["tenor","years","spread_bp","country"])\
            .sort_values("years").reset_index(drop=True)
