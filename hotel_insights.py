import sys
import os
import sqlite3
import pandas as pd
import streamlit as st
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np

# --- 1. CONFIGURAÇÃO DE AMBIENTE ---
path_customizado = '/home/eacborges/Python_Tools'
if path_customizado not in sys.path:
    sys.path.append(path_customizado)

# Backend gráfico para Linux
matplotlib.use('Agg')

# Configuração da Página
st.set_page_config(
    page_title="Hotel Insights Local | SaaS", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="expanded"
)

# --- 2. BACKEND & DATABASE ---
def init_db():
    conn = sqlite3.connect('hotel_saas.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE UNIQUE,
            quartos_totais INTEGER,
            ocupacao_pct REAL,
            adr REAL,
            concorrente_adr REAL,
            revpar REAL,
            receita REAL
        )
    ''')
    
    # Popula com dados se estiver vazio
    c.execute('SELECT count(*) FROM diario')
    if c.fetchone()[0] == 0:
        datas = [datetime.now() - timedelta(days=x) for x in range(30)]
        for d in datas:
            is_weekend = d.weekday() >= 4
            occ = np.random.uniform(70, 95) if is_weekend else np.random.uniform(40, 65)
            adr = 280.0 if is_weekend else 210.0
            conc_adr = adr * np.random.uniform(0.9, 1.1)
            revpar = (occ/100) * adr
            rec = revpar * 50
            
            c.execute('''INSERT INTO diario 
                         (data, quartos_totais, ocupacao_pct, adr, concorrente_adr, revpar, receita) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                         (d.strftime('%Y-%m-%d'), 50, occ, adr, conc_adr, revpar, rec))
        conn.commit()
    conn.close()

def salvar_registro(data, quartos, ocupacao, adr, concorrente):
    revpar = (ocupacao/100) * adr
    receita = revpar * quartos
    conn = sqlite3.connect('hotel_saas.db')
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR REPLACE INTO diario (data, quartos_totais, ocupacao_pct, adr, concorrente_adr, revpar, receita)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data, quartos, ocupacao, adr, concorrente, revpar, receita))
        conn.commit()
        return True, "✅ Dados processados e armazenados com sucesso!"
    except Exception as e:
        return False, f"Erro ao salvar: {e}"
    finally:
        conn.close()

def carregar_dados():
    conn = sqlite3.connect('hotel_saas.db')
    df = pd.read_sql_query("SELECT * FROM diario ORDER BY data ASC", conn)
    conn.close()
    df['data'] = pd.to_datetime(df['data'])
    return df

init_db()

# --- 3. FRONTEND ---
def main():
    st.sidebar.title("🏨 Hotel Insights")
    st.sidebar.caption("Inteligência para PMEs da Serra Gaúcha")
    
    menu = st.sidebar.radio(
        "Menu Principal", 
        ["Dashboard Executivo", "Lançamento Diário", "Simulador Yield"]
    )
    st.sidebar.markdown("---")
    
    if menu == "Dashboard Executivo":
        st.title("📊 Painel de Controle (RevPAR)")
        df = carregar_dados()
        if not df.empty:
            last = df.iloc[-1]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Ocupação", f"{last['ocupacao_pct']:.1f}%")
            k2.metric("Nossa Diária", f"R$ {last['adr']:.2f}")
            k3.metric("Concorrente", f"R$ {last['concorrente_adr']:.2f}", 
                      delta=f"{last['adr'] - last['concorrente_adr']:.2f} vs Mercado", delta_color="inverse")
            k4.metric("RevPAR", f"R$ {last['revpar']:.2f}")
            
            st.divider()
            st.subheader("📈 Evolução da Receita por Quarto")
            st.line_chart(df.set_index('data')[['revpar']], color="#29B5E8")
            
            st.subheader("⚔️ Monitoramento de Competitividade")
            st.line_chart(df.set_index('data')[['adr', 'concorrente_adr']], color=["#00CC96", "#EF553B"])
            st.caption("Verde: Nossa Diária | Vermelho: Concorrente")

    elif menu == "Lançamento Diário":
        st.title("📝 Coleta de Dados")
        with st.form("input_form"):
            c1, c2 = st.columns(2)
            data_in = c1.date_input("Data", datetime.now())
            quartos_in = c2.number_input("Quartos Disponíveis", value=50)
            c3, c4, c5 = st.columns(3)
            ocup_in = c3.slider("Ocupação (%)", 0, 100, 60)
            adr_in = c4.number_input("Sua Diária (R$)", value=220.0)
            conc_in = c5.number_input("Preço Concorrente (R$)", value=215.0)
            if st.form_submit_button("💾 Salvar"):
                sucesso, msg = salvar_registro(data_in, quartos_in, ocup_in, adr_in, conc_in)
                if sucesso: st.success(msg)
                else: st.error(msg)

    elif menu == "Simulador Yield":
        st.title("🧮 Calculadora de Yield")
        col1, col2 = st.columns(2)
        with col1:
            cenario_adr = st.number_input("Diária Planejada", 100.0, 1000.0, 250.0)
            cenario_occ = st.slider("Ocupação Estimada", 0, 100, 50)
            st.metric("Receita Projetada", f"R$ {(cenario_occ/100)*cenario_adr*50:,.2f}")
        with col2:
            if cenario_occ < 40: st.warning("⚠️ Baixar preço sugerido.")
            elif cenario_occ > 85: st.success("🚀 Aumentar preço sugerido.")
            else: st.info("✅ Manter preço.")

if __name__ == "__main__":
    main()
