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


# --------------------------------------------------------------------------
# Respostas Q1–Q12
# --------------------------------------------------------------------------

def respostas(base: pd.DataFrame) -> list[dict]:
    lob = por_lob(base)
    lob_ano = por_lob_ano(base)
    cresc = crescimento(base)
    ativas = ativas_por_ano(base, "premio")
    ativas_pres = ativas_por_ano(base, "presenca")
    trend = tendencias(base)
    q4_tab = q4(base)
    akad = akad_tabela(base)
    comp = comparacao_akad(base)
    conc = concentracao(base)
    anos = sorted(base["ano"].unique())
    a0, a1 = anos[0], anos[-1]

    top1 = lob.iloc[0]
    sin_top = lob.sort_values("sinistralidade", ascending=False).iloc[0]
    lucro_top = lob.sort_values("lucro", ascending=False).iloc[0]
    margem_top = lob.sort_values("margem", ascending=False).iloc[0]
    cresc_pct = cresc.iloc[0] if not cresc.empty else None
    cresc_abs = cresc.sort_values("abs", ascending=False).iloc[0] if not cresc.empty else None

    fase = base[base["ano"] >= 2022]
    fase_anos = sorted(int(a) for a in fase["ano"].unique()) if not fase.empty else []
    fase0, fase1 = (fase_anos[0], fase_anos[-1]) if fase_anos else (None, None)

    def _share(lob_nome: str, ano: int) -> float:
        g = base[(base["lob"] == lob_nome) & (base["ano"] == ano)]
        total = float(g["premio_ganho"].sum())
        ak = float(g.loc[g["codigo_susep"] == AKAD, "premio_ganho"].sum())
        return ak / total if total > 0 else 0.0

    fase_txt = ""
    if fase_anos and fase0 != fase1:
        partes = [f"{l} {f_pct(_share(l, fase0))}→{f_pct(_share(l, fase1))}" for l in LOB_ORDEM]
        fase_txt = (
            f"Na fase Akad ({fase0}–{fase1}), o share por LOB foi " + "; ".join(partes) + "."
        )

    fase_comp_txt = ""
    if not fase.empty:
        partes = []
        for l in LOB_ORDEM:
            gf = fase[fase["lob"] == l]
            if gf.empty:
                continue
            ma = metricas(gf)
            aa = metricas(gf[gf["codigo_susep"] == AKAD])
            partes.append(
                f"{l}: margem Akad {f_pct(aa['margem'])} vs mercado {f_pct(ma['margem'])}, "
                f"sinistralidade {f_pct(aa['sinistralidade'])} vs {f_pct(ma['sinistralidade'])}"
            )
        fase_comp_txt = f"Na fase Akad ({fase0}–{fase1}), " + "; ".join(partes) + "."

    fase_m = {
        l: metricas(fase[fase["lob"] == l])
        for l in LOB_ORDEM
        if not fase[fase["lob"] == l].empty
    }
    fase_a = {
        l: metricas(fase[(fase["lob"] == l) & (fase["codigo_susep"] == AKAD)])
        for l in LOB_ORDEM
        if not fase[(fase["lob"] == l) & (fase["codigo_susep"] == AKAD)].empty
    }

    def _fase_lob(l: str) -> str:
        a, m = fase_a.get(l, {}), fase_m.get(l, {})
        return (
            f"{l}: share {f_pct(_share(l, fase0))}→{f_pct(_share(l, fase1))}, "
            f"margem {f_pct(a.get('margem'))} vs {f_pct(m.get('margem'))}, "
            f"sinistralidade {f_pct(a.get('sinistralidade'))} vs {f_pct(m.get('sinistralidade'))}"
        )

    def q4_text():
        partes = []
        for lob_nome in LOB_ORDEM:
            g = q4_tab[q4_tab["lob"] == lob_nome]
            if g.empty:
                continue
            r = g.iloc[0]
            partes.append(f"{lob_nome}: {r['seguradora']} ({f_pct(r['sinistralidade'])})")
        return "Com corte de materialidade de 1% do prêmio da LOB, as maiores sinistralidades do período são " + "; ".join(partes) + ". Sem o corte, seguradoras minúsculas dominam por efeito de base."

    def q8_text():
        partes = []
        for l in LOB_ORDEM:
            rr = conc[conc.lob == l]
            if rr.empty:
                continue
            rr = rr.iloc[0]
            seg = por_seguradora(base[(base.lob == l) & (base.premio_ganho > 0)])
            top = seg.sort_values("premio", ascending=False).head(3)["seguradora"].tolist()
            partes.append(f"{l}: top 5 {f_pct(rr['top5'])}, {int(rr['n80'])} até 80%; líderes {', '.join(top)}")
        return "A concentração é parecida entre as LOBs. " + "; ".join(partes) + "."

    def q9_text():
        partes = []
        for _, r in trend.iterrows():
            tend = "melhora" if r["slope"] < -0.005 else ("piora" if r["slope"] > 0.005 else "estável")
            partes.append(f"{r['lob']}: média {f_pct(r['sin_media'])}, desvio {f_pct(r['vol'])}, tendência {tend}")
        return "; ".join(partes) + ". Garantia é a mais confortável em nível; E&O e Empresarial melhoram; RCG é a mais volátil; Transportes é a mais estável, mas com sinistralidade alta."

    def q10_text():
        partes = []
        for _, r in akad.iterrows():
            partes.append(
                f"{r['lob']}: share {f_pct(r['share1'])} e {int(r['rank1'])}º lugar em {a1} "
                f"(em {a0}: {f_pct(r['share0'])}, {int(r['rank0'])}º)"
            )
        return "A Akad é relevante em E&O e Transportes. " + "; ".join(partes) + ". A posição melhora em quatro das cinco LOBs; em Garantia o share sobe, mas o posto cai porque o mercado ganhou mais concorrentes."

    def q11_text():
        partes = []
        for _, r in comp.iterrows():
            melhor = r["akad_mg"] > r["mercado_mg"] and r["akad_sin"] <= r["mercado_sin"]
            partes.append(
                f"{r['lob']}: margem Akad {f_pct(r['akad_mg'])} vs mercado {f_pct(r['mercado_mg'])}; "
                f"sinistralidade {f_pct(r['akad_sin'])} vs {f_pct(r['mercado_sin'])}"
                + (" — melhor que o mercado" if melhor else "")
            )
        return "; ".join(partes) + ". A vantagem mais clara está em E&O e RCG; Transportes tem escala, mas margem abaixo do mercado."

    respostas = [
        {
            "n": "01",
            "pergunta": "Qual a LOB com maior prêmio no período inteiro (2020 a 2025)?",
            "resposta": f"{top1['lob']} lidera com {f_bi(top1['premio'])}, seguida de "
            + ", ".join(f"{r['lob']} ({f_bi(r['premio'])})" for _, r in lob.iloc[1:].iterrows())
            + ". O prêmio é nominal.",
        },
        {
            "n": "02",
            "pergunta": "Qual a LOB com mais seguradoras ativas em 2020? E em 2025?",
            "resposta": f"Com ativa = prêmio ganho maior que zero, {ativas[a0].idxmax()} lidera em {a0} "
            f"({int(ativas[a0].max())}) e {ativas[a1].idxmax()} lidera em {a1} ({int(ativas[a1].max())}). "
            f"Por presença de linha, a leitura seria {ativas_pres[a0].idxmax()} em {a0} e {ativas_pres[a1].idxmax()} em {a1}; "
            "é presença cadastral, não operação.",
        },
        {
            "n": "03",
            "pergunta": "Qual a LOB com maior sinistralidade no período inteiro?",
            "resposta": f"{sin_top['lob']} tem a maior sinistralidade agregada: {f_pct(sin_top['sinistralidade'])}. "
            + " ".join(f"{r['lob']} {f_pct(r['sinistralidade'])};" for _, r in lob.sort_values('sinistralidade', ascending=False).iterrows()),
        },
        {
            "n": "04",
            "pergunta": "Qual a seguradora com maior sinistralidade no período em cada LOB?",
            "resposta": q4_text(),
        },
        {
            "n": "05",
            "pergunta": "Quanto foi o resultado técnico (receitas – despesas) de cada LOB?",
            "resposta": "No período: " + "; ".join(f"{r['lob']} {f_bi(r['lucro'])}" for _, r in lob.sort_values('lucro', ascending=False).iterrows())
            + f". {lucro_top['lob']} lidera, com {f_bi(lucro_top['lucro'])}. Resultado técnico não é lucro contábil: não inclui despesa administrativa, imposto nem resultado financeiro.",
        },
        {
            "n": "06",
            "pergunta": "Quanto foi a margem (resultado técnico/prêmio) de cada LOB?",
            "resposta": "Margem no período: " + "; ".join(f"{r['lob']} {f_pct(r['margem'])}" for _, r in lob.sort_values('margem', ascending=False).iterrows())
            + f". {margem_top['lob']} tem a maior margem ({f_pct(margem_top['margem'])}).",
        },
        {
            "n": "07",
            "pergunta": "Qual LOB teve o maior crescimento em prêmio no período, em porcentagem e em valor absoluto?",
            "resposta": (
                "Selecione pelo menos dois anos para calcular crescimento. "
                if cresc_pct is None
                else f"Em porcentagem, {cresc_pct.name} cresce {f_pct(cresc_pct['pct'])}; em valor absoluto, "
                f"{cresc_abs.name} adiciona {f_bi(cresc_abs['abs'])}. Sempre leia os dois juntos: "
                "porcentagem alta sobre base pequena pode ser irrelevante em tamanho."
            ),
        },
        {
            "n": "08",
            "pergunta": "Quais são as seguradoras realmente relevantes de cada LOB? Como margem e sinistralidade delas se comparam ao mercado?",
            "resposta": q8_text() + " O critério de relevância é o top 80% do prêmio acumulado. Na aba Concorrência, a tabela mostra share, margem e sinistralidade de cada relevante contra o mercado.",
        },
        {
            "n": "09",
            "pergunta": "Como é a tendência de sinistros e sinistralidade de cada LOB? Qual é a mais saudável/atrativa?",
            "resposta": q9_text(),
        },
        {
            "n": "10",
            "pergunta": "Em quais LOBs a Akad é relevante? Como se comportou a posição dela no período? O que pode explicar as mudanças?",
            "resposta": q10_text() + " " + fase_txt + " Leitura de marca: 2020–2021 é a operação Argo; a Akad nasce em 2022. A série de seis anos serve para tamanho e tendência, mas a posição atual deve ser lida de 2022 em diante. O rebranding é um divisor estrutural: parte do movimento reflete a reconstrução da marca e da estratégia, não só crescimento orgânico. A base não prova causalidade; as hipóteses são foco comercial, apetite de risco, canais de distribuição, capital e resseguro.",
        },
        {
            "n": "11",
            "pergunta": "Considerando margem e sinistralidade, em quais LOBs a Akad é melhor que o mercado? E em relação a outras seguradoras do mesmo porte? E às relevantes?",
            "resposta": q11_text() + " " + fase_comp_txt + " Em E&O e RCG a Akad também supera os pares de porte e as relevantes na margem; em Transportes, Garantia e Empresarial fica atrás. Em RCG o share ainda é pequeno e o mercado é volátil, então a vantagem é promissora, mas não escalada.",
        },
        {
            "n": "12",
            "pergunta": "Em qual LOB a Akad deveria focar nos próximos anos? Qual deve ser a estratégia?",
            "resposta": (
                f"Minha recomendação olha a fase Akad ({fase0}–{fase1}), porque 2020–2021 é a operação Argo e a marca Akad nasce em 2022. "
                + "; ".join(_fase_lob(l) for l in LOB_ORDEM)
                + ". A leitura é: E&O é o núcleo, porque combina liderança, margem acima do mercado e sinistralidade controlada; "
                "a posição de 2022 em diante mostra que a marca nasceu forte nessa LOB. Transportes é escala a corrigir, não "
                "prioridade de crescimento: a Akad cresceu, mas a margem da fase Akad é muito baixa e a sinistralidade passou de 60%. "
                "O foco ali é reprecificação, gestão de sinistros, resseguro e mix, não volume. RCG é aposta seletiva: share pequeno, "
                "mas margem acima do mercado e sinistralidade menor; crescer em nichos, com controle de acumulação. Garantia tem o "
                "mercado mais rentável, mas a Akad é subescala e opera pior; só entra com parceria ou nicho. Empresarial é grande, "
                "mas a Akad tem menos de 1% e margem baixa; não é prioridade. Em resumo: defender e expandir E&O, corrigir Transportes, "
                "crescer seletivamente em RCG e manter Garantia/Empresarial como opcionais. A estratégia deve usar a posição de 2022 "
                "como seguradora moderna e inovadora: canais de corretores, pricing e gestão de sinistros são a alavanca, não só preço."
            ),
        },
    ]
    return respostas
