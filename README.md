# 💹 G10 Rates Trading Dashboard

[![GitHub last commit](https://img.shields.io/github/last-commit/<your-user>/g10-rates-dashboard?color=orange)](https://github.com/<your-user>/g10-rates-dashboard/commits/main)
[![Language](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Dash-Plotly-success?logo=plotly)](https://dash.plotly.com/)
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

> **Interactive trading dashboard for G10 government bonds and interest rate swaps.**
>
> Visualize yield curves, spreads, butterflies, carry/roll, and hedging ideas in a single modern Dash app.

---

## 🚀 Features

### 🧭 Overview
- Par & zero-coupon yield curves for all G10 countries  
- Spreads vs benchmark (e.g., France vs Germany Bunds)  
- Live-updating data tables with sorting/filtering  

### 🔄 Spreads & Flies
- Two-leg spreads (2s10s, 5s30s, 2s5s)  
- 2s/5s/10s butterfly indicator  
- Dynamic refresh every 90 s  

### 💰 Carry & Roll
- 1M / 3M carry and roll-down calculations  
- Sortable by highest carry opportunities  

### 🌍 G10 Matrix
- Cross-country spread heatmap (2Y, 5Y, 10Y, 30Y)  
- Quick visual comparison of relative value  

### 🧮 Hedging
- DV01 matching for futures or IRS hedges  
- Auto-sizing proposals for fixed-income portfolios  

---

## 🏗️ Project Structure

📂 Cash-Bond-Dashboard-Live
│
├── Cash-Bond-Dash.py # Main Dash application
│
├── modules/
│ ├── data_loader.py # Fetches government yield data
│ ├── swap_loader.py # Loads swap curves (stub → API later)
│ ├── calculations.py # Bootstrapping, spreads, ASW, zero-curves
│ ├── plots.py # Plotly figure builders
│ ├── analytics.py # Carry, roll, matrix, flies
│ └── hedging.py # DV01 & hedge sizing logic
│
├── assets/ # CSS styles (themes)
├── README.md
└── requirements.txt or pyproject.toml

---

## ⚙️ Installation

```bash
# Clone the repo
git clone https://github.com/<your-user>/g10-rates-dashboard.git
cd g10-rates-dashboard

# (Optional) create virtual environment
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate.bat   # Windows

# Install dependencies
pip install -r requirements.txt
If using Poetry:
poetry install
poetry run python Cash-Bond-Dash.py
▶️ Run the App
python Cash-Bond-Dash.py
Then open your browser to:
👉 http://127.0.0.1:8050
🌈 Themes
🟠 Bloomberg Dark (default)
⚪ Plotly White (light mode)
Switch instantly via the top toolbar dropdown.
📊 Next Steps
 Replace stubs with live feeds (Bloomberg / Refinitiv / Eikon / Quandl)
 Add historical spread time series
 Extend hedging logic with futures margin analytics
 Deploy online (Render / Heroku / Azure App Service)
🧠 Credits
Developed by Nicolas Balland
Focus: G10 Rates · Relative Value · Fixed-Income Trading Analytics
📜 License
This project is released under the MIT License.
See LICENSE for details.
