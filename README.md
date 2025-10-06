filename: README.md
content: |-
  # 💹 G10 Rates Trading Dashboard

  [![GitHub last commit](https://img.shields.io/github/last-commit/<your-user>/g10-rates-dashboard?color=orange&label=Last%20Commit)](https://github.com/Timothee-Balland/G10-Rates-Trading-Dashboard/commits/main)
  ![Language](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
  ![Framework](https://img.shields.io/badge/Dash-Plotly-success?logo=plotly)
  [![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

  Interactive trading dashboard for **G10 government bonds** and **interest rate swaps**.  
  Visualize yield curves, spreads, butterflies, carry/roll, and hedging ideas in a single modern Dash app.

  ## 🚀 Features
  - **Overview**: Par & zero-coupon curves, spreads vs Bund, sortable table  
  - **Spreads & Flies**: 2s10s, 5s30s, 2s5s, 2/5/10 butterfly  
  - **Carry & Roll**: 1M / 3M carry & roll-down approximations  
  - **G10 Matrix**: Cross-country spread heatmap (2Y, 5Y, 10Y, 30Y)  
  - **Hedging**: DV01 matching and sizing (futures / IRS)

  ## 🏗️ Project Structure
      📂 Cash-Bond-Dashboard-Live
      │
      ├── Cash-Bond-Dash.py              # Main Dash application
      │
      ├── modules/
      │   ├── data_loader.py             # Fetches government yield data
      │   ├── swap_loader.py             # Loads swap curves (stub → API later)
      │   ├── calculations.py            # Bootstrapping, spreads, ASW, zero-curves
      │   ├── plots.py                   # Plotly figure builders
      │   ├── analytics.py               # Carry, roll, matrix, flies
      │   └── hedging.py                 # DV01 & hedge sizing logic
      │
      ├── assets/                        # CSS themes
      ├── README.md
      └── requirements.txt or pyproject.toml

  ## ⚙️ Installation
  ```bash
  # Clone the repo
  git clone https://github.com/<your-user>/g10-rates-dashboard.git
  cd g10-rates-dashboard

  # (Optional) create a virtual environment
  python3 -m venv .venv
  source .venv/bin/activate        # macOS / Linux
  # .venv\Scripts\activate.bat     # Windows

  # Install dependencies
  pip install -r requirements.txt
