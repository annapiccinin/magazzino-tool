import streamlit as st
import matplotlib.pyplot as plt
from analisi import *

st.set_page_config(page_title="Magazzino Tool", layout="wide")
st.title("📦 Analisi magazzino")

file = st.sidebar.file_uploader("Carica l'Excel", type="xlsx")
mesi = st.sidebar.slider("Stock fermo da più di (mesi)", 3, 24, 6)
z = st.sidebar.selectbox("Livello di servizio", [1.28, 1.65, 2.33],
                         index=1, format_func=lambda v: {1.28: "90%", 1.65: "95%", 2.33: "99%"}[v])

if file is None:
    st.info("Carica un file Excel per iniziare (puoi usare dati_esempio.xlsx).")
    st.stop()

articoli, mov, ubi = carica(file)
tab1, tab2 = st.tabs(["Slotting ABC/XYZ", "Stock morto e scorte"])

with tab1:
    classi = abc_xyz(mov)
    ordinati, spost, m_pre, m_post, ore = slotting(articoli, ubi, classi)

    c1, c2, c3 = st.columns(3)
    c1.metric("Articoli da spostare", len(spost))
    c2.metric("Riduzione percorsi", f"{(1 - m_post / m_pre):.0%}")
    c3.metric("Ore risparmiate nel periodo", f"{ore:.1f} h")

    colori = {"A": "red", "B": "orange", "C": "lightgray"}
    fig, ax = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for a, (xc, yc, titolo) in zip(ax, [("x", "y", "PRIMA"),
                                         ("x_nuova", "y_nuova", "DOPO")]):
        a.scatter(ubi["x"], ubi["y"], c="#eeeeee", s=40)  # tutte le ubicazioni
        a.scatter(ordinati[xc], ordinati[yc],
                  c=ordinati["ABC"].map(colori).fillna("lightgray"), s=60)
        a.scatter(0, 0, marker="s", c="blue", s=200)       # baia spedizione
        a.set_title(titolo)
    st.pyplot(fig)
    st.caption("🔴 A (alta rotazione)  🟠 B  ⚪ C  🟦 baia di spedizione")

    st.subheader("Lista spostamenti")
    st.dataframe(spost[["codice", "descrizione", "ABC", "XYZ",
                        "ubicazione", "ubicazione_nuova"]])

with tab2:
    morto, valore = stock_morto(articoli, mov, mesi)
    st.metric(f"💶 Merce ferma da oltre {mesi} mesi", f"{valore:,.0f} €".replace(",", "."))
    st.dataframe(morto[["codice", "descrizione", "giacenza", "valore", "giorni_fermo"]])

    st.subheader("Scorte di sicurezza e punto di riordino")
    sc = scorte_sicurezza(articoli, mov, z)
    st.dataframe(sc[["codice", "giacenza", "scorta_sicurezza",
                     "punto_riordino", "da_riordinare"]])
    st.download_button("Scarica Excel risultati",
                       sc.to_csv(index=False).encode(), "scorte.csv")
    