# G10 Rates Trading Dashboard

![GitHub last commit](https://img.shields.io/badge/last%20commit-October%202025-brightgreen)
![Python](https://img.shields.io/badge/python-v3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

Interactive dashboard (Dash/Plotly) for **G10 rates** to spot **relative value** across govies and swaps.  
It fetches sovereign yield curves, builds zero curves, computes **Gov vs Bund**, **ASW (Gov − IRS)** and **IRS vs EUR IRS** spreads, plus quick **carry/roll** and **flies**. A **hedging** pane proposes DV01-matched futures/IRS hedges.

## Features

- **Multi-curve plotting**: Par & Zero (bootstrapped) for bonds and swaps  
- **Relative Value modes** (toggle in UI):
  - **Gov vs Bund** (sovereign spread)
  - **ASW (Gov − IRS)** per currency
  - **IRS vs EUR IRS** (cross-currency vs EUR)
- **RV helpers**: 2s10s/5s30s, **2-5-10 fly**, **G10 heatmap** vs Bund
- **Carry & Roll** table (1M / 3M approximations)
- **Hedging**: DV01 comparison, suggested sizing via futures or IRS
- **Theming**: Bloomberg-like dark theme (`bbg`) or light
- **Clean UX**: tabs (Overview, Spreads & Flies, Carry & Roll, G10 Matrix, Hedging)

## Methodology

- **Bootstrapping**  
  - Bonds: `bootstrap_zero_from_par` (compounding selectable, freq configurable)  
  - Swaps: `bootstrap_zero_from_par_swaps` (fixed-leg frequency by currency)
- **Relative Value**  
  - `add_spread_vs_ref` (Gov vs Bund)  
  - `asw_spread` (Gov − IRS) with robust **interpolation on swap grid**  
  - `swap_spread_vs_ref` (IRS − EUR IRS) with strict/nearest alignment
- **Analytics**  
  - `two_leg_spreads` (2s10s, 5s30s…), `fly_2_5_10`, `carry_roll_table`  
  - `g10_matrix_spreads_vs_ref` (wide → heatmap with zmid=0)

## App Structure (one-file launch)

- **Entry**: `Cash-Bond-Dash.py`  
- **Modules**: `modules/`  
  - `data_loader.py` – govies (G10)  
  - `swap_loader.py` – swaps (stub G10 incl. USD, CAD, GBP, EUR, JPY, AUD, NZD, SEK)  
  - `calculations.py` – bootstraps & RV math  
  - `analytics.py` – spreads/flies/carry helpers  
  - `plots.py` – Plotly figures (dark theme, tidy tooltips)

## Quickstart

```bash
# 1) Clone
git clone https://github.com/<your-user>/g10-rates-dashboard.git
cd g10-rates-dashboard

# 2) (Option A) venv + pip
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) (Option B) Poetry
poetry install
poetry run python Cash-Bond-Dash.py

# 3) Run (pip/venv)
python Cash-Bond-Dash.py
# → http://127.0.0.1:8050
Single script run: python Cash-Bond-Dash.py
Dependencies
dash, plotly
pandas, numpy
(optionnel) scipy (si tu ajoutes des fits NSS ensuite)
(Ajoute un requirements.txt si besoin : dash plotly pandas numpy)
Data Model (columns)
Bonds: country, tenor, years, yield, (prev, high, low, chg, chg %, time)
Swaps: currency, tenor, years, rate
Spreads output: tenor, years, spread_bp, country
Usage Tips
Change Instrument (Bonds/Swaps), Spread mode, Courbe (Par/Zéro) & Pays via top toolbar.
For EUR countries, IRS vs EUR IRS ≈ 0 by design. Use ASW or Gov vs Bund instead.
Heatmap is centered (zmid=0) for instant rich/cheap read.
Roadmap
Real-time market data adapters (govies & swaps)
OIS/€STR basis option (Gov − OIS, IRS − OIS)
Trade idea snapshots (bookmark RV states)
Backtest: carry/roll P&L vs realized
License
MIT — see LICENSE.
