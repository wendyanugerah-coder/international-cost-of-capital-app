# International Cost of Capital App

This Streamlit application compares the cost of equity, cost of debt, and weighted average cost of capital (WACC) in USD and a selected country's currency.

## Features

- Industry and country selection
- Automatic data retrieval
- Manual input overrides
- Adjustable equity risk premium and debt financing
- US and foreign corporate tax selection
- Side-by-side cost of capital comparison
- All-industry comparison
- Downloadable CSV results
- Data refresh button

## Data Sources

- Damodaran US industry unlevered betas:
  https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls

- Damodaran BBB borrowing spread:
  https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html

- OECD corporate tax rates:
  https://www.oecd.org/

- Trading Economics government bond yields:
  https://tradingeconomics.com/bonds

## Default Settings

- Industry: Software (System & Application)
- Country: United States
- Corporate tax rate: US tax rate
- Equity risk premium: 6.5%
- Debt financing: 30%

## Formulas

D/E = Debt Share / (1 - Debt Share)

Levered Beta = Unlevered Beta * (1 + (1 - Tax Rate) * D/E)

Cost of Equity = Government Yield + Levered Beta * Equity Risk Premium

Cost of Debt = Government Yield + BBB Spread

Foreign Automatic BBB Spread = USD BBB Spread * (1 + Foreign Yield) / (1 + US Yield)

WACC = (1 - Debt Share) * Cost of Equity + Debt Share * Cost of Debt * (1 - Tax Rate)

Rates are converted to decimals before calculation.
The formulas, including the automatic foreign spread assumption, should be verified against the formulas provided in class.

## Verification

1. Equal government bond yields produce equal results when shared inputs are identical and the foreign spread override is off.
2. Zero debt financing makes WACC equal the cost of equity.
3. Overriding the foreign BBB spread leaves USD results unchanged.

## Deployment

1. Upload app.py, requirements.txt, and README.md to GitHub.
2. Open https://share.streamlit.io.
3. Select the repository and main branch.
4. Set the main file path to app.py.
5. Select Python 3.12.
6. Click Deploy.

## Data Limitations

Live market data may be temporarily unavailable.
Users can enter verified manual inputs when automatic data retrieval fails.
