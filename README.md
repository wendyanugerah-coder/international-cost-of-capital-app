International Cost of Capital App
A Streamlit project for comparing a project's annual nominal cost of equity, borrowing cost and weighted average cost of capital (WACC) in USD and a selected country's currency. Python 3.12; no local installation or API key is required for deployment.
Default settings
Industry: Software (System & Application)
Country: United States (USD)
Project tax: U.S. corporate tax rate
Equity risk premium: 6.5%
Debt financing: 30% of enterprise capital, D/(D+E)
Source data
The app requests current source data and caches it for 15 minutes (bond prices) or one hour (other sources). The sidebar Refresh source data button clears those caches. The source audit shows the observation or release date separately from retrieval time, the source URL, the fetched and used values, and whether the value comes from a live request, a dated reference fallback, or a manual override.
Damodaran US industry betas XLS: uses the Unlevered beta column, not levered beta or cash-adjusted beta. If the workbook fails, attempts the parallel HTML table.
Damodaran ratings and spreads: first Baa2/BBB row in the large non-financial service firms table.
OECD assignment report: uses the same OECD Corporate Tax Statistics underlying dataset, latest data explorer. The SDMX query selects the combined statutory general-government corporate income tax rate, and the latest nonmissing year for each country. Not just the central/federal tax rate.
Trading Economics government bonds: requests the published country-specific 10-year government bond pages linked from the bonds listing; uses the Actual yield or exact 10Y row, not forecasts. No API key or paid endpoints. Coverage, publication dates, website layout and access restrictions can vary; manual overrides are available for every input.
If source requests fail, dated reference values are provided only for the default software beta (1.23, January 2026), USD BBB spread (1.11%, January 2026), and US/Indonesia government yields (5.145% and 7.607%, November 13, 2026), checked on November 15, 2026. These are explicitly labeled as reference fallbacks and are NOT fresh quotes. The app does not invent missing tax or other bond data. Enter verified manual values if needed. If beta data are blocked, only the default reference industry is available until a successful fetch. The country list includes ISO countries and territories; not every country has a published 10-year bond or OECD tax observation. See the error details and verify the bond currency for countries with multiple currencies.
Model — class formulas
The model follows Sergio Rebelo, CasePacket2026 Part 9, slides 564–569 and 579–585. The formulas are displayed in the app and implemented in the single `calculate()` function. All rates are entered as percentages and converted to decimals for the math.
Let `d` be target debt share, `T` the one shared project tax rate (US or selected country), `ERP` the one equity risk premium, `y_US` and `y_F` the respective nominal 10-year government yields, and `s_US` the USD BBB spread.
```
D/E = d/(1-d)
beta_L = beta_U * (1 + (1-T)*D/E)
k_e_US = y_US + beta_L*ERP
k_e_F  = (1+k_e_US)*(1+y_F)/(1+y_US)-1
s_F_auto = s_US * (1+y_F)/(1+y_US)
k_d_US = y_US + s_US
k_d_F  = y_F + s_F (automatic or manually overridden)
WACC_c = (1-d)*k_e_c + d*k_d_c*(1-T)
```
The automatic foreign spread uses a gross-yield translation of the USD borrowing rate: `(1+k_d_US)*(1+y_F)/(1+y_US)-1-y_F`. This simplifies to the formula above. It is an assumption, not an observed foreign BBB spread. Local government yields are proxies, not necessarily default-free rates. No separate country-risk premium is added. The app reports both pre-tax and after-tax borrowing costs. It allows zero debt but not 100%, because D/E is undefined at 100%. The foreign equity rate uses the same gross-yield factor as the borrowing-rate conversion.
Deploy on Streamlit Community Cloud
Create a public GitHub repository at https://github.com/new named `international-cost-of-capital-app`.
Upload `app.py`, `requirements.txt`, and `README.md` at the top level. Commit the files to `main`.
Sign in at https://share.streamlit.io using GitHub. Create app > Yup, I have an app.
Select `YOUR-USERNAME/international-cost-of-capital-app`, branch `main`, main file `app.py`.
Choose Python 3.12 in Advanced settings, leave Secrets blank, and Deploy.
Save the public Streamlit URL. If data retrieval fails, click Refresh and inspect Data sources; use the exact source URLs to obtain verified manual inputs. For a startup error, inspect Manage app > Logs.
Optional local run:
```
python -m pip install -r requirements.txt
streamlit run app.py
```
Independent verification (illustrative manual inputs, not current market data)
Use the override controls and enter unlevered beta 1.20, both corporate taxes 25%, US yield 4%, local yield 6%, USD spread 1%, ERP 6.5%, and debt share 30%. Leave local spread override off. You can use Indonesia as the selected country to label the foreign results. All values below are hypothetical.
D/E = 0.30/0.70 = 0.428571429
Levered beta = 1.20 × [1 + 0.75 × 0.428571429] = 1.585714286
USD equity cost = 4 + 1.585714286 × 6.5 = 14.307142857%
Local equity cost = [(1 + 0.14307142857) × 1.06/1.04 − 1] × 100 = 16.505357143%
USD pre-tax debt cost = 5%; local automatic spread = 1 × 1.06/1.04 = 1.019230769%; local pre-tax debt cost = 7.019230769%
USD WACC = 0.70 × 14.307142857 + 0.30 × 5 × 0.75 = 11.140000%
Local WACC = 0.70 × 16.505357143 + 0.30 × 7.019230769 × 0.75 = 13.133076923%
Assignment checks:
Set both yields to 4% with local spread override off. Both currency results must be equal.
Set debt share to 0%. WACC equals cost of equity in each currency.
Restore debt share to 30%. Toggle local spread override and enter 2%. USD results must remain unchanged, while local borrowing cost and WACC change. Local equity cost stays unchanged.
Switch the tax selector from U.S. to selected country using different tax rates. The same selected project tax applies to both currencies.
Download project and all-industry CSVs. Download the source audit CSV to preserve data provenance.
The in-app verification checks supplement, not replace, the independent spreadsheet or calculator check you need for your submission. Save the app URL, repository URL, screenshots of AI prompts and responses, model/date, and your own calculation/checked design choice.
Lecture example test (slide 585)
Unlevered beta 0.80, tax 35%, ERP 6.5%, debt share 30%, USD yield 4%, Colombia yield 12%, USD spread 1.5%. Expected USD equity 10.6486%, COP equity 19.1600%, USD WACC 8.5265%, COP WACC 16.0670%.
