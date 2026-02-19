import streamlit as st
import yfinance as yf
import pandas as pd
import time
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="TradeBot AI — Options Scanner", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #c8d8e8; }
    h1, h2, h3 { color: #00ff88 !important; }
    div[data-testid="stMetricValue"] { color: #00ff88 !important; font-size: 28px !important; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("# 📊 TradeBot AI — Options Scanner")
st.markdown("**Unusual Activity · Greeks · OI · Volumen · IV%** — Powered by yfinance")
st.markdown("---")

@st.cache_data(ttl=300)
def get_stock_info(ticker):
    for i in range(3):
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            precio = (info.get('currentPrice') or info.get('regularMarketPrice') or info.get('ask') or info.get('bid', 0))
            cambio = info.get('regularMarketChangePercent', 0)
            nombre = info.get('shortName', ticker)
            exps   = stock.options
            return stock, precio, cambio, nombre, list(exps) if exps else []
        except:
            if i < 2: time.sleep(2)
    return None, 0, 0, ticker, []

@st.cache_data(ttl=300)
def get_chain(ticker, exp, tipo):
    for i in range(3):
        try:
            stock = yf.Ticker(ticker)
            chain = stock.option_chain(exp)
            return chain.calls.copy() if tipo == 'calls' else chain.puts.copy()
        except:
            if i < 2: time.sleep(2)
    return None

col1, col2, col3 = st.columns([2,1,1])
with col1:
    ticker = st.text_input("🔍 Ticker", value="AAPL", placeholder="AAPL, TSLA, ONDS...").upper().strip()
with col2:
    tipo = st.selectbox("Tipo", ["calls","puts"])
with col3:
    min_vol = st.number_input("Vol mínimo unusual", min_value=10, value=100, step=10)

if st.button("▶️ Analizar", use_container_width=True, type="primary"):
    with st.spinner(f"Conectando con Yahoo Finance..."):
        stock, precio, cambio, nombre, exps = get_stock_info(ticker)

    if not stock or not exps:
        st.error(f"❌ No se pudo obtener datos de {ticker}.")
        st.warning("⏳ Yahoo Finance tiene límite de peticiones. Espera 1-2 minutos e intenta de nuevo.")
        st.info("💡 Tip: Prueba primero con AAPL o SPY para verificar que funciona.")
        st.stop()

    st.markdown(f"### {nombre} ({ticker})")
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("💲 Precio", f"${precio:.2f}", f"{cambio:+.2f}%")
    m2.metric("📅 Expiraciones", len(exps))
    m3.metric("📊 Tipo", tipo.upper())
    m4.metric("⏰ Delay", "~15 min")
    st.markdown("---")

    exp = st.selectbox("📅 Expiración", exps)

    with st.spinner("Cargando cadena de opciones..."):
        time.sleep(0.5)
        df_raw = get_chain(ticker, exp, tipo)

    if df_raw is None:
        st.error("❌ Error cargando opciones. Espera 2 minutos e intenta de nuevo.")
        st.stop()

    df = df_raw[['strike','bid','ask','volume','openInterest','impliedVolatility']].copy()
    df.columns = ['Strike','Bid','Ask','Volumen','OI','IV%']
    tiene_greeks = all(g in df_raw.columns for g in ['delta','gamma','theta','vega'])
    for g,col in [('delta','Delta'),('gamma','Gamma'),('theta','Theta'),('vega','Vega')]:
        df[col] = df_raw[g].round(4) if g in df_raw.columns else None
    df['IV%']     = (df['IV%']*100).round(1)
    df['Bid']     = df['Bid'].fillna(0).round(2)
    df['Ask']     = df['Ask'].fillna(0).round(2)
    df['OI']      = df['OI'].fillna(0).astype(int)
    df['Volumen'] = df['Volumen'].fillna(0).astype(int)
    df['Estado']  = df['Strike'].apply(lambda s: '✅ ITM' if s < precio else '⭕ OTM')
    df['Vol/OI']  = df.apply(lambda r: f"{r['Volumen']/r['OI']:.1f}x" if r['OI']>0 else 'NEW', axis=1)
    df['🔥']      = df.apply(lambda r: '🔥 UNUSUAL' if (r['Volumen']>r['OI']*1.5 and r['Volumen']>min_vol) else '', axis=1)
    unu = len(df[df['🔥']=='🔥 UNUSUAL'])

    tab1,tab2 = st.tabs([f"📋 Cadena ({len(df)})", f"🔥 Unusual ({unu})"])
    with tab1:
        if not tiene_greeks:
            st.warning(f"⚠️ Greeks no disponibles para {ticker} (normal en small caps)")
        cols = ['Strike','Estado','Delta','Gamma','Theta','Vega','IV%','Bid','Ask','OI','Volumen','Vol/OI','🔥'] if tiene_greeks else ['Strike','Estado','IV%','Bid','Ask','OI','Volumen','Vol/OI','🔥']
        def color_rows(row):
            if row.get('🔥')=='🔥 UNUSUAL': return ['background-color:#2a1800;color:#ffd700']*len(row)
            elif row.get('Estado')=='✅ ITM': return ['background-color:#0a1f0a;color:#00ff88']*len(row)
            return ['']*len(row)
        st.dataframe(df[cols].style.apply(color_rows,axis=1), use_container_width=True, height=500)
    with tab2:
        df_u = df[df['🔥']=='🔥 UNUSUAL']
        if df_u.empty:
            st.info("📊 Sin unusual activity. Prueba otra fecha o reduce el volumen mínimo.")
        else:
            st.success(f"🔥 {len(df_u)} contratos con flujo inusual")
            for _,row in df_u.iterrows():
                st.markdown(f"**Strike ${row['Strike']}** — {row['Estado']} | OI: **{row['OI']:,}** | Vol: **{row['Volumen']:,}** | Vol/OI: **{row['Vol/OI']}** | IV: **{row['IV%']}%**")
                st.divider()

    st.markdown("---")
    st.markdown("### 🔥 Unusual Activity — Todas las expiraciones")
    with st.spinner("Escaneando... (30 segundos)"):
        todos = []
        for e in exps[:5]:
            try:
                time.sleep(0.8)
                d = get_chain(ticker, e, tipo)
                if d is None: continue
                d = d.copy()
                d['volume']       = d['volume'].fillna(0).astype(int)
                d['openInterest'] = d['openInterest'].fillna(0).astype(int)
                u = d[(d['volume']>d['openInterest']*1.5)&(d['volume']>min_vol)].copy()
                if not u.empty:
                    u['Exp']    = e
                    u['Vol/OI'] = u.apply(lambda r: f"{r['volume']/r['openInterest']:.1f}x" if r['openInterest']>0 else 'NEW', axis=1)
                    u['Estado'] = u['strike'].apply(lambda s: '✅ ITM' if s<precio else '⭕ OTM')
                    u['IV%']    = (u['impliedVolatility']*100).round(1)
                    todos.append(u[['Exp','strike','Estado','IV%','openInterest','volume','Vol/OI']].rename(columns={'strike':'Strike','openInterest':'OI','volume':'Volumen'}))
            except: pass
        if todos:
            df_all = pd.concat(todos).sort_values('Volumen',ascending=False).reset_index(drop=True)
            st.dataframe(df_all, use_container_width=True)
            st.success(f"🔥 {len(df_all)} contratos unusual en total")
        else:
            st.info("📊 Sin unusual activity detectado.")

    st.caption("⚠️ Datos ~15 min delay. Solo educativo. No es asesoramiento financiero.")
