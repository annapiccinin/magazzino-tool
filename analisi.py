import numpy as np
import pandas as pd

def carica(file):
    xl = pd.read_excel(file, sheet_name=None)
    return xl["Articoli"], xl["Movimentazioni"], xl["Ubicazioni"]

# ---------- IDEA 1: ABC/XYZ + SLOTTING ----------
def abc_xyz(mov):
    mov = mov.copy()
    mov["data"] = pd.to_datetime(mov["data"])

    # ABC sulla frequenza di prelievo (righe), la metrica giusta per lo slotting
    righe = mov.groupby("codice").size().sort_values(ascending=False)
    cum = righe.cumsum() / righe.sum()
    abc = pd.cut(cum, [0, 0.8, 0.95, 1.001], labels=["A", "B", "C"])

    # XYZ sulla variabilità mensile della domanda (coefficiente di variazione)
    mov["mese"] = mov["data"].dt.to_period("M")
    mesi = pd.period_range(mov["mese"].min(), mov["mese"].max(), freq="M")
    mensile = (mov.pivot_table(index="codice", columns="mese",
                               values="quantita", aggfunc="sum", fill_value=0)
                  .reindex(columns=mesi, fill_value=0))
    cv = mensile.std(axis=1) / mensile.mean(axis=1)
    xyz = pd.cut(cv, [-1, 0.5, 1.0, np.inf], labels=["X", "Y", "Z"])

    return pd.DataFrame({"righe": righe, "ABC": abc, "CV": cv.round(2),
                         "XYZ": xyz}).reset_index()

def slotting(articoli, ubicazioni, classi, baia=(0, 0), velocita_m_s=1.0):
    df = articoli.merge(ubicazioni, on="ubicazione").merge(
        classi[["codice", "righe", "ABC", "XYZ"]], on="codice", how="left")
    df["righe"] = df["righe"].fillna(0)
    df["dist_prima"] = np.hypot(df["x"] - baia[0], df["y"] - baia[1])

    # Ubicazioni occupate, ordinate dalla più vicina alla baia
    posti = df[["ubicazione", "x", "y"]].copy()
    posti["dist"] = np.hypot(posti["x"] - baia[0], posti["y"] - baia[1])
    posti = posti.sort_values("dist").reset_index(drop=True)

    # Articoli più movimentati -> posti più vicini
    ordinati = df.sort_values("righe", ascending=False).reset_index(drop=True)
    ordinati["ubicazione_nuova"] = posti["ubicazione"]
    ordinati["x_nuova"] = posti["x"]
    ordinati["y_nuova"] = posti["y"]
    ordinati["dist_dopo"] = posti["dist"]

    # Metri percorsi (andata e ritorno per ogni riga di prelievo)
    metri_prima = (ordinati["righe"] * ordinati["dist_prima"] * 2).sum()
    metri_dopo = (ordinati["righe"] * ordinati["dist_dopo"] * 2).sum()
    ore_risparmiate = (metri_prima - metri_dopo) / velocita_m_s / 3600

    spostamenti = ordinati[ordinati["ubicazione"] != ordinati["ubicazione_nuova"]]
    return ordinati, spostamenti, metri_prima, metri_dopo, ore_risparmiate

# ---------- IDEA 2: STOCK MORTO + SCORTE ----------
def stock_morto(articoli, mov, mesi_soglia=6):
    mov = mov.copy()
    mov["data"] = pd.to_datetime(mov["data"])
    oggi = mov["data"].max()
    ultima = mov.groupby("codice")["data"].max().rename("ultimo_movimento")
    df = articoli.merge(ultima, on="codice", how="left")
    df["giorni_fermo"] = (oggi - df["ultimo_movimento"]).dt.days
    df["giorni_fermo"] = df["giorni_fermo"].fillna(9999)  # mai mosso
    df["valore"] = df["giacenza"] * df["costo_unitario"]
    morto = df[df["giorni_fermo"] > mesi_soglia * 30].copy()
    return morto.sort_values("valore", ascending=False), morto["valore"].sum()

def scorte_sicurezza(articoli, mov, livello_servizio_z=1.65):
    mov = mov.copy()
    mov["data"] = pd.to_datetime(mov["data"])
    mov["mese"] = mov["data"].dt.to_period("M")
    mesi = pd.period_range(mov["mese"].min(), mov["mese"].max(), freq="M")
    mensile = (mov.pivot_table(index="codice", columns="mese",
                               values="quantita", aggfunc="sum", fill_value=0)
                  .reindex(columns=mesi, fill_value=0))
    d_medio = mensile.mean(axis=1) / 30            # domanda media giornaliera
    d_sigma = mensile.std(axis=1) / np.sqrt(30)    # deviazione giornaliera (stima)
    df = articoli.set_index("codice").join(
        pd.DataFrame({"domanda_giorno": d_medio, "sigma_giorno": d_sigma}))
    df = df.dropna(subset=["domanda_giorno"])
    lt = df["lead_time_giorni"]
    df["scorta_sicurezza"] = (livello_servizio_z * df["sigma_giorno"] * np.sqrt(lt)).round()
    df["punto_riordino"] = (df["domanda_giorno"] * lt + df["scorta_sicurezza"]).round()
    df["da_riordinare"] = df["giacenza"] <= df["punto_riordino"]
    return df.reset_index()
