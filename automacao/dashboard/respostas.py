"""Respostas Q1–Q12 do case, escritas a partir dos dados filtrados.

Cada resposta é um dict {n, pergunta, curta, resposta}:
  - `curta`    uma frase, para legenda de gráfico e para a fala;
  - `resposta` markdown completo (frase-resposta, tabela de apoio, leitura).

Todo número vem da base recebida: se o usuário filtra LOBs ou anos, o texto muda
junto. As únicas partes fixas são o contexto de marca e a recomendação da Q12
(papel de cada LOB), que são julgamento, não resultado automático.

Método: sinistralidade e margem = razão de somas; resultado técnico = prêmio ganho
+ receita de resseguro − sinistro ocorrido − despesa de resseguro − despesa
comercial; ativa = prêmio ganho > 0; relevante = top 80% do prêmio acumulado.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import analise as A

AKAD = A.AKAD
INICIO_FASE_AKAD = 2022
TOL = 0.01  # 1 p.p.: abaixo disso a diferença é tratada como "em linha"

NOME_COMPONENTE = {
    "sin": "sinistralidade",
    "resseg": "resseguro líquido",
    "com": "despesa comercial",
}


# --------------------------------------------------------------------------
# Utilitários de texto
# --------------------------------------------------------------------------

def _nan(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def _pct(v, dec: int = 1) -> str:
    return A.f_pct(v, dec)


def _lista(itens) -> str:
    itens = [str(i) for i in itens]
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _tabela(cab: list[str], linhas: list[list], esq=1) -> str:
    """Tabela markdown. `esq`: nº de colunas à esquerda (as primeiras) ou conjunto de índices."""
    esq = set(range(esq)) if isinstance(esq, int) else set(esq)
    alinh = ["---" if i in esq else "---:" for i in range(len(cab))]
    saida = ["| " + " | ".join(cab) + " |", "| " + " | ".join(alinh) + " |"]
    saida += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return "\n".join(saida)


def _item(n: str, pergunta: str, curta: str, corpo: str = "") -> dict:
    texto = f"**{curta}**" + (f"\n\n{corpo.strip()}" if corpo.strip() else "")
    return {"n": n, "pergunta": pergunta, "curta": curta, "resposta": texto}


def _mult(a: float, b: float) -> float:
    return b / a if a and a > 0 else math.inf


def _x(v: float) -> str:
    """Multiplicador em texto: '×3,5'."""
    return "n/d" if not math.isfinite(v) else f"×{v:.1f}".replace(".", ",")


# --------------------------------------------------------------------------
# Contexto comum
# --------------------------------------------------------------------------

class _Ctx:
    def __init__(self, base: pd.DataFrame):
        self.base = base
        self.anos = sorted(int(a) for a in base["ano"].unique())
        self.a0, self.a1 = self.anos[0], self.anos[-1]
        self.periodo = f"{self.a0}–{self.a1}" if self.a0 != self.a1 else str(self.a0)
        presentes = set(base["lob"].unique())
        self.lobs = [l for l in A.LOB_ORDEM if l in presentes]

        self.lob = A.por_lob(base).set_index("lob")          # ordenado por prêmio
        self.lob_ano = A.por_lob_ano(base)
        self.cresc = A.crescimento(base)
        self.conc = A.concentracao(base).set_index("lob")
        self.trend = A.tendencias(base).set_index("lob")
        self.akad = A.akad_tabela(base)
        self.akad = self.akad.set_index("lob") if not self.akad.empty else self.akad

        fase = base[base["ano"] >= INICIO_FASE_AKAD]
        self.tem_fase = not fase.empty
        self.fase = fase if self.tem_fase else base
        fa = sorted(int(a) for a in self.fase["ano"].unique())
        self.f0, self.f1 = fa[0], fa[-1]
        self.fase_rotulo = f"{self.f0}–{self.f1}" if self.f0 != self.f1 else str(self.f0)
        # a fase só é um recorte distinto se o período também tem anos anteriores a 2022
        self.fase_distinta = self.tem_fase and self.a0 < INICIO_FASE_AKAD

    def premio_ano(self, lob: str, ano: int, so_akad: bool = False) -> float:
        g = self.base[(self.base["lob"] == lob) & (self.base["ano"] == ano)]
        if so_akad:
            g = g[g["codigo_susep"] == AKAD]
        return float(g["premio_ganho"].sum())


# --------------------------------------------------------------------------
# Q1–Q3
# --------------------------------------------------------------------------

def _q01(c: _Ctx) -> dict:
    lob = c.lob
    total = float(lob["premio"].sum())
    top = lob.index[0]
    if len(lob) == 1:
        curta = f"{top} soma {A.f_bi(lob.loc[top, 'premio'])} em {c.periodo}."
    else:
        curta = (
            f"{top} lidera com {A.f_bi(lob.loc[top, 'premio'])}, "
            f"{_pct(lob.loc[top, 'premio'] / total, 0)} do prêmio das {len(lob)} LOBs em {c.periodo}."
        )
    linhas = [[l, A.f_bi(r["premio"]), _pct(r["premio"] / total)] for l, r in lob.iterrows()]
    corpo = (
        _tabela(["LOB", "Prêmio ganho", "% do total"], linhas)
        + "\n\nValores nominais, sem correção pela inflação. Prêmio mede tamanho de mercado, "
        "não rentabilidade: a maior LOB não é necessariamente a mais lucrativa (ver Q5 e Q6)."
    )
    return _item("01", "Qual a LOB com maior prêmio no período inteiro (2020 a 2025)?", curta, corpo)


def _q02(c: _Ctx) -> dict:
    atv = A.ativas_por_ano(c.base, "premio")
    pres = A.ativas_por_ano(c.base, "presenca")
    a0, a1 = c.a0, c.a1
    l0, l1 = atv[a0].idxmax(), atv[a1].idxmax()
    n0, n1 = int(atv[a0].max()), int(atv[a1].max())

    if a0 == a1:
        curta = f"{l0} tem mais seguradoras ativas em {a0}: {n0}."
    elif l0 == l1:
        curta = f"{l0} tem mais seguradoras ativas nos dois anos: {n0} em {a0} e {n1} em {a1}."
    else:
        curta = f"{l0} lidera em {a0} ({n0}) e {l1} lidera em {a1} ({n1})."

    pl0, pl1 = pres[a0].idxmax(), pres[a1].idxmax()
    if a0 == a1:
        cab = ["LOB", f"Ativas {a0}", f"Linhas no SES {a0}"]
        linhas = [[l, int(atv.loc[l, a0]), int(pres.loc[l, a0])] for l in c.lobs]
        leitura_pres = f"{pl0} em {a0}"
    else:
        cab = ["LOB", f"Ativas {a0}", f"Ativas {a1}", f"Linhas no SES {a0}", f"Linhas no SES {a1}"]
        linhas = [
            [l, int(atv.loc[l, a0]), int(atv.loc[l, a1]), int(pres.loc[l, a0]), int(pres.loc[l, a1])]
            for l in c.lobs
        ]
        leitura_pres = f"{pl0} em {a0} e {pl1} em {a1}"
    corpo = (
        _tabela(cab, linhas)
        + "\n\nAtiva = seguradora com prêmio ganho maior que zero no ano. O SES também lista "
        "seguradoras cadastradas sem operação; se a contagem fosse por presença de linha, a "
        f"leitura seria {leitura_pres}, mas isso mede cadastro, não atividade."
    )
    return _item("02", "Qual a LOB com mais seguradoras ativas em 2020? E em 2025?", curta, corpo)


def _q03(c: _Ctx) -> dict:
    d = c.lob.sort_values("sinistralidade", ascending=False)
    top = d.index[0]
    curta = f"{top} tem a maior sinistralidade do período: {_pct(d.loc[top, 'sinistralidade'])}"
    if len(d) > 1:
        seg = d.index[1]
        gap = d.loc[top, "sinistralidade"] - d.loc[seg, "sinistralidade"]
        if gap < 0.005:
            curta += (
                f", em empate técnico com {seg} ({_pct(d.loc[seg, 'sinistralidade'])}; "
                f"diferença de {gap * 100:.1f} pp)".replace(".", ",")
            )
    curta += "."
    linhas = [
        [l, A.f_bi(r["sinistro"]), A.f_bi(r["premio"]), _pct(r["sinistralidade"])]
        for l, r in d.iterrows()
    ]
    corpo = _tabela(["LOB", "Sinistros ocorridos", "Prêmio ganho", "Sinistralidade"], linhas)
    if len(d) > 1:
        low = d.index[-1]
        corpo += (
            f"\n\n{low} é a menor ({_pct(d.loc[low, 'sinistralidade'])}). "
        )
    corpo += (
        "Sinistralidade = soma dos sinistros ocorridos ÷ soma dos prêmios ganhos "
        "(razão de somas, não média das razões anuais)."
    )
    return _item("03", "Qual a LOB com maior sinistralidade no período inteiro?", curta, corpo)


# --------------------------------------------------------------------------
# Q4
# --------------------------------------------------------------------------

def q4_curta(base: pd.DataFrame, min_share: float = 0.01) -> str:
    tab = A.q4(base, min_share=min_share, top=1)
    partes = [
        f"{r['lob']} – {A.nome_curto(r['seguradora'])} ({_pct(r['sinistralidade'])})"
        for _, r in tab.iterrows()
    ]
    return (
        f"Com corte de materialidade (share ≥ {_pct(min_share, 0)} do prêmio da LOB), a maior "
        f"sinistralidade é: " + "; ".join(partes) + "."
    )


def _q04(c: _Ctx) -> dict:
    com = A.q4(c.base, min_share=0.01, top=1).set_index("lob")
    sem = A.q4(c.base, min_share=0.0, top=1).set_index("lob")
    linhas = []
    for l in c.lobs:
        if l not in com.index or l not in sem.index:
            continue
        a, b = com.loc[l], sem.loc[l]
        linhas.append([
            l, A.nome_curto(a["seguradora"]), _pct(a["sinistralidade"]), _pct(a["share"]),
            A.nome_curto(b["seguradora"]), _pct(b["sinistralidade"], 0), A.f_din(b["premio"]),
        ])
    cab = ["LOB", "Com corte ≥ 1%", "Sinistr.", "Share",
           "Sem corte", "Sinistr.", "Prêmio da seguradora"]
    curta = q4_curta(c.base, 0.01)
    extremo = max(
        (sem.loc[l] for l in c.lobs if l in sem.index),
        key=lambda r: r["sinistralidade"],
        default=None,
    )
    corpo = _tabela(cab, linhas, esq={0, 1, 4})
    corpo += (
        "\n\nA resposta usa corte de materialidade: só entram seguradoras com pelo menos 1% do "
        "prêmio da LOB no período. Sem o corte, o ranking vira uma lista de seguradoras minúsculas"
    )
    if extremo is not None:
        corpo += (
            f" (por exemplo, {A.nome_curto(extremo['seguradora'])}: sinistralidade de "
            f"{_pct(extremo['sinistralidade'], 0)} sobre um prêmio de {A.f_din(extremo['premio'])})"
        )
    corpo += (
        ", em que um único sinistro domina a razão. O cálculo é por seguradora, somando o período "
        "(razão de somas), sobre linhas com prêmio positivo; sinistralidade negativa é reversão "
        "de reserva e, por isso, nunca aparece como a maior."
    )
    return _item("04", "Qual a seguradora com maior sinistralidade no período em cada LOB?", curta, corpo)


# --------------------------------------------------------------------------
# Q5–Q7
# --------------------------------------------------------------------------

def _q05(c: _Ctx) -> dict:
    d = c.lob.sort_values("lucro", ascending=False)
    top = d.index[0]
    total = float(d["lucro"].sum())
    pos_premio = int(c.lob["premio"].rank(ascending=False).loc[top])
    curta = f"{top} gera o maior resultado técnico: {A.f_bi(d.loc[top, 'lucro'])}"
    if len(d) > 1 and pos_premio != 1:
        curta += f", mesmo sendo a {pos_premio}ª em prêmio"
    curta += "."
    linhas = [
        [l, A.f_bi(r["lucro"]), _pct(r["lucro"] / total) if total > 0 else "–", A.f_bi(r["premio"])]
        for l, r in d.iterrows()
    ]
    corpo = (
        _tabela(["LOB", "Resultado técnico", "% do total", "Prêmio ganho"], linhas)
        + "\n\nResultado técnico = prêmio ganho + receita com resseguro − sinistro ocorrido − "
        "despesa com resseguro − despesa comercial. Não é lucro contábil: ficam de fora despesas "
        "administrativas, impostos e o resultado financeiro."
    )
    return _item("05", "Quanto foi o resultado técnico (receitas – despesas) de cada LOB?", curta, corpo)


def _q06(c: _Ctx) -> dict:
    d = c.lob.sort_values("margem", ascending=False)
    top, bot = d.index[0], d.index[-1]
    curta = f"{top} tem a maior margem ({_pct(d.loc[top, 'margem'])})"
    if len(d) > 1:
        curta += f" e {bot} a menor ({_pct(d.loc[bot, 'margem'])})"
        if bot == c.lob.index[0]:
            curta += ", apesar de ser a maior LOB em prêmio"
    curta += "."

    comp = {l: A.componentes(c.base[c.base["lob"] == l]) for l in d.index}
    linhas = [
        [l, _pct(comp[l]["sin"]), _pct(comp[l]["resseg"]), _pct(comp[l]["com"]), _pct(comp[l]["margem"])]
        for l in d.index
    ]
    corpo = _tabela(
        ["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Margem"], linhas
    )
    corpo += (
        "\n\nMargem = resultado técnico ÷ prêmio ganho = 100% − sinistralidade − resseguro líquido "
        "(despesa − receita com resseguro) − despesa comercial."
    )
    if len(d) > 1:
        dif = {k: comp[top][k] - comp[bot][k] for k in ("sin", "resseg", "com")}
        gap_pp = f"{(d.loc[top, 'margem'] - d.loc[bot, 'margem']) * 100:.1f}".replace(".", ",")
        corpo += (
            f" A diferença de {gap_pp} pp entre {top} e {bot} "
            f"vem de sinistralidade ({A.f_pp(-dif['sin'])}), resseguro líquido ({A.f_pp(-dif['resseg'])}) "
            f"e despesa comercial ({A.f_pp(-dif['com'])}), a favor de {top}."
        )
    return _item("06", "Quanto foi a margem (resultado técnico/prêmio) de cada LOB?", curta, corpo)


def _q07(c: _Ctx) -> dict:
    pergunta = "Qual LOB teve o maior crescimento em prêmio no período, em porcentagem e em valor absoluto?"
    if c.cresc.empty:
        return _item("07", pergunta, "Selecione pelo menos dois anos para calcular crescimento.")
    d = c.cresc
    pct_top = d["pct"].idxmax()
    abs_top = d["abs"].idxmax()
    if pct_top == abs_top:
        curta = (
            f"{pct_top} lidera nos dois critérios: {_pct(d.loc[pct_top, 'pct'])} "
            f"(+{A.f_bi(d.loc[pct_top, 'abs'])})."
        )
    else:
        curta = (
            f"{pct_top} cresce mais em porcentagem ({_pct(d.loc[pct_top, 'pct'])}); "
            f"{abs_top} adiciona mais em valor absoluto (+{A.f_bi(d.loc[abs_top, 'abs'])})."
        )
    linhas = [
        [l, A.f_bi(r["primeiro"]), A.f_bi(r["ultimo"]), A.f_bi(r["abs"]), _pct(r["pct"]), _pct(r["cagr"])]
        for l, r in d.sort_values("pct", ascending=False).iterrows()
    ]
    corpo = _tabela(
        ["LOB", f"Prêmio {c.a0}", f"Prêmio {c.a1}", "Variação absoluta", "Variação %", "Ao ano (CAGR)"],
        linhas,
    )
    if pct_top != abs_top:
        corpo += (
            f"\n\nOs dois critérios contam histórias diferentes: {pct_top} parte de uma base de "
            f"{A.f_bi(d.loc[pct_top, 'primeiro'])} e por isso soma só {A.f_bi(d.loc[pct_top, 'abs'])}; "
            f"{abs_top} cresce a uma taxa menor sobre uma base maior e é quem mais aumenta o mercado em reais."
        )
    corpo += " Valores nominais: o crescimento inclui inflação."
    return _item("07", pergunta, curta, corpo)


# --------------------------------------------------------------------------
# Q8
# --------------------------------------------------------------------------

def _q08(c: _Ctx) -> dict:
    linhas, desvios, n80s, top5s = [], [], [], []
    for l in c.lobs:
        mesa, n, mercado = A.relevantes(c.base, l)
        if mesa.empty:
            continue
        prem = float(mesa["premio"].sum())
        sin = float(mesa["sinistro"].sum()) / prem if prem > 0 else math.nan
        mg = float(mesa["lucro"].sum()) / prem if prem > 0 else math.nan
        d_sin, d_mg = sin - mercado["sinistralidade"], mg - mercado["margem"]
        top5 = float(c.conc.loc[l, "top5"]) if l in c.conc.index else math.nan
        n80s.append(n)
        top5s.append(top5)
        if abs(d_sin) >= 2 * TOL or abs(d_mg) >= 2 * TOL:
            desvios.append((l, d_sin, d_mg))
        lideres = ", ".join(A.nome_curto(s) for s in mesa.head(3)["seguradora"])
        linhas.append([
            l, int(c.conc.loc[l, "n_ativas"]) if l in c.conc.index else "–", n, _pct(top5),
            f"{_pct(sin)} ({A.f_pp(d_sin)})", f"{_pct(mg)} ({A.f_pp(d_mg)})", lideres,
        ])
    if not linhas:
        return _item("08", "Quais são as seguradoras realmente relevantes de cada LOB?", "Sem seguradoras com prêmio positivo.")

    intervalo = f"{min(n80s)}" if min(n80s) == max(n80s) else f"{min(n80s)} a {max(n80s)}"
    curta = (
        f"{intervalo} seguradoras explicam 80% do prêmio em cada LOB (as 5 maiores somam "
        f"{_pct(min(top5s), 0)} a {_pct(max(top5s), 0)}), e as relevantes "
    )
    if desvios:
        partes = []
        for l, d_sin, d_mg in desvios:
            if abs(d_sin) >= 2 * TOL:
                partes.append(f"{l} (sinistralidade {A.f_pp(d_sin)})")
            else:
                partes.append(f"{l} (margem {A.f_pp(d_mg)})")
        curta += f"se comportam como o mercado, exceto em {_lista(partes)}."
    else:
        curta += "se comportam como o mercado (diferenças menores que 2 pp)."
    corpo = _tabela(
        ["LOB", "Ativas no período", "Relevantes (80%)", "Top 5", "Sinistralidade das relevantes (vs mercado)",
         "Margem das relevantes (vs mercado)", "Líderes"],
        linhas,
        esq={0, 6},
    )
    corpo += (
        "\n\nRelevante = seguradora entre as que, somadas em ordem de prêmio, chegam a 80% do prêmio "
        "da LOB. A diferença entre parênteses é contra o mercado inteiro da LOB. A concentração é "
        "moderada: nenhuma LOB é duopólio, mas também nenhuma é pulverizada. Na aba Concorrência há a "
        "lista completa das relevantes, com share, margem e sinistralidade de cada uma."
    )
    return _item("08", "Quais são as seguradoras realmente relevantes de cada LOB? Como margem e sinistralidade delas se comparam ao mercado?", curta, corpo)


# --------------------------------------------------------------------------
# Q9
# --------------------------------------------------------------------------

def _rotulo_tendencia(slope: float) -> str:
    if _nan(slope):
        return "–"
    if slope < -0.005:
        return f"melhora ({A.f_pp(slope)}/ano)"
    if slope > 0.005:
        return f"piora ({A.f_pp(slope)}/ano)"
    return f"estável ({A.f_pp(slope)}/ano)"


def _q09(c: _Ctx) -> dict:
    t = c.trend.loc[[l for l in c.lobs if l in c.trend.index]]
    pergunta = "Como é a tendência de sinistros e sinistralidade de cada LOB? Qual você considera mais saudável/atrativa?"
    if len(t) == 0:
        return _item("09", pergunta, "Sem dados suficientes.")

    pior, pior_txt = {}, {}
    for l in t.index:
        g = c.lob_ano[c.lob_ano["lob"] == l].dropna(subset=["sinistralidade"])
        if not g.empty:
            r = g.loc[g["sinistralidade"].idxmax()]
            pior[l] = f"{int(r['ano'])} ({_pct(r['sinistralidade'])})"
            pior_txt[l] = f"pior ano {int(r['ano'])}, com {_pct(r['sinistralidade'])}"
    cagr_premio = c.cresc["cagr"] if not c.cresc.empty else pd.Series(dtype=float)

    linhas = [
        [l, _pct(r["sin_media"]), _pct(r["vol"]), _rotulo_tendencia(r["slope"]), pior.get(l, "–"),
         _pct(r["cresc_sinistro"]), _pct(cagr_premio.get(l, math.nan))]
        for l, r in t.sort_values("sin_media").iterrows()
    ]
    tabela = _tabela(
        ["LOB", "Sinistralidade média anual", "Volatilidade (desvio)", "Tendência", "Pior ano",
         "Crescimento dos sinistros ao ano", "Crescimento do prêmio ao ano"],
        linhas,
        esq={0, 3, 4},
    )

    nivel = t["sin_media"].idxmin()
    # atratividade: margem alta, sinistralidade baixa e crescimento alto (ranking médio)
    ranks = pd.DataFrame(index=t.index)
    ranks["margem"] = c.lob.loc[t.index, "margem"].rank(ascending=False)
    ranks["sin"] = c.lob.loc[t.index, "sinistralidade"].rank(ascending=True)
    if not c.cresc.empty:
        ranks["cresc"] = c.cresc.loc[[l for l in t.index if l in c.cresc.index], "pct"].rank(ascending=False)
    atrativa = ranks.mean(axis=1).idxmin()

    if len(t) == 1:
        curta = f"{nivel}: sinistralidade média de {_pct(t.loc[nivel, 'sin_media'])}, {_rotulo_tendencia(t.loc[nivel, 'slope'])}."
    elif nivel == atrativa:
        curta = f"{nivel} é a LOB mais saudável e atrativa: menor sinistralidade e melhor conjunto de margem e crescimento."
    else:
        curta = (
            f"{nivel} é a mais saudável em nível de sinistralidade ({_pct(t.loc[nivel, 'sin_media'])} em média); "
            f"no conjunto margem + sinistralidade + crescimento, {atrativa} é a mais atrativa."
        )

    melhora = [f"{l} ({A.f_pp(r['slope'])}/ano)" for l, r in t.iterrows() if not _nan(r["slope"]) and r["slope"] < -0.005]
    piora = [f"{l} ({A.f_pp(r['slope'])}/ano)" for l, r in t.iterrows() if not _nan(r["slope"]) and r["slope"] > 0.005]
    estavel = [l for l, r in t.iterrows() if not _nan(r["slope"]) and abs(r["slope"]) <= 0.005]
    tem_serie = bool(t["slope"].notna().any())  # tendência e volatilidade exigem 2+ anos
    pontos = []
    if tem_serie:
        pontos.append(
            "**Tendência da sinistralidade:** "
            + "; ".join(
                x for x in [
                    f"melhora em {_lista(melhora)}" if melhora else "",
                    f"piora em {_lista(piora)}" if piora else "",
                    f"estável em {_lista(estavel)}" if estavel else "",
                ] if x
            )
            + "."
        )
        if len(t) > 1:
            estavel_top, volatil = t["vol"].idxmin(), t["vol"].idxmax()
            pontos.append(
                f"**Estabilidade:** {estavel_top} é a mais estável (desvio de {_pct(t.loc[estavel_top, 'vol'])}) "
                f"e {volatil} a mais volátil (desvio de {_pct(t.loc[volatil, 'vol'])}; {pior_txt.get(volatil, '')})."
            )
        if len(t) > 1 and nivel != atrativa:
            cresc_atr = (
                f", crescimento de {_pct(c.cresc.loc[atrativa, 'pct'])} no período"
                if not c.cresc.empty and atrativa in c.cresc.index else ""
            )
            pontos.append(
                f"**Nível × conjunto:** {nivel} tem o menor nível de sinistralidade, mas com tendência de "
                f"{_rotulo_tendencia(t.loc[nivel, 'slope'])} e {pior_txt.get(nivel, 'oscilação entre os anos')}. "
                f"{atrativa} combina a margem de {_pct(c.lob.loc[atrativa, 'margem'])}, sinistralidade de "
                f"{_pct(c.lob.loc[atrativa, 'sinistralidade'])} ({_rotulo_tendencia(t.loc[atrativa, 'slope'])})"
                f"{cresc_atr}. Por isso a escolha da mais atrativa combina os três critérios, não só a média."
            )
    else:
        pontos.append("Selecione pelo menos dois anos para medir tendência e volatilidade.")
    corpo = (
        tabela
        + "\n\nSinistralidade média = média simples dos anos (usada para medir volatilidade e tendência; "
        "o nível do período, por razão de somas, está na Q3). Tendência = inclinação da reta ajustada à "
        "sinistralidade anual, em pontos percentuais por ano; ±0,5 pp/ano é tratado como estável.\n\n"
        + "\n".join(f"- {p}" for p in pontos)
    )
    return _item("09", pergunta, curta, corpo)


# --------------------------------------------------------------------------
# Q10
# --------------------------------------------------------------------------

def _margem_akad_ano(base: pd.DataFrame, lob: str, ano: int) -> float:
    g = base[(base["lob"] == lob) & (base["ano"] == ano) & (base["codigo_susep"] == AKAD)]
    return A.metricas(g)["margem"] if not g.empty else math.nan


def _q10(c: _Ctx) -> dict:
    pergunta = "Em quais LOBs a Akad é relevante? Como se comportou a posição dela no período? O que pode explicar as mudanças?"
    if c.akad.empty:
        return _item("10", pergunta, "A Akad não aparece nas LOBs selecionadas.")
    ak = c.akad.loc[[l for l in c.lobs if l in c.akad.index]]
    a0, a1 = c.a0, c.a1

    def relevante(r) -> bool:
        return (not _nan(r["rank1"]) and r["rank1"] <= 5) or r["share1"] >= 0.05

    rel = [l for l, r in ak.iterrows() if relevante(r)]
    sub = [l for l in ak.index if l not in rel]

    def desc(l: str) -> str:
        r = ak.loc[l]
        pos = f", {int(r['rank1'])}º" if not _nan(r["rank1"]) else ""
        return f"{l} ({_pct(r['share1'])}{pos})"

    if rel:
        curta = f"A Akad é relevante em {_lista([desc(l) for l in rel])}"
        curta += f"; nas demais é subescala: {_lista([desc(l) for l in sub])}." if sub else "."
    else:
        curta = f"A Akad é subescala em todas as LOBs selecionadas: {_lista([desc(l) for l in ak.index])}."

    linhas = [
        [l, A.f_mi(r["premio0"]), A.f_mi(r["premio1"]), _pct(r["share0"]), _pct(r["share1"]),
         f"{int(r['rank0'])}º" if not _nan(r["rank0"]) else "–",
         f"{int(r['rank1'])}º" if not _nan(r["rank1"]) else "–"]
        for l, r in ak.iterrows()
    ]
    tabela = _tabela(
        ["LOB", f"Prêmio {a0}", f"Prêmio {a1}", f"Share {a0}", f"Share {a1}", f"Posição {a0}", f"Posição {a1}"],
        linhas,
    )

    corpo = tabela + "\n\nRelevante = entre as 5 maiores em prêmio na LOB ou com share de pelo menos 5% no último ano."
    if a0 == a1:
        return _item("10", pergunta, curta, corpo)

    melhorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] < r["rank0"]]
    piorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] > r["rank0"]]
    traj = f"**Posição:** o posto melhora em {len(melhorou)} de {len(ak)} LOBs ({_lista(melhorou)})" if melhorou else "**Posição:** nenhuma LOB melhora de posto"
    if piorou:
        det = []
        atv = A.ativas_por_ano(c.base, "premio")
        for l in piorou:
            r = ak.loc[l]
            det.append(
                f"{l}, onde o posto cai de {int(r['rank0'])}º para {int(r['rank1'])}º mesmo com share de "
                f"{_pct(r['share0'])} para {_pct(r['share1'])}, porque as seguradoras ativas foram de "
                f"{int(atv.loc[l, a0])} para {int(atv.loc[l, a1])}"
            )
        traj += "; exceção: " + "; ".join(det)
    traj += "."

    fase_txt = ""
    if c.fase_distinta and c.f0 != c.f1:
        partes = []
        for l in ak.index:
            s0 = c.premio_ano(l, c.f0, True) / max(c.premio_ano(l, c.f0), 1)
            s1 = c.premio_ano(l, c.f1, True) / max(c.premio_ano(l, c.f1), 1)
            partes.append(f"{l} {_pct(s0)}→{_pct(s1)}")
        fase_txt = f"**Só na fase Akad ({c.f0}–{c.f1}), o share foi:** " + "; ".join(partes) + "."

    # o que pode explicar: fatos por LOB, calculados
    fatos = []
    for l, r in ak.iterrows():
        mult_ak = _mult(r["premio0"], r["premio1"])
        mult_mk = _mult(c.premio_ano(l, a0), c.premio_ano(l, a1))
        m0, m1 = _margem_akad_ano(c.base, l, a0), _margem_akad_ano(c.base, l, a1)
        linha = (
            f"**{l}:** prêmio {A.f_mi(r['premio0'])} → {A.f_mi(r['premio1'])} "
            f"({_x(mult_ak)}) contra {_x(mult_mk)} do mercado"
            + f"; margem da Akad {_pct(m0)} → {_pct(m1)}."
        )
        if math.isfinite(mult_ak) and mult_ak >= 8:
            linha += " Partiu de uma base muito pequena: o salto reflete uma operação ainda incipiente que ganhou tração."
        elif relevante(r) and not _nan(m0) and not _nan(m1):
            if m1 < m0 - 0.05:
                linha += " Cresceu perdendo margem."
            elif m1 > m0 + 0.05:
                linha += " Cresceu ganhando margem."
        if l == "Empresarial" and c.a0 <= 2022 and c.a1 >= 2024:
            p22 = c.premio_ano(l, 2022, True)
            p24 = c.premio_ano(l, 2024, True)
            linha += (
                f" Em Empresarial, o prêmio da Akad foi {A.f_mi(p22)} em 2022 e {A.f_mi(p24)} em 2024: "
                "é um lançamento de produto, não crescimento de uma carteira madura."
            )
        fatos.append(linha)

    marca = (
        "**Contexto de marca:** a operação brasileira começou em 2012 como Argo Seguros, foi comprada "
        "em 2021 por um grupo liderado pela GP Investments e passou a se chamar Akad em junho de 2022. "
        "O código SUSEP (02798) não muda, então a série é contínua, mas 2020–2021 reflete a estratégia "
        "Argo e 2022 em diante a da Akad. Por isso a posição atual deve ser lida de 2022 em diante."
    )
    hip = (
        "**O que pode explicar as mudanças (hipóteses; o SES não prova causalidade):** foco comercial "
        "em corretores e em PMEs, apetite de risco e política de preço, capital disponível para reter "
        "risco e a estrutura de resseguro. Os fatos acima mostram onde houve crescimento, mas "
        "a causa exige dados internos (preço, comissão por canal, tratados de resseguro)."
    )
    corpo += "\n\n" + traj
    if fase_txt:
        corpo += "\n\n" + fase_txt
    corpo += "\n\n" + "\n".join(f"- {f}" for f in fatos) + "\n\n" + marca + "\n\n" + hip
    return _item("10", pergunta, curta, corpo)


# --------------------------------------------------------------------------
# Q11
# --------------------------------------------------------------------------

def _status(akad: float, ref: float, menor_melhor: bool) -> str:
    d = (ref - akad) if menor_melhor else (akad - ref)
    return "melhor" if d > TOL else ("pior" if d < -TOL else "em linha")


def _frase(akad: float, refs: dict[str, float], menor_melhor: bool) -> str:
    grupos: dict[str, list[str]] = {"melhor": [], "em linha": [], "pior": []}
    for nome, v in refs.items():
        if not _nan(v) and not _nan(akad):
            grupos[_status(akad, v, menor_melhor)].append(nome)
    rot = {"melhor": "melhor que", "em linha": "em linha com", "pior": "pior que"}
    partes = [f"{rot[k]} {_lista(v)}" for k, v in grupos.items() if v]
    return _lista(partes) if partes else "sem referência"


def _tabela_comparacao(comp: pd.DataFrame) -> str:
    linhas = [
        [l, _pct(r["akad_mg"]), _pct(r["mercado_mg"]), f"{_pct(r['peers_mg'])} ({int(r['peers_n'])})",
         f"{_pct(r['relev_mg'])} ({int(r['relev_n'])})",
         _pct(r["akad_sin"]), _pct(r["mercado_sin"]), _pct(r["peers_sin"]), _pct(r["relev_sin"])]
        for l, r in comp.iterrows()
    ]
    return _tabela(
        ["LOB", "Margem Akad", "Mercado", "Pares (n)", "Relevantes (n)",
         "Sinistr. Akad", "Mercado", "Pares", "Relevantes"],
        linhas,
    )


def _comparacao(base: pd.DataFrame, lobs: list[str]) -> pd.DataFrame:
    comp = A.comparacao_akad(base)
    if comp.empty:
        return comp
    comp = comp.set_index("lob")
    return comp.loc[[l for l in lobs if l in comp.index]]


def _contribuicoes(df: pd.DataFrame, lob: str) -> dict:
    """Contribuição de cada componente para (margem Akad − margem mercado), em fração."""
    g = df[df["lob"] == lob]
    a, m = A.componentes(g[g["codigo_susep"] == AKAD]), A.componentes(g)
    out = {k: -(a[k] - m[k]) for k in ("sin", "resseg", "com")}
    out["total"] = a["margem"] - m["margem"]
    return out


def _driver(contrib: dict) -> str:
    k = max(("sin", "resseg", "com"), key=lambda x: abs(contrib[x]) if not _nan(contrib[x]) else 0)
    return f"{NOME_COMPONENTE[k]} ({A.f_pp(contrib[k])})"


def _q11(c: _Ctx) -> dict:
    pergunta = "Considerando margem e sinistralidade, em quais LOBs a Akad é melhor que o mercado? E em relação a outras seguradoras do mesmo porte? E às relevantes?"
    comp = _comparacao(c.base, c.lobs)
    if comp.empty:
        return _item("11", pergunta, "A Akad não aparece nas LOBs selecionadas.")

    consistentes, abaixo, mistas, veredito = [], [], [], []
    for l, r in comp.iterrows():
        mg = {"mercado": r["mercado_mg"], "pares": r["peers_mg"], "relevantes": r["relev_mg"]}
        sn = {"mercado": r["mercado_sin"], "pares": r["peers_sin"], "relevantes": r["relev_sin"]}
        st_mg = [_status(r["akad_mg"], v, False) for v in mg.values() if not _nan(v)]
        st_sn = [_status(r["akad_sin"], v, True) for v in sn.values() if not _nan(v)]
        if st_mg and all(s == "melhor" for s in st_mg) and all(s != "pior" for s in st_sn):
            consistentes.append(l)
        elif st_mg and all(s == "pior" for s in st_mg):
            abaixo.append(l)
        else:
            mistas.append(l)
        veredito.append(
            f"**{l}:** margem {_frase(r['akad_mg'], mg, False)}; "
            f"sinistralidade {_frase(r['akad_sin'], sn, True)}."
        )

    partes = []
    if consistentes:
        partes.append(
            f"supera mercado, pares e relevantes em margem, sem piorar a sinistralidade, em {_lista(consistentes)}"
        )
    if abaixo:
        partes.append(f"fica abaixo dos três em margem em {_lista(abaixo)}")
    if mistas:
        partes.append(f"tem resultado misto em {_lista(mistas)}")
    curta = "A Akad " + "; ".join(partes) + "."

    corpo = f"**Período {c.periodo}.**\n\n" + _tabela_comparacao(comp)
    corpo += (
        "\n\nPares = seguradoras com prêmio entre 1/3 e 3 vezes o da Akad na LOB no último ano; "
        "relevantes = as que somam 80% do prêmio da LOB (sem a Akad); entre parênteses, o número de "
        "seguradoras do grupo. \"Em linha\" = diferença de até 1 pp.\n\n"
        + "\n".join(f"- {v}" for v in veredito)
    )

    if c.fase_distinta and c.f0 != c.f1:
        comp_f = _comparacao(c.fase, c.lobs)
        if not comp_f.empty:
            corpo += (
                f"\n\n**Só na fase Akad ({c.f0}–{c.f1}):**\n\n" + _tabela_comparacao(comp_f)
            )

    # de onde vem a diferença de margem (na fase Akad, se existir)
    ref_df = c.fase
    ref_rot = f"{c.f0}–{c.f1}" if c.f0 != c.f1 else str(c.f0)
    linhas, notas = [], []
    for l in comp.index:
        k = _contribuicoes(ref_df, l)
        if any(_nan(k[x]) for x in k):
            continue
        linhas.append([l, A.f_pp(k["sin"]), A.f_pp(k["resseg"]), A.f_pp(k["com"]), A.f_pp(k["total"])])
        notas.append(f"{l}: {A.f_pp(k['total'])} de margem frente ao mercado, puxado por {_driver(k)}")
    if linhas:
        corpo += (
            f"\n\n**De onde vem a diferença de margem ({ref_rot}).** Contribuição de cada componente para "
            "(margem da Akad − margem do mercado), em pontos percentuais do prêmio; positivo ajuda a Akad.\n\n"
            + _tabela(["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Diferença de margem"], linhas)
            + "\n\n" + "\n".join(f"- {n}" for n in notas)
            + "\n\nResseguro líquido = despesa − receita com resseguro. Um valor menor que o do mercado "
            "significa que a Akad cede menos risco: a margem sobe nos anos bons, mas a Akad retém mais "
            "capital e mais volatilidade."
        )
    return _item("11", pergunta, curta, corpo)


# --------------------------------------------------------------------------
# Q12
# --------------------------------------------------------------------------

PAPEL = {
    "E&O": ("Núcleo", "defender e expandir"),
    "Transportes": ("Corrigir", "rentabilizar antes de crescer"),
    "RCG": ("Aposta seletiva", "crescer em nichos, com controle de acumulação"),
    "Garantia": ("Opcional", "só com parceria ou nicho"),
    "Empresarial": ("Opcional", "não é prioridade"),
}


def _q12(c: _Ctx) -> dict:
    pergunta = "Em qual LOB a Akad deveria focar nos próximos anos? Qual deve ser a estratégia?"
    if not c.tem_fase:
        return _item(
            "12",
            pergunta,
            "A fase Akad começa em 2022. Selecione pelo menos um ano de 2022 em diante.",
            "A marca Akad foi criada em junho de 2022, depois da compra pela GP em 2021. "
            "A série de 2020–2021 é a operação Argo; sem anos de 2022 em diante, não há base "
            "para recomendar foco com a estratégia atual. Volte o filtro para 2022–2025.",
        )
    fase = c.fase
    lobs = [l for l in c.lobs if not fase[(fase["lob"] == l) & (fase["codigo_susep"] == AKAD)].empty]
    if not lobs:
        return _item("12", pergunta, "A Akad não aparece nas LOBs selecionadas.")

    def share(l: str, ano: int) -> float:
        tot = c.premio_ano(l, ano)
        return c.premio_ano(l, ano, True) / tot if tot > 0 else 0.0

    tot_akad_f1 = sum(c.premio_ano(l, c.f1, True) for l in c.lobs)
    dados = {}
    for l in lobs:
        g = fase[fase["lob"] == l]
        a = g[g["codigo_susep"] == AKAD]
        m_ak, m_mk = A.metricas(a), A.metricas(g)
        dados[l] = {
            "s0": share(l, c.f0), "s1": share(l, c.f1),
            "mg_a": m_ak["margem"], "mg_m": m_mk["margem"],
            "sin_a": m_ak["sinistralidade"], "sin_m": m_mk["sinistralidade"],
            "lucro_a": m_ak["lucro"], "premio_a": m_ak["premio"],
            "mix": c.premio_ano(l, c.f1, True) / tot_akad_f1 if tot_akad_f1 > 0 else math.nan,
            "k": _contribuicoes(fase, l),
        }

    linhas = []
    for l in lobs:
        d = dados[l]
        papel, acao = PAPEL.get(l, ("–", "–"))
        linhas.append([
            l, f"{_pct(d['s0'])} → {_pct(d['s1'])}",
            f"{_pct(d['mg_a'])} vs {_pct(d['mg_m'])}",
            f"{_pct(d['sin_a'])} vs {_pct(d['sin_m'])}",
            A.f_mi(d["lucro_a"]), _pct(d["mix"], 0), f"**{papel}**: {acao}",
        ])
    tabela = _tabela(
        ["LOB", "Share", "Margem Akad vs mercado", "Sinistr. Akad vs mercado",
         "Resultado técnico da Akad", f"% do prêmio da Akad em {c.f1}", "Papel"],
        linhas,
        esq={0, 6},
    )

    curta = (
        "Focar em E&O (defender e expandir), corrigir a rentabilidade de Transportes, tratar RCG como "
        "aposta seletiva e manter Garantia e Empresarial como opcionais."
    )

    partes = [f"**Base da recomendação:** fase Akad ({c.fase_rotulo}), porque a marca e a estratégia atuais começam em 2022.", tabela]

    def d(l: str) -> dict | None:
        return dados.get(l)

    eo = d("E&O")
    if eo:
        fatos_eo = []
        if c.lob["margem"].idxmax() == "E&O":
            fatos_eo.append(f"a LOB de maior margem do mercado ({_pct(c.lob.loc['E&O', 'margem'])})")
        if not c.cresc.empty and "E&O" in c.cresc.index and c.cresc["pct"].idxmax() == "E&O":
            fatos_eo.append(f"a que mais cresce em porcentagem ({_pct(c.cresc.loc['E&O', 'pct'])})")
        txt = (
            f"**Por que E&O.** É a LOB em que a Akad já lidera ({_pct(eo['s1'])} de share em {c.f1}), com margem "
            f"de {_pct(eo['mg_a'])} contra {_pct(eo['mg_m'])} do mercado e sinistralidade de "
            f"{_pct(eo['sin_a'])} contra {_pct(eo['sin_m'])}."
            + (f" É também {_lista(fatos_eo)}." if fatos_eo else "")
            + " "
        )
        tr = d("Transportes")
        if tr and tr["premio_a"] > 0 and eo["premio_a"] > 0:
            txt += (
                f"No período, E&O deu à Akad {A.f_din(eo['lucro_a'])} de resultado técnico com "
                f"{A.f_din(eo['premio_a'])} de prêmio; Transportes deu {A.f_din(tr['lucro_a'])} com "
                f"{A.f_din(tr['premio_a'])}."
            )
        partes.append(txt)
        partes.append(
            "**Ressalvas de E&O (o que a banca deve cobrar).** "
            f"(1) A vantagem de margem vem sobretudo do resseguro (contribui com {A.f_pp(eo['k']['resseg'])}) e pouco da "
            f"sinistralidade (contribui com {A.f_pp(eo['k']['sin'])}): a Akad cede pouco risco, o que rende mais nos anos "
            "bons mas exige mais capital e aumenta a volatilidade. "
            "(2) Em uma carteira jovem, que cresce rápido e é de cauda longa, a sinistralidade recente pode subestimar o "
            "custo final; vale validar a suficiência das reservas. "
            f"(3) O mercado é pequeno ({A.f_bi(c.premio_ano('E&O', c.f1))} em {c.f1}) e a Akad já tem {_pct(eo['s1'], 0)} dele: "
            "o teto de crescimento orgânico é baixo, então expandir exige aumentar o mercado "
            "(novas profissões e segmentos, PMEs, riscos cibernéticos) e não apenas tomar share."
        )

    tr = d("Transportes")
    if tr:
        partes.append(
            f"**Transportes: corrigir, não crescer.** A Akad subiu para {_pct(tr['s1'])} de share, mas a margem na fase é "
            f"{_pct(tr['mg_a'])} contra {_pct(tr['mg_m'])} do mercado. A diferença de {A.f_pp(tr['k']['total'])} vem de "
            f"sinistralidade ({A.f_pp(tr['k']['sin'])}) e despesa comercial ({A.f_pp(tr['k']['com'])}), parcialmente "
            f"compensadas pelo resseguro ({A.f_pp(tr['k']['resseg'])}); são contribuições à margem. Como Transportes é {_pct(tr['mix'], 0)} do prêmio da "
            "Akad em " + str(c.f1) + ", a rentabilidade dessa LOB define o resultado da empresa. "
            "Ações: reprecificação por segmento e rota, gestão de sinistros e prevenção (roubo e acidente), "
            "revisão da política de comissão e do mix de clientes e uso do resseguro para limitar perdas grandes."
        )

    rcg = d("RCG")
    if rcg:
        vol_rcg = c.trend.loc["RCG", "vol"] if "RCG" in c.trend.index else math.nan
        partes.append(
            f"**RCG: aposta seletiva.** Share pequeno ({_pct(rcg['s1'])}), mas margem de {_pct(rcg['mg_a'])} contra "
            f"{_pct(rcg['mg_m'])} do mercado e sinistralidade de {_pct(rcg['sin_a'])} contra {_pct(rcg['sin_m'])}. "
            "O risco é que o mercado é volátil"
            + (f" (desvio anual de {_pct(vol_rcg)} na sinistralidade)" if not _nan(vol_rcg) else "")
            + ": crescer em nichos, com limites de acumulação e resseguro para perdas grandes."
        )

    gar, emp = d("Garantia"), d("Empresarial")
    if gar or emp:
        txt = "**Garantia e Empresarial: opcionais.** "
        if gar:
            lider_lucro = c.lob["lucro"].idxmax() == "Garantia"
            txt += (
                f"Garantia {'tem o maior resultado técnico do mercado' if lider_lucro else 'gera'} "
                f"({A.f_bi(c.lob.loc['Garantia', 'lucro'])}), mas a Akad tem "
                f"{_pct(gar['s1'])} e margem de {_pct(gar['mg_a'])} contra {_pct(gar['mg_m'])}; o principal fator é "
                f"{_driver(gar['k'])}. Só vale entrar com parceria ou nicho. "
            )
        if emp:
            txt += (
                f"Em Empresarial a Akad tem {_pct(emp['s1'])} e margem de {_pct(emp['mg_a'])} contra {_pct(emp['mg_m'])}; "
                f"o principal fator é {_driver(emp['k'])}, ou seja, o custo de distribuir um produto novo e pequeno. "
                "Só faz sentido com um canal digital de PMEs de custo menor."
            )
        partes.append(txt)

    partes.append(
        "**Estratégia.** (1) Canais: manter o corretor como parceiro e usar a tecnologia da Akad (cotação e emissão "
        "digitais) para baixar o custo comercial onde ele pesa, em Empresarial e Transportes. (2) Subscrição e preço: "
        "dados e modelos para precificar por segmento, começando por Transportes. (3) Sinistros: regulação mais "
        "rápida e antifraude. (4) Resseguro: reavaliar a retenção em E&O (capital) e o custo da cessão em Garantia. "
        "(5) Infraestrutura e capital: garantir solvência para sustentar a retenção em E&O e o crescimento seletivo."
    )
    partes.append(
        "**Limites da análise.** Valores nominais; resultado técnico não é lucro contábil (sem despesa administrativa, "
        "imposto e resultado financeiro); o SES mostra o que aconteceu, não por quê. A recomendação é um julgamento a "
        "validar com dados internos de preço, comissão por canal e tratados de resseguro."
    )
    return _item("12", pergunta, curta, "\n\n".join(partes))


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------

def gerar(base: pd.DataFrame) -> list[dict]:
    """Q1–Q12 para a base recebida (já filtrada por LOB e ano)."""
    if base.empty:
        return [
            {"n": f"{i:02d}", "pergunta": "", "curta": "Sem dados.", "resposta": "Sem dados."}
            for i in range(1, 13)
        ]
    c = _Ctx(base)
    return [
        _q01(c), _q02(c), _q03(c), _q04(c), _q05(c), _q06(c),
        _q07(c), _q08(c), _q09(c), _q10(c), _q11(c), _q12(c),
    ]
