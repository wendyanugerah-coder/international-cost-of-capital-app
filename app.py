"""International cost of capital: rates stored as decimals only in calculate()."""
from datetime import datetime, timezone, date
from io import BytesIO, StringIO
import math
import re
import unicodedata
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
from bs4 import BeautifulSoup
import pycountry
from babel.numbers import get_territory_currencies
from babel import Locale

BETA = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
BETA_HTML = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/Betas.html'
RATINGS = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
OECD_REPORT = 'https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html'
OECD_DATA = 'https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/.A.CIT_C.ST..S13...'
BONDS = 'https://tradingeconomics.com/bonds'
DEFAULT = 'Software (System & Application)'

def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

def get(url, **kwargs):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; university finance project)', **kwargs.pop('headers', {})}
    r = requests.get(url, headers=headers, timeout=(8, 22), **kwargs)
    r.raise_for_status()
    return r

def norm(s):
    return re.sub(r'\s+', ' ', str(s).replace('\xa0',' ')).strip().lower()

def num(x):
    try:
        v = float(str(x).strip().replace('%','').replace(',','').replace('−','-'))
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None

def metadata(value, url, period, fetched=None, status='Live source'):
    return {'value': value, 'source': url, 'period': period, 'retrieved': fetched or (now() if value is not None or status=='Live source' else 'Not retrieved'), 'status': status}

def analysis_date(text):
    m = re.search(r'(?:as of|last updated in|last updated:)\s*([A-Za-z]+\s+(?:\d{1,2},?\s+)?20\d{2})', text, re.I)
    if m: return m.group(1)
    m = re.search(r'(?:date updated|date of analysis|last updated)\s*:?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/20\d{2})',text,re.I)
    return m.group(1) if m else 'Not stated by source'

def parse_beta_grid(grid):
    for i, row in grid.iterrows():
        labels = [norm(v) for v in row]
        if 'industry name' not in labels or 'unlevered beta' not in labels:
            continue
        a,b = labels.index('industry name'),labels.index('unlevered beta')
        out = {}
        for _, rec in grid.loc[i+1:].iterrows():
            name = str(rec.iloc[a]).strip()
            value = num(rec.iloc[b])
            if name and name.lower() != 'nan' and not name.lower().startswith('total market') and value is not None:
                out[name] = value
        if DEFAULT in out and len(out)>10:
            return out
    raise ValueError('Industry name / unlevered beta columns not found')

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_betas():
    errors=[]
    try:
        r=get(BETA)
        book=pd.read_excel(BytesIO(r.content), sheet_name=None, header=None, engine='xlrd')
        for grid in book.values():
            try:
                values=parse_beta_grid(grid)
                period=analysis_date(' '.join(str(x) for x in grid.head(10).to_numpy().ravel()))
                return values, metadata(None,BETA,period), ''
            except ValueError:
                continue
        raise ValueError('No usable industry sheet')
    except Exception as e:
        errors.append(f'XLS: {e}')
    try:
        r=get(BETA_HTML)
        soup=BeautifulSoup(r.text,'html.parser')
        for table in soup.find_all('table'):
            grid=pd.DataFrame([[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])] for tr in table.find_all('tr')])
            try:
                return parse_beta_grid(grid), metadata(None,BETA_HTML,analysis_date(soup.get_text(' ',strip=True))), '; '.join(errors)
            except ValueError:
                continue
        raise ValueError('No usable HTML industry table')
    except Exception as e:
        errors.append(f'HTML: {e}')
    return {DEFAULT:1.23}, metadata(None,BETA_HTML,'January 2026','2026-11-15 (reference check)','Dated reference fallback; only default industry'), '; '.join(errors)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_spread():
    try:
        soup=BeautifulSoup(get(RATINGS).text,'html.parser')
        for table in soup.find_all('table'):
            if 'large non-financial' not in norm(table.get_text(' ',strip=True)):
                continue
            for row in table.find_all('tr'):
                cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'])]
                for i, cell in enumerate(cells[:-1]):
                    if re.sub(r'\s','',cell).upper()=='BAA2/BBB':
                        v=num(cells[i+1])
                        if v is not None and v>=0:
                            return metadata(v,RATINGS,analysis_date(soup.get_text(' ',strip=True))), ''
        raise ValueError('Large non-financial Baa2/BBB row not found')
    except Exception as e:
        return metadata(1.11,RATINGS,'January 2026','2026-11-15 (reference check)','Dated reference fallback'), str(e)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_taxes():
    try:
        params={'startPeriod':str(date.today().year-4),'dimensionAtObservation':'AllDimensions'}
        try:
            r=get(OECD_DATA,params=params,headers={'Accept':'text/csv'})
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code not in (400,406,415): raise
            r=get(OECD_DATA,params=params,headers={'Accept':'application/vnd.sdmx.data+csv;version=2.0.0'})
        df=pd.read_csv(StringIO(r.text))
        df.columns=[str(c).strip() for c in df.columns]
        required={'REF_AREA','TIME_PERIOD','OBS_VALUE'}
        if not required.issubset(df.columns):
            raise ValueError(f'Unexpected OECD columns: {list(df.columns)}')
        # The URL already selects statutory combined general-government rates.
        # When these dimensions appear, verify them too.
        for col,code in [('MEASURE','CIT_C'),('TARGETING','ST'),('SECTOR','S13'),('INSTITUTIONAL_SECTOR','S13')]:
            if col in df.columns:
                df=df[df[col].astype(str).eq(code)]
        df['OBS_VALUE']=pd.to_numeric(df['OBS_VALUE'],errors='coerce')
        df['TIME_PERIOD']=pd.to_numeric(df['TIME_PERIOD'],errors='coerce')
        df=df[df['OBS_VALUE'].between(0,100)&df['TIME_PERIOD'].le(date.today().year)].dropna(subset=['TIME_PERIOD'])
        out={}
        for code, group in df.groupby('REF_AREA'):
            latest=group[group.TIME_PERIOD==group.TIME_PERIOD.max()]
            if latest.OBS_VALUE.nunique()!=1:
                continue
            out[str(code)]=metadata(float(latest.OBS_VALUE.iloc[0]),OECD_DATA,str(int(latest.TIME_PERIOD.iloc[0])))
        if 'USA' not in out:
            raise ValueError('No unambiguous US combined statutory rate')
        return out,''
    except Exception as e:
        return {},str(e)

ALIASES={'USA':'United States','GBR':'United Kingdom','KOR':'South Korea','PRK':'North Korea','RUS':'Russia','VNM':'Vietnam','CZE':'Czech Republic','TUR':'Turkey','IRN':'Iran','TWN':'Taiwan','HKG':'Hong Kong','MAC':'Macao','BOL':'Bolivia','VEN':'Venezuela','TZA':'Tanzania','MDA':'Moldova','LAO':'Laos','SYR':'Syria','BRN':'Brunei','PSE':'Palestine','COD':'Democratic Republic of the Congo','COG':'Congo','CIV':'Ivory Coast','SVK':'Slovakia','MKD':'North Macedonia','CPV':'Cape Verde','SWZ':'Eswatini','MMR':'Myanmar'}

def countries():
    names=Locale('en').territories
    return {c.alpha_3:(ALIASES.get(c.alpha_3,names.get(c.alpha_2,c.name)),c.alpha_2) for c in pycountry.countries}

COUNTRIES=countries()

def slug_for(code):
    name=COUNTRIES[code][0]
    name=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')

def bond_url(code):
    return f'https://tradingeconomics.com/{slug_for(code)}/government-bond-yield'

@st.cache_data(ttl=900, show_spinner=False)
def fetch_bond_index():
    try:
        soup=BeautifulSoup(get(BONDS).text,'html.parser')
        out={}
        for a in soup.select('a[href*="/government-bond-yield"]'):
            path=a.get('href','')
            m=re.search(r'/([^/]+)/government-bond-yield(?:[?#]|$)',path)
            if m:
                out[m.group(1)]=f'https://tradingeconomics.com/{m.group(1)}/government-bond-yield'
        return out,''
    except Exception as e:
        return {},str(e)

def parse_yield_html(html, url):
    soup=BeautifulSoup(html,'html.parser')
    heading=soup.find('h1')
    if not heading or not re.search(r'10\s*[- ]?\s*(?:year|y\b)',heading.get_text(' ',strip=True),re.I):
        raise ValueError('10-year bond page heading not found')
    text=soup.get_text(' ',strip=True)
    # Prefer the clearly labeled Actual value above the daily change, never a forecast.
    m=re.search(r'\bActual\s+(-?\d+(?:\.\d+)?)\s*%?\s+Daily Change\b',text,re.I)
    if not m:
        # Country page has a maturity-specific bond table; exact 10Y row only.
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells=[c.get_text(' ',strip=True) for c in row.find_all(['td','th'])]
                if len(cells)>=2 and re.search(r'\b10Y$',cells[0],re.I) and num(cells[1]) is not None:
                    value=num(cells[1]); break
            else:
                continue
            break
        else:
            raise ValueError('Current Actual yield or exact 10Y row not found')
    else:
        value=num(m.group(1))
    if value is None or value<=-100:
        raise ValueError('Invalid yield')
    # The publisher may give a quote date or only a page update date.
    m=re.search(r'\byield\b.{0,140}?\bon\s+([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})',text,re.I)
    if m:
        period=m.group(1)+' (quote date)'
    else:
        m=re.search(r'last updated on\s+([A-Za-z]+\s+\d{1,2}\s+(?:of\s+)?20\d{2})',text,re.I)
        period=m.group(1)+' (page update; quote date not stated)' if m else 'Quote date not stated'
    return metadata(value,url,period)

@st.cache_data(ttl=900, show_spinner=False)
def fetch_yield(code, url):
    try:
        return parse_yield_html(get(url).text,url),''
    except Exception as e:
        # A small dated reference snapshot is never represented as a live quote.
        snapshots={'USA':5.1450,'IDN':7.6070}
        if code in snapshots:
            return metadata(snapshots[code],url,'2026-11-13 (quote date)','2026-11-15 (reference check)','Dated reference fallback'), str(e)
        return metadata(None,url,'Unavailable',status='Unavailable'),str(e)

def calculate(beta_u, tax_pct, erp_pct, debt_pct, us_y_pct, local_y_pct, spread_pct, foreign_override_pct=None):
    """One project; percent inputs, percent outputs for all rates."""
    inputs=[beta_u,tax_pct,erp_pct,debt_pct,us_y_pct,local_y_pct,spread_pct]
    if foreign_override_pct is not None: inputs.append(foreign_override_pct)
    if not all(math.isfinite(v) for v in inputs): raise ValueError('All inputs must be finite')
    if not 0<=tax_pct<=100 or not 0<=debt_pct<100 or min(us_y_pct,local_y_pct)<=-100 or spread_pct<0 or (foreign_override_pct is not None and foreign_override_pct<0):
        raise ValueError('Invalid tax, debt share, yield or spread')
    t,e,d,yu,yf,s=[x/100 for x in (tax_pct,erp_pct,debt_pct,us_y_pct,local_y_pct,spread_pct)]
    beta_l=beta_u*(1+(1-t)*d/(1-d))
    # Provisional currency translation of the USD debt gross return.
    # The assignment references separate class formulas; verify this choice.
    auto=s*(1+yf)/(1+yu)
    sf=auto if foreign_override_pct is None else foreign_override_pct/100
    keu,kef=yu+beta_l*e,yf+beta_l*e
    kdu,kdf=yu+s,yf+sf
    wu,wf=(1-d)*keu+d*kdu*(1-t),(1-d)*kef+d*kdf*(1-t)
    return {'levered_beta':beta_l,'foreign_spread_auto_pct':100*auto,'foreign_spread_used_pct':100*sf,'usd_equity_pct':100*keu,'local_equity_pct':100*kef,'usd_debt_pct':100*kdu,'local_debt_pct':100*kdf,'usd_after_tax_debt_pct':100*kdu*(1-t),'local_after_tax_debt_pct':100*kdf*(1-t),'usd_wacc_pct':100*wu,'local_wacc_pct':100*wf}

def manual(label, rec, key, minimum=None, maximum=None, step=0.01, fmt='%.4f'):
    source_val=rec.get('value') if rec else None
    override=st.checkbox('Override '+label,value=source_val is None,key=key+'_toggle')
    if source_val is None: st.caption('No source value available; enable override and enter a verified input.')
    else: st.caption(f'Source value: {source_val:.6g} | {rec["period"]} | {rec["status"]}')
    if override:
        val=st.number_input(label,min_value=minimum,max_value=maximum,value=float(source_val) if source_val is not None else None,step=step,format=fmt,key=key+'_value',placeholder='Enter value')
        return val,'Manual override'
    return source_val,rec['status'] if rec else 'Unavailable'

def run():
    st.set_page_config(page_title='International Cost of Capital',page_icon='📊',layout='wide')
    st.title('International Cost of Capital')
    st.caption('Compare the same project in USD and the selected country’s currency.')
    if st.sidebar.button('Refresh source data',type='primary'):
        for f in (fetch_betas,fetch_spread,fetch_taxes,fetch_bond_index,fetch_yield): f.clear()
        st.rerun()
    with st.spinner('Retrieving Damodaran, OECD and Trading Economics data…'):
        betas,beta_info,beta_err=fetch_betas()
        spread_info,spread_err=fetch_spread()
        taxes,tax_err=fetch_taxes()
        bond_index,bond_err=fetch_bond_index()
    st.sidebar.header('Project settings')
    inds=sorted(betas)
    industry=st.sidebar.selectbox('Industry',inds,index=inds.index(DEFAULT) if DEFAULT in inds else 0)
    codes=sorted(COUNTRIES,key=lambda c:COUNTRIES[c][0])
    code=st.sidebar.selectbox('Target country',codes,index=codes.index('USA'),format_func=lambda c:f'{COUNTRIES[c][0]} ({c})')
    country=COUNTRIES[code][0]
    currencies=get_territory_currencies(COUNTRIES[code][1],start_date=date.today(),end_date=date.today())
    currency=st.sidebar.selectbox('Target currency',currencies) if currencies else st.sidebar.text_input('Target currency code',value='Local currency')
    if len(currencies)>1: st.sidebar.caption('Check that the government yield is denominated in the currency selected.')
    erp=st.sidebar.number_input('Equity risk premium (%)',min_value=0.0,value=6.5,step=0.1)
    debt=st.sidebar.slider('Target debt share D/(D+E) (%)',0.0,99.0,30.0,0.5)
    tax_choice=st.sidebar.radio('Project corporate tax rate (both currencies)',['U.S.','Selected country'],index=0)
    with st.spinner('Retrieving 10-year yields…'):
        us_url=bond_index.get(slug_for('USA'),bond_url('USA'))
        local_url=bond_index.get(slug_for(code),bond_url(code))
        us_y_info,us_err=fetch_yield('USA',us_url)
        local_y_info,local_err=(us_y_info,us_err) if code=='USA' else fetch_yield(code,local_url)
    if code=='USA': local_y_info=us_y_info
    us_tax=taxes.get('USA',metadata(None,OECD_DATA,'Unavailable',status='Unavailable'))
    local_tax=taxes.get(code,metadata(None,OECD_DATA,'Unavailable',status='Unavailable'))
    beta_rec={**beta_info,'value':betas[industry]}
    st.info('Class formulas were not supplied with the assignment. The displayed model uses Hamada beta, CAPM, and a gross-yield currency conversion for the automatic local BBB spread. Verify these against your lecture notes before submitting.')
    if any([beta_err,spread_err,tax_err,bond_err,us_err,local_err]):
        st.warning('One or more live requests failed or used a fallback. Inspect Data sources and use verified manual inputs if needed. Dated reference values are not live quotes.')
    st.subheader('Source inputs and manual overrides')
    a,b,c=st.columns(3)
    with a:
        bu,bu_status=manual('Unlevered beta',beta_rec,'beta_'+industry,step=.01)
        sp,sp_status=manual('USD BBB borrowing spread (%)',spread_info,'spread',minimum=0.0)
    with b:
        tu,tu_status=manual('U.S. corporate tax (%)',us_tax,'tax_USA',minimum=0.0,maximum=100.0)
        if code=='USA':
            tf,tf_status=tu,tu_status
            st.caption('Selected-country tax equals U.S. tax.')
        else: tf,tf_status=manual('Target-country corporate tax (%)',local_tax,'tax_'+code,minimum=0.0,maximum=100.0)
    with c:
        yu,yu_status=manual('U.S. 10-year yield (%)',us_y_info,'yield_USA',minimum=-99.0)
        # Independent local override is allowed even for USA for the verification scenario.
        yf,yf_status=manual('Target-country 10-year yield (%)',({**local_y_info,'value':yu} if code=='USA' else local_y_info),'yield_local_'+code,minimum=-99.0)
        if code=='USA' and yf_status!='Manual override': yf_status=yu_status
    project_tax=tu if tax_choice=='U.S.' else tf
    project_status=tu_status if tax_choice=='U.S.' else tf_status
    auto=sp*(100+yf)/(100+yu) if None not in (sp,yu,yf) else None
    st.subheader('Target-currency BBB spread')
    st.write(f'Automatic spread: **{auto:.6f}%**' if auto is not None else 'Automatic spread unavailable until required inputs are provided.')
    override=st.checkbox('Override target-currency BBB spread',key='foreign_spread_'+code)
    sf=st.number_input('Manual target BBB spread (%)',min_value=0.0,value=float(auto) if auto is not None else None,step=.01,format='%.6f',key='foreign_value_'+code) if override else None
    st.caption('Automatic spread = USD BBB spread × (1 + local yield)/(1 + USD yield), with yields in decimal form. Local spread override affects only local debt and WACC.')
    with st.expander('Data sources, dates and retrieval details',expanded=True):
        recs=[('Unlevered beta',beta_rec,bu,bu_status),('USD BBB spread (%)',spread_info,sp,sp_status),('US corporate tax (%)',us_tax,tu,tu_status),('Target corporate tax (%)',local_tax,tf,tf_status),('US 10-year yield (%)',us_y_info,yu,yu_status),('Target 10-year yield (%)',local_y_info,yf,yf_status)]
        source_rows=[{'Input':name,'Source value':rec['value'],'Used value':v,'Used status':status,'Source status':rec['status'],'Observation / release':rec['period'],'Retrieved (UTC)':rec['retrieved'],'URL':rec['source']} for name,rec,v,status in recs]
        st.dataframe(pd.DataFrame(source_rows),hide_index=True,use_container_width=True)
        st.markdown(f'[Damodaran beta workbook]({BETA}) · [Damodaran ratings]({RATINGS}) · [OECD assignment report]({OECD_REPORT}) · [Trading Economics bonds]({BONDS})')
        for name,err in [('Beta',beta_err),('BBB spread',spread_err),('OECD',tax_err),('Bond list',bond_err),('US yield',us_err),('Target yield',local_err)]:
            if err: st.caption(f'{name}: {err}')
        st.download_button('Download source audit CSV',pd.DataFrame(source_rows).to_csv(index=False),'source_audit.csv','text/csv')
    if None in (bu,sp,project_tax,yu,yf) or (override and sf is None):
        st.warning('Enter missing required inputs above to calculate results. No missing rate is silently replaced by zero.')
        return
    result=calculate(bu,project_tax,erp,debt,yu,yf,sp,sf)
    st.subheader('Cost of capital comparison')
    st.write(f'{industry} · United States vs {country} · Shared tax {project_tax:.4f}% · Debt share {debt:.1f}% · Levered beta {result["levered_beta"]:.6f}')
    measures=[('Cost of equity','equity'),('Pre-tax cost of debt','debt'),('After-tax cost of debt','after_tax_debt'),('WACC','wacc')]
    rows=[]
    l,r=st.columns(2)
    for col,title,prefix in [(l,'USD','usd'),(r,f'{currency} · {country}','local')]:
        with col:
            st.markdown('### '+title)
            for label,k in measures: st.metric(label,f'{result[prefix+"_"+k+"_pct"]:.4f}%')
    for label,k in measures: rows.append({'Measure':label,'USD (%)':result['usd_'+k+'_pct'],f'Target {currency} (%)':result['local_'+k+'_pct']})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    with st.expander('Formulas and assumptions',expanded=True):
        st.latex(r'\beta_L=\beta_U[1+(1-T)D/E],\quad D/E=d/(1-d)')
        st.latex(r'k_{e,c}=y_c+\beta_L ERP,\quad k_{d,c}=y_c+s_c')
        st.latex(r's_f=s_{USD}\frac{1+y_f}{1+y_{USD}},\quad WACC_c=(1-d)k_{e,c}+d k_{d,c}(1-T)')
        st.write('Rates are nominal annual rates; the same project tax, financing weights and ERP apply to both currencies. The government yield is a proxy, not necessarily a default-free rate. The spread conversion assumes the gross government-yield ratio proxies currency adjustment. It is not a directly observed local BBB spread. No separate country-risk premium is added. Compare the provisional formulas with class notes.')
    base={'industry':industry,'country':country,'country_iso3':code,'target_currency':currency,'unlevered_beta':bu,'tax_pct':project_tax,'tax_choice':tax_choice,'tax_status':project_status,'erp_pct':erp,'debt_share_pct':debt,'us_yield_pct':yu,'local_yield_pct':yf,'usd_spread_pct':sp,'foreign_spread_override':override,'beta_status':bu_status,'us_yield_status':yu_status,'local_yield_status':yf_status,'usd_spread_status':sp_status,'calculated_utc':now()}
    st.download_button('Download selected project CSV',pd.DataFrame([{**base,**result}]).to_csv(index=False),'project_cost_of_capital.csv','text/csv')
    st.subheader('All-industry comparison')
    st.caption('Each industry uses its own source unlevered beta and the same project assumptions. A manual beta applies only to the selected industry in this table.')
    allrows=[]
    for name,source_beta in sorted(betas.items()):
        used=bu if name==industry else source_beta
        calc=calculate(used,project_tax,erp,debt,yu,yf,sp,sf)
        allrows.append({**base,'industry':name,'unlevered_beta':used,'beta_status':bu_status if name==industry else beta_info['status'],**calc})
    df=pd.DataFrame(allrows)
    if len(df)<=1: st.warning('Only the reference software industry is available: retry the live beta download for the full comparison.')
    st.dataframe(df[['industry','unlevered_beta','levered_beta','usd_equity_pct','local_equity_pct','usd_debt_pct','local_debt_pct','usd_wacc_pct','local_wacc_pct']],hide_index=True,use_container_width=True)
    chart=df[['industry','usd_wacc_pct','local_wacc_pct']].rename(columns={'usd_wacc_pct':'USD','local_wacc_pct':f'Target {currency}'}).melt('industry',var_name='Currency',value_name='WACC (%)')
    st.plotly_chart(px.bar(chart,x='industry',y='WACC (%)',color='Currency',barmode='group').update_layout(xaxis_tickangle=-60,height=500),use_container_width=True)
    st.download_button('Download all industries CSV',df.to_csv(index=False),'all_industries_cost_of_capital.csv','text/csv')
    with st.expander('Verification checks'):
        equal=calculate(bu,project_tax,erp,debt,yu,yu,sp)
        zero=calculate(bu,project_tax,erp,0,yu,yf,sp,sf)
        altered=calculate(bu,project_tax,erp,debt,yu,yf,sp,(auto or 0)+1)
        checks={'Equal yields and auto spread: USD and target costs match':all(math.isclose(equal['usd_'+k+'_pct'],equal['local_'+k+'_pct'],abs_tol=1e-10) for _,k in measures),'Zero debt: WACC equals equity cost in both currencies':all(math.isclose(zero[p+'_wacc_pct'],zero[p+'_equity_pct'],abs_tol=1e-10) for p in ['usd','local']),'Local spread override leaves USD costs unchanged':all(math.isclose(result['usd_'+k+'_pct'],altered['usd_'+k+'_pct'],abs_tol=1e-10) for _,k in measures)}
        for label,passed in checks.items(): st.write(('PASS — ' if passed else 'FAIL — ')+label)
        st.caption('These automated checks supplement, not replace, your independent spreadsheet/calculator verification.')

if __name__=='__main__':
    run()
