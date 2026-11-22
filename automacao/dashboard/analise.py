"""Camada de análise do case (Q1–Q12) sobre o snapshot anual.

Regras: sinistralidade e margem por razão de somas; resultado técnico na
coluna `lucro`; seguradora ativa = prêmio ganho > 0; chave por Código SUSEP.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ses import publish
from ses.config import Config

LOB_ORDEM = ["Transportes", "Empresarial", "Garantia", "RCG", "E&O"]
LOB_COR = {
    "Transportes": "#F7A3BF",
    "Empresarial": "#6B72D8",
    "Garantia": "#8C4A6B",
    "RCG": "#143057",
    "E&O": "#E9256A",
}
AKAD = "02798"
COR_AKAD = "#E9256A"
VALORES = [
    "premio_ganho", "sinistro_ocorrido", "despesa_resseguro",
    "receita_resseguro", "despesa_comercial",
]


# --------------------------------------------------------------------------
# Carga e filtros
# --------------------------------------------------------------------------

def carregar_base(snapshot: str | None = None) -> pd.DataFrame:
    cfg = Config()
    nome = snapshot or publish.atual(cfg)
    if nome is None:
        return pd.DataFrame(columns=["lob", "ano", "codigo_susep", *VALORES, "lucro"])
    try:
        base = publish.carregar_base(cfg, nome)
    except Exception:
        base = pd.read_csv(
            cfg.snapshots / nome / "base.csv",
            encoding="utf-8-sig",
            dtype={"ramo_codigo": str, "codigo_susep": str},
        )
    base["ramo_codigo"] = base["ramo_codigo"].astype(str).str.zfill(4)
    base["codigo_susep"] = base["codigo_susep"].astype(str).str.zfill(5)
    return base


def filtrar(base: pd.DataFrame, lobs: list[str], ano_ini: int, ano_fim: int) -> pd.DataFrame:
    if base.empty:
        return base
    mask = base["lob"].isin(lobs) & base["ano"].between(ano_ini, ano_fim)
    return base.loc[mask].copy()


# --------------------------------------------------------------------------
# Métricas
# --------------------------------------------------------------------------

def metricas(df: pd.DataFrame) -> dict:
    p = float(df["premio_ganho"].sum())
    s = float(df["sinistro_ocorrido"].sum())
    l = float(df["lucro"].sum())
    return {
        "premio": p,
        "sinistro": s,
        "lucro": l,
        "sinistralidade": s / p if p > 0 else math.nan,
        "margem": l / p if p > 0 else math.nan,
    }


def por_lob(base: pd.DataFrame) -> pd.DataFrame:
    linhas = [{"lob": lob, **metricas(g)} for lob, g in base.groupby("lob")]
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    return df.sort_values("premio", ascending=False).reset_index(drop=True)


def por_lob_ano(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for (lob, ano), g in base.groupby(["lob", "ano"]):
        linhas.append({"lob": lob, "ano": int(ano), **metricas(g)})
    return pd.DataFrame(linhas).sort_values(["lob", "ano"]).reset_index(drop=True)


def por_seguradora(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for (lob, cod), g in base.groupby(["lob", "codigo_susep"], sort=False):
        m = metricas(g)
        m.update(
            lob=lob,
            codigo_susep=cod,
            seguradora=g["seguradora"].iloc[-1],
        )
        linhas.append(m)
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    total = df.groupby("lob")["premio"].transform("sum")
    df["share"] = df["premio"] / total.replace(0, np.nan)
    return df


def crescimento(base: pd.DataFrame) -> pd.DataFrame:
    p = base.groupby(["lob", "ano"]).premio_ganho.sum().unstack()
    if p.empty or p.shape[1] < 2:
        return pd.DataFrame()
    anos = sorted(p.columns)
    a, b = anos[0], anos[-1]
    out = pd.DataFrame(
        {
            "ano_ini": a,
            "ano_fim": b,
            "primeiro": p[a],
            "ultimo": p[b],
            "abs": p[b] - p[a],
        }
    )
    out["pct"] = np.where(out["primeiro"] > 0, out["ultimo"] / out["primeiro"] - 1, np.nan)
    out["cagr"] = np.where(
        (out["primeiro"] > 0) & (b > a),
        (out["ultimo"] / out["primeiro"]) ** (1 / (b - a)) - 1,
        np.nan,
    )
    return out.sort_values("pct", ascending=False)


def ativas_por_ano(base: pd.DataFrame, definicao: str = "premio") -> pd.DataFrame:
    df = base[base["premio_ganho"] > 0] if definicao == "premio" else base
    return df.groupby(["lob", "ano"]).codigo_susep.nunique().unstack()


def concentracao(base: pd.DataFrame) -> pd.DataFrame:
    ativa = base[base["premio_ganho"] > 0]
    cadastradas = base.groupby("lob").codigo_susep.nunique()
    linhas = []
    for lob, g in ativa.groupby("lob"):
        s = g.groupby("codigo_susep").premio_ganho.sum().sort_values(ascending=False)
        share = s / s.sum()
        n80 = int((share.cumsum() < 0.8).sum()) + 1
        linhas.append(
            {
                "lob": lob,
                "n_total": int(cadastradas.get(lob, 0)),
                "n_ativas": int(len(s)),
                "top5": float(share.head(5).sum()),
                "n80": n80,
                "hhi": int((share**2).sum() * 10000),
            }
        )
    return pd.DataFrame(linhas).sort_values("top5", ascending=False)


def tendencias(base: pd.DataFrame) -> pd.DataFrame:
    s = por_lob_ano(base)
    linhas = []
    for lob, g in s.groupby("lob"):
        g = g.sort_values("ano")
        valid = g.dropna(subset=["sinistralidade"])
        slope = (
            float(np.polyfit(valid["ano"], valid["sinistralidade"], 1)[0])
            if len(valid) >= 2
            else math.nan
        )
        cresc_sin = math.nan
        if len(g) >= 2 and g["sinistro"].iloc[0] > 0 and g["ano"].iloc[-1] > g["ano"].iloc[0]:
            cresc_sin = (g["sinistro"].iloc[-1] / g["sinistro"].iloc[0]) ** (
                1 / (g["ano"].iloc[-1] - g["ano"].iloc[0])
            ) - 1
        linhas.append(
            {
                "lob": lob,
                "sin_media": float(g["sinistralidade"].mean()),
                "vol": float(g["sinistralidade"].std()),
                "slope": slope,
                "cresc_sinistro": float(cresc_sin),
                "margem_media": float(g["margem"].mean()),
            }
        )
    return pd.DataFrame(linhas).sort_values("sin_media").reset_index(drop=True)


def q4(base: pd.DataFrame, min_share: float = 0.01, top: int = 3) -> pd.DataFrame:
    seg = por_seguradora(base[base["premio_ganho"] > 0])
    if seg.empty:
        return seg
    filtrada = seg[(seg["share"] >= min_share) & (seg["premio"] > 0)].copy()
    linhas = []
    for lob in LOB_ORDEM:
        g = filtrada[filtrada["lob"] == lob]
        if g.empty:
            g = seg[seg["lob"] == lob].nlargest(1, "premio")
        for _, r in g.sort_values("sinistralidade", ascending=False).head(top).iterrows():
            linhas.append(r.to_dict())
    return pd.DataFrame(linhas)


def relevantes(base: pd.DataFrame, lob: str, cobertura: float = 0.8):
    g = base[base["lob"] == lob]
    seg = por_seguradora(g[g["premio_ganho"] > 0])
    if seg.empty:
        return seg, 0, metricas(g)
    ordenada = seg.sort_values("premio", ascending=False)
    cum = ordenada["share"].cumsum()
    n = int((cum < cobertura).sum()) + 1
    mesa = ordenada.head(n).copy()
    mercado = metricas(g)
    mesa["delta_sin"] = mesa["sinistralidade"] - mercado["sinistralidade"]
    mesa["delta_margem"] = mesa["margem"] - mercado["margem"]
    return mesa, n, mercado


def akad_tabela(base: pd.DataFrame) -> pd.DataFrame:
    ak = base[base["codigo_susep"] == AKAD]
    anos = sorted(base["ano"].unique())
    if not anos:
        return pd.DataFrame()
    linhas = []
    for lob in LOB_ORDEM:
        g = base[base["lob"] == lob]
        if g.empty:
            continue
        a = ak[ak["lob"] == lob]
        p0, p1 = anos[0], anos[-1]
        premio0 = float(a.loc[a["ano"] == p0, "premio_ganho"].sum())
        premio1 = float(a.loc[a["ano"] == p1, "premio_ganho"].sum())
        mercado0 = float(g.loc[g["ano"] == p0, "premio_ganho"].sum())
        mercado1 = float(g.loc[g["ano"] == p1, "premio_ganho"].sum())

        def rank(ano: int):
            p = g[(g["ano"] == ano) & (g["premio_ganho"] > 0)].groupby("codigo_susep").premio_ganho.sum()
            if AKAD not in p.index:
                return None
            return int(p.rank(ascending=False, method="min").loc[AKAD])

        linhas.append(
            {
                "lob": lob,
                "premio0": premio0,
                "premio1": premio1,
                "share0": premio0 / mercado0 if mercado0 > 0 else 0.0,
                "share1": premio1 / mercado1 if mercado1 > 0 else 0.0,
                "rank0": rank(p0),
                "rank1": rank(p1),
                "n1": int(g[(g["ano"] == p1) & (g["premio_ganho"] > 0)].codigo_susep.nunique()),
                "abs": premio1 - premio0,
                "cresc": premio1 / premio0 - 1 if premio0 > 0 else math.nan,
            }
        )
    return pd.DataFrame(linhas)


def comparacao_akad(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for lob, g in base.groupby("lob"):
        a = g[g["codigo_susep"] == AKAD]
        if a.empty:
            continue
        ma, aa = metricas(g), metricas(a)
        p_ult = g[g["ano"] == g["ano"].max()].groupby("codigo_susep").premio_ganho.sum()
        alvo = p_ult.get(AKAD, 0.0)
        peers = [c for c in p_ult[(p_ult >= alvo / 3) & (p_ult <= alvo * 3)].index if c != AKAD]
        pm = metricas(g[g["codigo_susep"].isin(peers)]) if peers else {"sinistralidade": math.nan, "margem": math.nan}
        s = g[g["premio_ganho"] > 0].groupby("codigo_susep").premio_ganho.sum().sort_values(ascending=False)
        cum = s / s.sum()
        n80 = int((cum.cumsum() < 0.8).sum()) + 1
        relevantes_ = [c for c in s.index[:n80] if c != AKAD]
        rm = metricas(g[g["codigo_susep"].isin(relevantes_)]) if relevantes_ else {"sinistralidade": math.nan, "margem": math.nan}
        linhas.append(
            {
                "lob": lob,
                "mercado_sin": ma["sinistralidade"],
                "mercado_mg": ma["margem"],
                "akad_sin": aa["sinistralidade"],
                "akad_mg": aa["margem"],
                "peers_n": len(peers),
                "peers_sin": pm["sinistralidade"],
                "peers_mg": pm["margem"],
                "relev_n": len(relevantes_),
                "relev_sin": rm["sinistralidade"],
                "relev_mg": rm["margem"],
            }
        )
    return pd.DataFrame(linhas).sort_values("lob")


# --------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------

def f_num(v, dec: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_pct(v, dec: int = 1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v*100:,.{dec}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def f_bi(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sinal = "−" if v < 0 else ""
    return f"{sinal}R$ {abs(v)/1e9:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")


def f_mi(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sinal = "−" if v < 0 else ""
    return f"{sinal}R$ {abs(v)/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")


def f_pp(v, dec: int = 1) -> str:
    """Diferença em pontos percentuais, com sinal ('+1,2 pp')."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v*100:+.{dec}f} pp".replace(".", ",").replace("-", "−")


def f_din(v) -> str:
    """Dinheiro em escala legível: bi, mi, mil ou reais."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if abs(v) >= 1e9:
        return f_bi(v)
    if abs(v) >= 1e6:
        return f_mi(v)
    sinal = "−" if v < 0 else ""
    if abs(v) >= 1e3:
        return f"{sinal}R$ {abs(v)/1e3:,.0f} mil".replace(",", ".")
    return f"{sinal}R$ {abs(v):,.0f}".replace(",", ".")


_SIGLAS = {"BTG", "XL", "HDI", "AIG", "IRB", "BV", "BVIX", "SA"}
_RUIDO = {
    "S.A.", "S.A", "S/A", "SA", "SEGUROS", "SEGURO", "SEGURADORA", "COMPANHIA", "DE",
    "BRASIL", "GERAIS", "CORPORATIVOS", "PATRIMONIAIS",
}


def nome_curto(nome: str) -> str:
    """'TOKIO MARINE SEGURADORA S.A.' -> 'Tokio Marine' (só para texto corrido)."""
    palavras = [p for p in " ".join(str(nome).split()).split(" ") if p.upper() not in _RUIDO]
    if not palavras:
        return str(nome).title()
    return " ".join(p.upper() if p.upper() in _SIGLAS else p.capitalize() for p in palavras)


def componentes(df: pd.DataFrame) -> dict:
    """Como a margem se forma, em fração do prêmio ganho.

    margem = 1 − sinistralidade − resseguro líquido − despesa comercial,
    onde resseguro líquido = despesa com resseguro − receita com resseguro.
    """
    p = float(df["premio_ganho"].sum())
    if p <= 0:
        return {"sin": math.nan, "resseg": math.nan, "com": math.nan, "margem": math.nan}
    return {
        "sin": float(df["sinistro_ocorrido"].sum()) / p,
        "resseg": float(df["despesa_resseguro"].sum() - df["receita_resseguro"].sum()) / p,
        "com": float(df["despesa_comercial"].sum()) / p,
        "margem": float(df["lucro"].sum()) / p,
    }


# --------------------------------------------------------------------------
# Respostas Q1–Q12 (texto em respostas.py)
# --------------------------------------------------------------------------

def respostas(base: pd.DataFrame) -> list[dict]:
    """Q1–Q12 recalculadas sobre `base` (já filtrada). Ver dashboard/respostas.py."""
    from .respostas import gerar

    return gerar(base)
