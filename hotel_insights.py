import sqlite3
import pandas as pd
import streamlit as st
import numpy as np
from datetime import datetime, timedelta

# --- 1. CONFIGURAÇÃO E CONSTANTES ---
# Removemos o sys.path fixo para garantir portabilidade
st.set_page_config(
    page_title="Hotel Insights Local | SaaS", 
    layout="wide", 
    page_icon="🏨",
    initial_sidebar_state="expanded"
)

DB_NAME = 'hotel_saas.db'
TOTAL_QUARTOS_PADRAO = 50  # Constante centralizada

# --- 2. GERENCIAMENTO DE DADOS (BACKEND) ---

def get_conexao():
    """Cria uma conexão com o banco de forma segura."""
    return sqlite3.connect(DB_NAME)

def init_db():
    """Inicializa o banco de dados se não existir."""
    try:
        with get_conexao() as conn:
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
            
            # Seed (Popular dados) se vazio
            c.execute('SELECT count(*) FROM diario')
            if c.fetchone()[0] == 0:
                print("Populando banco de dados com dados fictícios...")
                datas = [datetime.now() - timedelta(days=x) for x in range(30)]
                registros = []
                for d in datas:
                    is_weekend = d.weekday() >= 4
                    occ = np.random.uniform(70, 95) if is_weekend else np.random.uniform(40, 65)
                    adr = 280.0 if is_weekend else 210.0
                    conc_adr = adr * np.random.uniform(0.9, 1.1)
                    revpar = (occ/100) * adr
                    rec = revpar * TOTAL_QUARTOS_PADRAO
                    
                    registros.append((
                        d.strftime('%Y-%m-%d'), 
                        TOTAL_QUARTOS_PADRAO, 
                        occ, adr, conc_adr, revpar, rec
                    ))
                
                c.executemany('''INSERT INTO diario 
                             (data, quartos_totais, ocupacao_pct, adr, concorrente_adr, revpar, receita) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)''', registros)
    except sqlite3.Error as e:
        st.error(f"Erro crítico ao iniciar banco de dados: {e}")

def salvar_registro(data, quartos, ocupacao, adr, concorrente):
    """Calcula KPIs e salva no banco com tratamento de erro robusto."""
    try:
        # Cálculo de Negócio (RevPAR)
        # Fórmula: RevPAR = (Ocupação / 100) * ADR
        revpar = (ocupacao / 100) * adr
        receita = revpar * quartos
        
        with get_conexao() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO diario 
                (data, quartos_totais, ocupacao_pct, adr, concorrente_adr, revpar, receita)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data, quartos, ocupacao, adr, concorrente, revpar, receita))
            conn.commit()
            
        # Limpa o cache para forçar recarregamento dos dados na próxima visualização
        st.cache_data.clear() 
        return True, "✅ Dados processados e armazenados com sucesso!"
        
    except Exception as e:
        return False, f"Erro ao salvar: {str(e)}"

@st.cache_data(ttl=600) # Cache por 10 minutos ou até limpar
def carregar_dados():
    """Lê dados do banco e converte para Pandas. Usa Cache para performance."""
    try:
        with get_conexao() as conn:
            df = pd.read_sql_query("SELECT * FROM diario ORDER BY data ASC", conn)
            df['data'] = pd.to_datetime(df['data'])
            return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# Inicialização segura
init_db()

# --- 3. FRONTEND (UI) ---
def main():
    st.sidebar.title("🏨 Hotel Insights")
    st.sidebar.caption("Inteligência para PMEs")
    
    menu = st.sidebar.radio(
        "Menu Principal", 
        ["Dashboard Executivo", "Lançamento Diário", "Simulador Yield"]
    )
    st.sidebar.markdown("---")
    
    # Carregamos os dados uma única vez aqui
    df = carregar_dados()

    if menu == "Dashboard Executivo":
        st.title("📊 Painel de Controle (RevPAR)")
        
        if not df.empty:
            # Filtro de Data (Opcional, mas boa prática)
            ultimos_dias = st.slider("Período de Análise (Dias)", 7, 30, 30)
            df_filtrado = df.tail(ultimos_dias)
            last = df_filtrado.iloc[-1]

            # KPIs
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Ocupação", f"{last['ocupacao_pct']:.1f}%")
            k2.metric("Diária Média (ADR)", f"R$ {last['adr']:.2f}")
            
            delta_mercado = last['adr'] - last['concorrente_adr']
            k3.metric(
                "Concorrente", 
                f"R$ {last['concorrente_adr']:.2f}", 
                delta=f"{delta_mercado:.2f} vs Mercado", 
                delta_color="inverse" # Verde se formos mais baratos (estratégia de volume) ou Vermelho se mais caros? Ajuste conforme estratégia.
            )
            k4.metric("RevPAR", f"R$ {last['revpar']:.2f}")
            
            st.divider()
            
            # Gráficos e Tabelas
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("📈 Evolução da Receita por Quarto")
                st.line_chart(df_filtrado.set_index('data')[['revpar']], color="#29B5E8")
            
            with c2:
                st.subheader("📥 Exportar Dados")
                st.write("Baixe o histórico completo para Excel/BI.")
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Baixar CSV",
                    data=csv,
                    file_name='hotel_data.csv',
                    mime='text/csv',
                )

            st.subheader("⚔️ Competitividade de Preço")
            st.line_chart(df_filtrado.set_index('data')[['adr', 'concorrente_adr']], color=["#00CC96", "#EF553B"])

    elif menu == "Lançamento Diário":
        st.title("📝 Coleta de Dados")
        with st.form("input_form"):
            c1, c2 = st.columns(2)
            data_in = c1.date_input("Data", datetime.now())
            # Usa a constante, mas permite edição
            quartos_in = c2.number_input("Quartos Disponíveis", value=TOTAL_QUARTOS_PADRAO)
            
            c3, c4, c5 = st.columns(3)
            ocup_in = c3.slider("Ocupação (%)", 0, 100, 60)
            adr_in = c4.number_input("Sua Diária (R$)", value=220.0)
            conc_in = c5.number_input("Preço Concorrente (R$)", value=215.0)
            
            if st.form_submit_button("💾 Processar e Salvar"):
                sucesso, msg = salvar_registro(data_in, quartos_in, ocup_in, adr_in, conc_in)
                if sucesso: st.success(msg)
                else: st.error(msg)

    elif menu == "Simulador Yield":
        st.title("🧮 Calculadora de Yield Management")
        st.info("Simule cenários futuros sem alterar o banco de dados.")
        
        col1, col2 = st.columns(2)
        with col1:
            cenario_adr = st.number_input("Diária Planejada (Target)", 100.0, 1000.0, 250.0)
            cenario_occ = st.slider("Ocupação Estimada (%)", 0, 100, 50)
            
            # Cálculo formal exibido
            receita_proj = (cenario_occ/100) * cenario_adr * TOTAL_QUARTOS_PADRAO
            st.metric("Receita Projetada", f"R$ {receita_proj:,.2f}")
            
        with col2:
            st.markdown("### Análise do Algoritmo")
            if cenario_occ < 40: 
                st.warning("⚠️ **Baixa Demanda:** Considere promoções agressivas ou pacotes agregados.")
            elif cenario_occ > 85: 
                st.success("🚀 **Alta Demanda:** Oportunidade para aumentar a diária (Yield Up).")
            else: 
                st.info("✅ **Estável:** Mantenha a estratégia atual.")

if __name__ == "__main__":
    main()
