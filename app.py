import streamlit as st
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="TradeBot AI — Options Scanner",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
    .main { background-color: #0a0e1a; }
    .stApp { background-color: #0a0e1a; color: #c8d8e8; }
    h1, h2, h3 { color: #00ff88 !important; }
    .stTextInput input { background-color: #0d1321 !important; color: #c8d8e8 !important; border: 1px solid #1e3050 !important; }
    .stSelectbox select { background-color: #0d1321 !important; color: #c8d8e8 !important; }
    .stDataFrame { background-color: #0d1321 !important; }
    div[data-testid="stMetricValue"] { color: #00ff88 !important; font-size: 28px !important; }
    .unusual-box { background-color: #1a0f00; border: 1px solid #ffd700; border-radius: 8px; padding: 12px; margin: 8px 0; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ──────────────────────────────────────────────────────
st.markdown("# 📊 TradeBot AI — Options Scanner")
st.markdown("**Unusual Activity · Greeks · OI · Volumen · IV%** — Powered by yfinance")
st.markdown("---")

# ── INPUT ───────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    ticker = st.text_input("🔍 Ticker", value="AAPL", placeholder="AAPL, TSLA, ONDS...").upper().strip()

with col2:
    tipo = st.selectbox("Tipo", ["calls", "puts"])

with col3:
    min_volumen = st.number_input("Volumen mínimo unusual", min_value=10, value=100, step=10)

buscar = st.button("▶️ Analizar", use_container_width=True, type="primary")

# ── ANÁLISIS ────────────────────────────────────────────────────
if buscar and ticker:
    with st.spinner(f"Buscando opciones para {ticker}..."):
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            precio = (info.get('currentPrice') or info.get('regularMarketPrice')
                      or info.get('ask') or info.get('bid', 0))
            cambio = info.get('regularMarketChangePercent', 0)
            nombre = info.get('shortName', ticker)
            expiraciones = stock.options

            if not expiraciones:
                st.error(f"❌ No hay opciones disponibles para {ticker}. Verifica el ticker.")
                st.stop()

            # ── Métricas precio ──────────────────────────────────
            st.markdown(f"### {nombre} ({ticker})")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💲 Precio", f"${precio:.2f}", f"{cambio:+.2f}%")
            m2.metric("📅 Expiraciones", len(expiraciones))
            m3.metric("📊 Tipo", tipo.upper())
            m4.metric("⏰ Datos", "~15 min delay")

            st.markdown("---")

            # ── Selector de expiración ───────────────────────────
            exp_elegida = st.selectbox("📅 Expiración", expiraciones)

            # ── Procesar cadena ──────────────────────────────────
            chain  = stock.option_chain(exp_elegida)
            df_raw = chain.calls.copy() if tipo == 'calls' else chain.puts.copy()

            df = df_raw[['strike','bid','ask','volume','openInterest','impliedVolatility']].copy()
            df.columns = ['Strike','Bid','Ask','Volumen','OI','IV%']

            # Greeks si existen
            tiene_greeks = all(g in df_raw.columns for g in ['delta','gamma','theta','vega'])
            for g, col in [('delta','Delta'),('gamma','Gamma'),('theta','Theta'),('vega','Vega')]:
                df[col] = df_raw[g].round(4) if g in df_raw.columns else None

            df['IV%']     = (df['IV%'] * 100).round(1)
            df['Bid']     = df['Bid'].fillna(0).round(2)
            df['Ask']     = df['Ask'].fillna(0).round(2)
            df['OI']      = df['OI'].fillna(0).astype(int)
            df['Volumen'] = df['Volumen'].fillna(0).astype(int)
            df['Estado']  = df['Strike'].apply(lambda s: '✅ ITM' if s < precio else '⭕ OTM')
            df['Vol/OI']  = df.apply(lambda r: f"{r['Volumen']/r['OI']:.1f}x" if r['OI'] > 0 else 'NEW', axis=1)
            df['🔥']      = df.apply(lambda r: '🔥 UNUSUAL' if (r['Volumen'] > r['OI'] * 1.5 and r['Volumen'] > min_volumen) else '', axis=1)

            unusual_count = len(df[df['🔥'] == '🔥 UNUSUAL'])

            # ── Tabs ─────────────────────────────────────────────
            tab1, tab2 = st.tabs([f"📋 Cadena completa ({len(df)} contratos)", f"🔥 Unusual Activity ({unusual_count})"])

            with tab1:
                if not tiene_greeks:
                    st.warning(f"⚠️ Greeks no disponibles para {ticker} en yfinance (normal en small caps)")

                if tiene_greeks:
                    cols_show = ['Strike','Estado','Delta','Gamma','Theta','Vega','IV%','Bid','Ask','OI','Volumen','Vol/OI','🔥']
                else:
                    cols_show = ['Strike','Estado','IV%','Bid','Ask','OI','Volumen','Vol/OI','🔥']

                def color_rows(row):
                    if row.get('🔥') == '🔥 UNUSUAL':
                        return ['background-color: #2a1800; color: #ffd700'] * len(row)
                    elif row.get('Estado') == '✅ ITM':
                        return ['background-color: #0a1f0a; color: #00ff88'] * len(row)
                    return [''] * len(row)

                st.dataframe(
                    df[cols_show].style.apply(color_rows, axis=1),
                    use_container_width=True,
                    height=500
                )

            with tab2:
                df_unusual = df[df['🔥'] == '🔥 UNUSUAL'].copy()

                if df_unusual.empty:
                    st.info("📊 Sin unusual activity detectado en esta expiración.")
                    st.markdown("Prueba con otra fecha de expiración o reduce el volumen mínimo.")
                else:
                    st.success(f"🔥 {len(df_unusual)} contratos con flujo inusual detectados")

                    for _, row in df_unusual.iterrows():
                        with st.container():
                            st.markdown(f"""
                            <div class='unusual-box'>
                            <b>Strike ${row['Strike']}</b> — {row['Estado']} — Exp: {exp_elegida}<br>
                            📊 OI: <b>{row['OI']:,}</b> | Volumen: <b>{row['Volumen']:,}</b> | Vol/OI: <b>{row['Vol/OI']}</b><br>
                            📈 IV: <b>{row['IV%']}%</b> | Bid/Ask: <b>${row['Bid']} / ${row['Ask']}</b>
                            {f"<br>Greeks → Delta: <b>{row['Delta']}</b> | Theta: <b>{row['Theta']}</b>" if tiene_greeks and row['Delta'] else ""}
                            </div>
                            """, unsafe_allow_html=True)

            # ── Escaneo unusual en TODAS las expiraciones ────────
            st.markdown("---")
            st.markdown("### 🔥 Unusual Activity — Todas las expiraciones")

            with st.spinner("Escaneando todas las expiraciones..."):
                todos_unusual = []
                for exp in expiraciones:
                    try:
                        c = stock.option_chain(exp)
                        d = c.calls.copy() if tipo == 'calls' else c.puts.copy()
                        d['volume']       = d['volume'].fillna(0).astype(int)
                        d['openInterest'] = d['openInterest'].fillna(0).astype(int)
                        u = d[(d['volume'] > d['openInterest'] * 1.5) & (d['volume'] > min_volumen)].copy()
                        if not u.empty:
                            u['Exp']    = exp
                            u['Vol/OI'] = u.apply(lambda r: f"{r['volume']/r['openInterest']:.1f}x" if r['openInterest'] > 0 else 'NEW', axis=1)
                            u['Estado'] = u['strike'].apply(lambda s: '✅ ITM' if s < precio else '⭕ OTM')
                            u['IV%']    = (u['impliedVolatility'] * 100).round(1)
                            todos_unusual.append(u[['Exp','strike','Estado','IV%','openInterest','volume','Vol/OI']].rename(columns={'strike':'Strike','openInterest':'OI','volume':'Volumen'}))
                    except:
                        pass

                if todos_unusual:
                    df_all = pd.concat(todos_unusual).sort_values('Volumen', ascending=False).reset_index(drop=True)
                    st.dataframe(df_all, use_container_width=True)
                    st.success(f"🔥 {len(df_all)} contratos con unusual activity en total")
                else:
                    st.info("📊 Sin unusual activity en ninguna expiración.")

            st.markdown("---")
            st.caption("⚠️ Datos con ~15 min de retraso vía yfinance. Solo educativo. No es asesoramiento financiero.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("Verifica que el ticker sea correcto y tenga opciones listadas.")
