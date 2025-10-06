#data_loader.py
from __future__ import annotations
import re
import time
from typing import Iterable, Optional, Dict, Any
import requests
import pandas as pd
from io import StringIO

# ------------------ Config ------------------

WORLD_URL = "https://www.investing.com/rates-bonds/world-government-bonds"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
}
_SESSION = requests.Session()

# Slugs des pages "pays" (fallback) — ajoute/ajuste au besoin
COUNTRY_PAGE_SLUGS = {
    "United States": "usa-government-bonds",
    "Canada": "canada-government-bonds",
    "United Kingdom": "uk-government-bonds",
    "Germany": "germany-government-bonds",
    "France": "france-government-bonds",
    "Italy": "italy-government-bonds",
    "Japan": "japan-government-bonds",
    "Australia": "australia-government-bonds",
    "New Zealand": "new-zealand-government-bonds",
    "Sweden": "sweden-government-bonds",
}

DEFAULT_G10 = list(COUNTRY_PAGE_SLUGS.keys())


# ------------------ Utils ------------------

_NUM_REPLACERS = (
    (",", ""),  # 1,234.5 -> 1234.5
    ("+", ""),  # +0.08 -> 0.08
    ("%", ""),  # 3.50% -> 3.50
)

def _to_float(x: Any) -> float | None:
    if pd.isna(x):
        return None
    s = str(x).strip()
    for a, b in _NUM_REPLACERS:
        s = s.replace(a, b)
    try:
        return float(s)
    except ValueError:
        return None

def tenor_to_years(tenor: str | None) -> float | None:
    """'10Y' -> 10.0 ; '6M' -> 0.5 ; '3M' -> 0.25 ; retourne None si inconnu."""
    if not isinstance(tenor, str):
        return None
    t = tenor.strip().upper()
    if t.endswith("Y"):
        return float(t[:-1].strip())
    if t.endswith("M"):
        return float(t[:-1].strip()) / 12.0
    return None

def _http_get(url: str, session: Optional[requests.Session] = None, retries: int = 2, backoff: float = 0.8) -> str:
    sess = session or _SESSION
    last_err = None
    for i in range(retries + 1):
        try:
            resp = sess.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            if i < retries:
                time.sleep(backoff * (2 ** i))
            else:
                raise
    raise last_err  # ne devrait pas arriver


# ------------------ Parsing ------------------

def _parse_world_tables(html: str) -> pd.DataFrame:
    """Parse la page 'world-government-bonds' et retourne un DF consolidé normalisé."""
    tables = pd.read_html(StringIO(html))  # évite le FutureWarning
    # garder les tables qui contiennent au moins 'Name' et 'Yield'
    wanted = [t for t in tables if {"Name", "Yield"}.issubset(set(map(str, t.columns)))]
    if not wanted:
        raise ValueError("Aucune table 'Name'/'Yield' détectée sur la page World.")

    df = pd.concat(wanted, ignore_index=True)
    # normalisation colonnes
    df.columns = [str(c).strip().lower() for c in df.columns]
    # certaines tables ont des colonnes 'unnamed: x' parasites
    df = df.loc[:, ~df.columns.str.startswith("unnamed")].copy()

    # extraire country & tenor depuis 'name' si pas déjà présent
    if "country" not in df.columns:
        df["country"] = df["name"].str.extract(r"^([A-Za-z \-']+)")
    if "tenor" not in df.columns:
        df["tenor"] = df["name"].str.extract(r"(\d+\s*[MYmy])")

    # champs numériques
    for col in ("yield", "prev.", "high", "low", "chg.", "chg. %"):
        if col in df.columns:
            df[col] = df[col].map(_to_float)

    # convertir tenor -> years
    df["years"] = df["tenor"].map(tenor_to_years)

    # cleanup des pays/tenors
    df["country"] = df["country"].astype(str).str.strip()
    df["tenor"] = df["tenor"].astype(str).str.upper().str.strip()

    # enlever lignes sans yield ou years
    df = df.dropna(subset=["yield", "years"]).copy()

    # enlever doublons éventuels (même pays/tenor)
    df = df.drop_duplicates(subset=["country", "tenor"]).reset_index(drop=True)

    return df


def _parse_country_page(html: str, country_name: str) -> pd.DataFrame:
    """Parse une page 'xxx-government-bonds' pour un pays donné, normalise comme le world DF."""
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise ValueError(f"Aucune table détectée sur la page du pays: {country_name}")
    # généralement la première table est la grille des maturités
    df = tables[0].copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("unnamed")].copy()

    # s'assurer des colonnes minimales
    if "name" not in df.columns:
        # certaines pages ont 'bond' au lieu de 'name'
        for alt in ("bond", "title"):
            if alt in df.columns:
                df.rename(columns={alt: "name"}, inplace=True)
                break

    if "name" in df.columns:
        # extraire tenor si pas présent
        if "tenor" not in df.columns:
            df["tenor"] = df["name"].str.extract(r"(\d+\s*[MYmy])")
        # si la colonne "country" n'existe pas
        if "country" not in df.columns:
            # "Australia 10Y" -> "Australia"
            guess = df["name"].str.extract(r"^([A-Za-z \-']+)")
            df["country"] = guess[0].fillna(country_name)
    else:
        # fallback: injecter country fourni
        df["country"] = country_name

    # champs numériques
    for col in ("yield", "prev.", "high", "low", "chg.", "chg. %"):
        if col in df.columns:
            df[col] = df[col].map(_to_float)

    # tenor -> years
    df["tenor"] = df["tenor"].astype(str).str.upper().str.strip()
    df["years"] = df["tenor"].map(tenor_to_years)

    # filtrer lignes valides
    if "yield" in df.columns:
        df = df.dropna(subset=["yield", "years"])
    else:
        df = df.dropna(subset=["years"])

    # normaliser "country"
    df["country"] = df["country"].astype(str).str.strip()

    # dédoublonner
    df = df.drop_duplicates(subset=["country", "tenor"]).reset_index(drop=True)
    return df


# ------------------ Public API ------------------

def fetch_yields(
    countries: Optional[Iterable[str]] = None,
    prefer_world: bool = True,
    session: Optional[requests.Session] = None
) -> pd.DataFrame:
    """
    Récupère les courbes de taux (pays, tenor, yield, years, + colonnes annexes si dispo)
    pour la page Investing 'world-government-bonds', avec fallback par pages pays.

    :param countries: liste de pays à garder (nom tel qu'apparaît dans la page, ex: 'Australia').
                      Si None -> renvoie tout.
    :param prefer_world: True = on scrap la page globale puis on filtre; False = on passe directement par les pages pays.
    :param session: requests.Session optionnel.
    :return: DataFrame avec colonnes au moins: country, tenor, years, yield, (prev., high, low, chg., chg. %, time si dispo)
    """
    s = session or requests.Session()

    result_frames = []

    wanted = set(countries) if countries else None

    if prefer_world:
        try:
            world_html = _http_get(WORLD_URL, s)
            world_df = _parse_world_tables(world_html)
            if wanted:
                world_df = world_df[world_df["country"].isin(wanted)].copy()
            result_frames.append(world_df)
            # retirer de wanted les pays déjà trouvés
            if wanted:
                covered = set(world_df["country"].unique())
                missing = list(wanted - covered)
            else:
                missing = []
        except Exception:
            # si la page globale échoue, on passera entièrement par les pages pays
            missing = list(wanted) if wanted else []

    else:
        missing = list(wanted) if wanted else DEFAULT_G10

    # fallback : pages pays pour ceux manquants/explicitement demandés
    for country in missing:
        slug = COUNTRY_PAGE_SLUGS.get(country)
        if not slug:
            continue
        url = f"https://www.investing.com/rates-bonds/{slug}"
        try:
            html = _http_get(url, s)
            df_country = _parse_country_page(html, country)
            # garde uniquement le pays demandé (au cas où parsing récupère d'autres labels)
            df_country = df_country[df_country["country"].str.lower() == country.lower()]
            result_frames.append(df_country)
        except Exception:
            # on ignore en silence; on pourrait logger si besoin
            continue

    if not result_frames:
        raise RuntimeError("Aucune donnée de taux récupérée (world + fallback pays ont échoué).")

    df_all = pd.concat(result_frames, ignore_index=True)
    # dernier nettoyage/tri
    df_all = df_all.drop_duplicates(subset=["country", "tenor"]).reset_index(drop=True)
    df_all = df_all.sort_values(by=["country", "years"])

    return df_all
