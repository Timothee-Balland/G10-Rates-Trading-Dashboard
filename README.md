# 📊 G10 Rates Trading Dashboard

![GitHub last commit](https://img.shields.io/badge/last%20commit-October%202025-brightgreen)
![Python](https://img.shields.io/badge/python-v3.12%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green)

## 🚀 Overview

Interactive dashboard (Dash/Plotly) for **G10 rates** to spot **relative value** across govies and swaps.  
It fetches **live sovereign yield data from Investing.com** (scraped in real time), builds zero curves, and computes **Gov vs Bund**, **ASW (Gov − IRS)** and **IRS vs EUR IRS** spreads — refreshed automatically every **90 seconds**.  
The dashboard also provides **carry/roll**, **flies**, and a **hedging** pane proposing DV01-matched futures/IRS hedges.

## ⚙️ Features

- **Multi-curve plotting**: Par & Zero (bootstrapped) for bonds and swaps
- **Live G10 data feed**: government yields scraped from *Investing.com*  
- **Relative Value modes** (toggle in UI):
  - **Gov vs Bund** (sovereign spread)
  - **ASW (Gov − IRS)** per currency
  - **IRS vs EUR IRS** (cross-currency vs EUR)
- **RV helpers**: 2s10s/5s30s, **2-5-10 fly**, **G10 heatmap** vs Bund
- **Carry & Roll** table (1M / 3M approximations)
- **Hedging**: DV01 comparison, suggested sizing via futures or IRS
- **Theming**: Bloomberg-like dark theme (`bbg`) or light
- **Clean UX**: tabs (Overview, Spreads & Flies, Carry & Roll, G10 Matrix, Hedging)

## 🧮 Methodology

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

## 🗂️ App Structure (one-file launch)

- **Entry**: `Cash-Bond-Dash.py`  
- **Modules**: `modules/`  
  - `data_loader.py` – govies (G10)  
  - `swap_loader.py` – swaps (stub G10 incl. USD, CAD, GBP, EUR, JPY, AUD, NZD, SEK)  
  - `calculations.py` – bootstraps & RV math  
  - `analytics.py` – spreads/flies/carry helpers  
  - `plots.py` – Plotly figures (dark theme, tidy tooltips)
- **Assets**: `assets/`  
  - `theme.css` – Web Design

## 🧭 Quickstart

```bash
# 1️⃣ Clone the repo
git clone https://github.com/Timothee-Balland/G10-Rates-Trading-Dashboard.git
cd G10-Rates-Dashboard

# 2️⃣ Install dependencies (via Poetry)
poetry install

# 3️⃣ Run the app
poetry run python Cash-Bond-Dash.py
# → http://127.0.0.1:8050
```

## 📚 Dependencies

Core libraries:
- `dash` — UI framework for Python web apps  
- `plotly` — advanced charting (interactive yield/spread plots)  
- `pandas`, `numpy` — data manipulation and computation  
- *(optional)* `scipy` — for future yield-curve fitting extensions  

## 🧠 Notes

- Default refresh interval: **90 seconds** (`REFRESH_MS` in `Cash-Bond-Dash.py`)
- Data in real Time scrapped from **Investing.com**
- Swap curves are **static stubs** (for now) — ready to be replaced by live APIs or CSV inputs  
- Designed for **modularity**: each analytical block (bootstrapping, spreads, hedging) is fully independent  
- Default theme: **Bloomberg dark** (`bbg`), toggleable to light mode  
- All data and analytics are in **percent / basis points** (no decimals), to match trader convention  
- Built for **relative value**, **carry/roll**, and **hedging** exploration — not as a pricing engine  

---

## 🪄 Roadmap

- 🌍 Integration of **real market data** for govies and swaps  
- 📈 Add **historical spread tracking** and chart replay mode  
- 🧮 Extend to **credit spreads (CDS, SSA)** and **OIS basis**  
- 🧱 Implement **trade blotter** for position & PnL tracking  
- ⚡ Introduce **auto-refresh toggle** and update interval control  
- 📊 Add **export functions** (Excel / PNG / JSON)  
- 🧠 Build **RV scoring model** combining carry, roll, z-spreads & liquidity metrics  

---

## 📝 License

This project is released under the **MIT License** — free to use, modify, and distribute with attribution.  
© 2025 — Built with 💼, 📈, and ☕️ by a fixed income enthusiast.

---

**At a glance**
- 🔢 G10 sovereign & swap curves  
- 💹 Real-time relative value spreads  
- 🧩 Carry/Roll and fly analytics  
- 🧱 DV01-based hedging proposals  
- ⚙️ Built in Python with Dash & Plotly  
- 🌐 Inspired by Bloomberg-style RV tools  
