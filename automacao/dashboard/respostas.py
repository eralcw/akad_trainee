"""Respostas Q1–Q12 do case, escritas a partir dos dados filtrados.

Cada resposta é um dict {n, pergunta, curta, corpo, resposta}:
  - `curta`    uma frase direta, para destaque visual, legenda de gráfico e fala;
  - `corpo`    explicação detalhada em linguagem clara + tabela de apoio + cuidados;
  - `resposta` `**curta**` + `corpo` (usado no download em Markdown e no roteiro HTML).

Todo número vem da base recebida: se o usuário filtra LOBs ou anos, o texto muda
junto. As únicas partes fixas são o contexto de marca e a recomendação da Q12
(papel de cada LOB), que são julgamento de negócio, não resultado automático.

Método: sinistralidade e margem = razão de somas; resultado técnico = prêmio ganho
+ receita de resseguro − sinistro ocorrido − despesa de resseguro − despesa
comercial; ativa = prêmio ganho > 0; relevante = top 80% do prêmio acumulado.
"""

from __future__ import annotations

import math

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


def _pp_abs(v: float) -> str:
    """Diferença em pp sem sinal, para frases com 'acima/abaixo'."""
    if _nan(v):
        return "–"
    return f"{abs(v)*100:.1f} pp".replace(".", ",")


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
    corpo_limpo = corpo.strip()
    texto = f"**{curta}**" + (f"\n\n{corpo_limpo}" if corpo_limpo else "")
    return {"n": n, "pergunta": pergunta, "curta": curta, "corpo": corpo_limpo, "resposta": texto}


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
        self.fase_distinta = self.tem_fase and self.a0 < INICIO_FASE_AKAD

    def premio_ano(self, lob: str, ano: int, so_akad: bool = False) -> float:
        g = self.base[(self.base["lob"] == lob) & (self.base["ano"] == ano)]
        if so_akad:
            g = g[g["codigo_susep"] == AKAD]
        return float(g["premio_ganho"].sum())


# --------------------------------------------------------------------------
# Q1–Q3
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Perguntas literais do PDF do case
# --------------------------------------------------------------------------

PERGUNTAS = {
    "01": "Qual a LOB com maior prêmio no período inteiro (2020 a 2025)?",
    "02": "Qual a LOB com mais seguradoras ativas em 2020? E em 2025?",
    "03": "Qual a LOB com maior sinistralidade no período inteiro?",
    "04": "Qual a seguradora com maior sinistralidade no período em cada LOB?",
    "05": "Quanto foi o lucro (receitas – despesas) de cada LOB?",
    "06": "Quanto foi a margem (lucro/prêmio) de cada LOB?",
    "07": "Qual LOB teve o maior crescimento em prêmio no período, em porcentagem e em valor absoluto?",
    "08": "Quais são as seguradoras realmente relevantes de cada LOB? Como se comportam a margem e a sinistralidade delas em relação ao mercado inteiro?",
    "09": "Como é a tendência de sinistros e sinistralidade de cada LOB? Qual você considera mais saudável/atrativa?",
    "10": "Em quais LOBs a Akad é relevante? Como se comportou a posição dela no período? O que pode explicar as mudanças?",
    "11": "Considerando margem e sinistralidade, em quais LOBs a Akad é melhor que o mercado? E em relação a outras seguradoras do mesmo porte? E em relação às seguradoras relevantes?",
    "12": "Na sua opinião, em qual LOB a Akad deveria focar nos próximos anos? Qual deve ser a estratégia (considere aspectos como crescimento, lucratividade, canais de venda, infraestrutura e outros que julgar importantes)?",
}


def _bloco(porques=(), tabela: str = "", metodo: str = "", atencao: str | None = None, extra: str = "") -> str:
    """Monta o corpo no padrão: Por quê → tabela → método → atenção."""
    partes = ["_Por quê_", ""]
    partes += [f"- {p}" for p in porques if p]
    partes.append("")
    if tabela:
        partes += [tabela, ""]
    if extra:
        partes += [extra.strip(), ""]
    if metodo:
        partes.append(f"_Método:_ {metodo}")
    if atencao:
        partes.append(f"_Atenção:_ {atencao}")
    return "\n".join(partes).strip()


def _share_ano(base: pd.DataFrame, lob: str, ano: int, so_akad: bool = False) -> float:
    g = base[(base["lob"] == lob) & (base["ano"] == ano)]
    total = float(g["premio_ganho"].sum())
    if so_akad:
        total = float(g.loc[g["codigo_susep"] == AKAD, "premio_ganho"].sum())
    return total


# --------------------------------------------------------------------------
# Q1–Q3
# --------------------------------------------------------------------------

def _q01(c: _Ctx) -> dict:
    lob, total = c.lob, float(c.lob["premio"].sum())
    top = lob.index[0]
    share_top = lob.loc[top, "premio"] / total if total else math.nan
    s0 = c.premio_ano(top, c.a0)
    s1 = c.premio_ano(top, c.a1)
    t0 = sum(c.premio_ano(l, c.a0) for l in c.lobs)
    t1 = sum(c.premio_ano(l, c.a1) for l in c.lobs)
    p0 = s0 / t0 if t0 else math.nan
    p1 = s1 / t1 if t1 else math.nan

    curta = (
        f"{top} lidera, com {A.f_bi(lob.loc[top, 'premio'])} de prêmio ganho "
        f"em {c.periodo} ({_pct(share_top, 0)} das {len(lob)} LOBs)."
    )
    porques = []
    if len(lob) > 1:
        seg = lob.index[1]
        porques.append(f"{seg} vem em segundo, com {A.f_bi(lob.loc[seg, 'premio'])}.")
        menor = lob.index[-1]
        porques.append(f"{menor} é a menor, com {A.f_bi(lob.loc[menor, 'premio'])}.")
    if c.a0 != c.a1:
        porques.append(
            f"A participação de {top} no prêmio das LOBs foi de {_pct(p0)} em {c.a0} "
            f"para {_pct(p1)} em {c.a1}."
        )
    tabela = _tabela(
        ["LOB", "Prêmio ganho", "% do total"],
        [[l, A.f_bi(r["premio"]), _pct(r["premio"] / total if total else math.nan)] for l, r in lob.iterrows()],
    )
    return _item(
        "01", PERGUNTAS["01"], curta,
        _bloco(
            porques, tabela,
            metodo="soma do prêmio ganho de 2020 a 2025, em valores nominais.",
            atencao="ser a maior em prêmio não significa ser a mais lucrativa; veja a Q5.",
        ),
    )


def _q02(c: _Ctx) -> dict:
    atv = A.ativas_por_ano(c.base, "premio")        # prêmio > 0
    pres = A.ativas_por_ano(c.base, "presenca")     # qualquer linha
    mat = (
        c.base[c.base["premio_ganho"] >= 1_000_000]
        .groupby(["lob", "ano"]).codigo_susep.nunique().unstack()
    )
    a0, a1 = c.a0, c.a1
    l0, l1 = atv[a0].idxmax(), atv[a1].idxmax()
    n0, n1 = int(atv[a0].max()), int(atv[a1].max())
    if a0 == a1:
        curta = f"{l0} tem mais seguradoras ativas em {a0}: {n0}."
    elif l0 == l1:
        curta = f"{l0} lidera nos dois anos: {n0} ativas em {a0} e {n1} em {a1}."
    else:
        curta = f"{l0} lidera em {a0} ({n0}) e {l1} em {a1} ({n1})."

    porques = []
    if a0 != a1:
        var = (atv[a1] - atv[a0]).sort_values(ascending=False)
        quem = var.index[0]
        sinal = "ganhou" if var.iloc[0] > 0 else "perdeu"
        porques.append(f"{quem} {sinal} {abs(int(var.iloc[0]))} concorrentes ativos no período.")
    menor = atv[a1].idxmin()
    top5 = c.conc.loc[menor, "top5"] if menor in c.conc.index else math.nan
    porques.append(
        f"{menor} tem o menor grupo ({int(atv.loc[menor, a1])}) e a maior concentração: "
        f"as 5 maiores somam {_pct(top5)} do prêmio."
    )
    if not mat.empty and a0 in mat.columns and a1 in mat.columns:
        ml0, ml1 = mat[a0].idxmax(), mat[a1].idxmax()
        if ml0 == ml1:
            porques.append(
                f"Com piso de materialidade (prêmio ≥ R$ 1 mi no ano), {ml0} lidera em "
                f"{a0} ({int(mat.loc[ml0, a0])}) e em {a1} ({int(mat.loc[ml0, a1])})."
            )
        else:
            porques.append(
                f"Com piso de R$ 1 mi de prêmio, o líder muda: {ml0} em {a0} e {ml1} em {a1}."
            )
    pl0 = pres[a0].idxmax()
    tabela = _tabela(
        ["LOB", f"Ativas {a0}", f"Ativas {a1}", "Variação"],
        [[l, int(atv.loc[l, a0]), int(atv.loc[l, a1]), f"{int(atv.loc[l, a1] - atv.loc[l, a0]):+d}"] for l in c.lobs],
    )
    return _item(
        "02", PERGUNTAS["02"], curta,
        _bloco(
            porques, tabela,
            metodo="ativa = seguradora com prêmio ganho maior que zero no ano.",
            atencao=(
                f"contando todas as empresas listadas no SES, inclusive as sem venda, "
                f"{pl0} lideraria em {a0}."
            ),
        ),
    )


def _q03(c: _Ctx) -> dict:
    d = c.lob.sort_values("sinistralidade", ascending=False)
    top = d.index[0]
    segundo = d.index[1] if len(d) > 1 else None
    curta = f"{top} lidera, com {_pct(d.loc[top, 'sinistralidade'])}"
    if segundo:
        gap = d.loc[top, "sinistralidade"] - d.loc[segundo, "sinistralidade"]
        if gap < 0.005:
            curta += f", praticamente empatada com {segundo} ({_pct(d.loc[segundo, 'sinistralidade'])})."
        else:
            curta += f"; {segundo} vem depois, com {_pct(d.loc[segundo, 'sinistralidade'])}."
    else:
        curta += "."

    porques = []
    if c.a0 != c.a1 and top in c.lob_ano["lob"].values:
        serie = c.lob_ano[c.lob_ano["lob"] == top].set_index("ano")["sinistralidade"]
        pior_ano = serie.idxmax()
        porques.append(
            f"{top} depende de {int(pior_ano)}: naquele ano a sinistralidade foi de "
            f"{_pct(serie.loc[pior_ano])}."
        )
        sem = c.base[c.base["ano"] != pior_ano]
        if not sem.empty:
            d_sem = A.por_lob(sem).set_index("lob")["sinistralidade"].sort_values(ascending=False)
            novo = d_sem.index[0]
            porques.append(
                f"Sem {int(pior_ano)}, {top} cairia para {_pct(d_sem.get(top, math.nan))} e "
                f"{novo} passaria a ser a maior, com {_pct(d_sem.loc[novo])}."
            )
    if len(d) > 1:
        menor = d.index[-1]
        porques.append(f"{menor} tem a menor sinistralidade: {_pct(d.loc[menor, 'sinistralidade'])}.")

    tabela = _tabela(
        ["LOB", "Sinistro ocorrido", "Prêmio ganho", "Sinistralidade"],
        [[l, A.f_bi(r["sinistro"]), A.f_bi(r["premio"]), _pct(r["sinistralidade"])] for l, r in d.iterrows()],
    )
    return _item(
        "03", PERGUNTAS["03"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "soma dos sinistros ÷ soma dos prêmios ganhos no período (razão de somas, "
                "não média das razões anuais)."
            ),
        ),
    )


# --------------------------------------------------------------------------
# Q4
# --------------------------------------------------------------------------

def q4_curta(base: pd.DataFrame, min_share: float = 0.01) -> str:
    tab = A.q4(base, min_share=min_share, top=1)
    if tab.empty:
        return "Sem seguradoras acima do corte."
    partes = [
        f"{r['lob']}: {A.nome_curto(r['seguradora'])} ({_pct(r['sinistralidade'], 0)})"
        for _, r in tab.iterrows()
    ]
    extremos = tab.nlargest(2, "sinistralidade")
    nomes = " e ".join(
        f"{A.nome_curto(r.seguradora)} em {r.lob} ({_pct(r.sinistralidade, 0)})"
        for r in extremos.itertuples()
    )
    if len(tab) > 2:
        return f"Com corte de {_pct(min_share, 0)} de participação, os extremos são {nomes}; veja a tabela."
    return f"Com corte de {_pct(min_share, 0)}: " + "; ".join(partes) + "."


def _q04(c: _Ctx) -> dict:
    com = A.q4(c.base, min_share=0.01, top=1).set_index("lob")
    sem = A.q4(c.base, min_share=0.0, top=1).set_index("lob")
    curta = q4_curta(c.base, 0.01)

    porques = []
    if not sem.empty:
        extremo = sem.sort_values("sinistralidade", ascending=False).iloc[0]
        porques.append(
            f"Sem corte, o ranking é dominado por empresas quase sem prêmio: "
            f"{A.nome_curto(extremo['seguradora'])} tem {_pct(extremo['sinistralidade'], 0)} "
            f"sobre {A.f_din(extremo['premio'])} de prêmio."
        )
    altos = com.sort_values("sinistralidade", ascending=False).head(2)
    for lob_nome, r in altos.iterrows():
        g = c.base[(c.base["lob"] == lob_nome) & (c.base["codigo_susep"] == r["codigo_susep"])]
        agg = g[g["premio_ganho"] > 0].groupby("ano")[["sinistro_ocorrido", "premio_ganho"]].sum()
        por_ano = (agg["sinistro_ocorrido"] / agg["premio_ganho"]).replace([math.inf, -math.inf], math.nan).dropna()
        if not por_ano.empty:
            pior = por_ano.idxmax()
            porques.append(
                f"{A.nome_curto(r['seguradora'])} ({lob_nome}) tem {_pct(r['sinistralidade'], 0)} no período; "
                f"o pior ano é {int(pior)}, com {_pct(por_ano.loc[pior], 0)}."
            )

    linhas = []
    for l in c.lobs:
        if l not in com.index or l not in sem.index:
            continue
        a, b = com.loc[l], sem.loc[l]
        linhas.append([
            l, A.nome_curto(a["seguradora"]), _pct(a["sinistralidade"], 0), _pct(a["share"]),
            A.nome_curto(b["seguradora"]), _pct(b["sinistralidade"], 0), A.f_din(b["premio"]),
        ])
    tabela = _tabela(
        ["LOB", "Com corte ≥ 1%", "Sinistr.", "Participação", "Sem corte", "Sinistr.", "Prêmio"],
        linhas, esq={0, 1, 4},
    )
    return _item(
        "04", PERGUNTAS["04"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "sinistros ÷ prêmio de cada seguradora, somados em 2020–2025; o corte de 1% "
                "exige participação mínima no prêmio da LOB."
            ),
            atencao=(
                "sinistralidade negativa tipicamente reflete reversão de reserva ou recuperação "
                "de salvados, não erro de dado."
            ),
        ),
    )


# --------------------------------------------------------------------------
# Q5–Q7
# --------------------------------------------------------------------------

def _q05(c: _Ctx) -> dict:
    d = c.lob.sort_values("lucro", ascending=False)
    top = d.index[0]
    total = float(d["lucro"].sum())
    pos = int(c.lob["premio"].rank(ascending=False).loc[top])
    curta = f"As {len(d)} LOBs somam {A.f_bi(total)} de lucro; {top} lidera com {A.f_bi(d.loc[top, 'lucro'])}"
    if len(d) > 1 and pos != 1:
        curta += f", mesmo sendo a {pos}ª em prêmio."
    else:
        curta += "."

    g = c.base[c.base["lob"] == top]
    p = float(g["premio_ganho"].sum())
    rr = float(g["receita_resseguro"].sum())
    so = float(g["sinistro_ocorrido"].sum())
    dr = float(g["despesa_resseguro"].sum())
    dc = float(g["despesa_comercial"].sum())
    formula = (
        f"{A.f_bi(p)} + {A.f_bi(rr)} − {A.f_bi(so)} − {A.f_bi(dr)} − {A.f_bi(dc)} "
        f"= {A.f_bi(p + rr - so - dr - dc)}"
    )
    porques = [
        f"{top} tem {_pct(d.loc[top, 'sinistralidade'])} de sinistralidade.",
        f"{d.index[-1]} fatura {A.f_bi(d.loc[d.index[-1], 'premio'])}, mas lucra {A.f_bi(d.loc[d.index[-1], 'lucro'])}.",
    ]
    tabela = _tabela(
        ["LOB", "Lucro", "% do total", "Prêmio ganho"],
        [[l, A.f_bi(r["lucro"]), _pct(r["lucro"] / total if total else math.nan), A.f_bi(r["premio"])] for l, r in d.iterrows()],
    )
    return _item(
        "05", PERGUNTAS["05"], curta,
        _bloco(
            porques, tabela,
            metodo=f"lucro = prêmio ganho + receita de resseguro − sinistro − despesa de resseguro − despesa comercial. Em {top}: {formula}.",
            atencao="é o lucro da operação de seguro; não inclui despesas administrativas, impostos nem resultado financeiro.",
        ),
    )


def _q06(c: _Ctx) -> dict:
    d = c.lob.sort_values("margem", ascending=False)
    top, bot = d.index[0], d.index[-1]
    curta = f"{top} tem a maior margem ({_pct(d.loc[top, 'margem'])}) e {bot} a menor ({_pct(d.loc[bot, 'margem'])})."

    comp = {l: A.componentes(c.base[c.base["lob"] == l]) for l in d.index}
    porques = []
    if len(d) > 1:
        contrib = {k: -(comp[top][k] - comp[bot][k]) for k in ("sin", "resseg", "com")}
        ajuda = [f"{NOME_COMPONENTE[k]} ({A.f_pp(v)})" for k, v in contrib.items() if v > 0]
        contra = [f"{NOME_COMPONENTE[k]} ({A.f_pp(v)})" for k, v in contrib.items() if v < 0]
        frase = f"A vantagem de {A.f_pp(d.loc[top, 'margem'] - d.loc[bot, 'margem'])} de {top} sobre {bot}"
        if ajuda:
            frase += f" vem de {_lista(ajuda)}"
        if contra:
            frase += f"; {_lista(contra)} joga contra"
        porques.append(frase + ".")
    terceira = d.index[1] if len(d) > 1 else None
    if terceira:
        resseg = comp[terceira]["resseg"]
        porques.append(
            f"{terceira} tem {_pct(comp[terceira]['sin'])} de sinistralidade, mas o resseguro "
            f"líquido consome {_pct(abs(resseg))} do prêmio; a margem fica em {_pct(comp[terceira]['margem'])}."
        )

    tabela = _tabela(
        ["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Margem"],
        [[l, _pct(comp[l]["sin"]), _pct(comp[l]["resseg"]), _pct(comp[l]["com"]), _pct(comp[l]["margem"])] for l in d.index],
    )

    # margem por ano
    linhas = []
    for l in c.lobs:
        g = c.lob_ano[c.lob_ano["lob"] == l].set_index("ano")
        linha = [l]
        for ano in c.anos:
            linha.append(_pct(g.loc[ano, "margem"]) if ano in g.index else "–")
        linhas.append(linha)
    tabela_ano = _tabela(["LOB"] + [str(a) for a in c.anos], linhas)

    extra = "Margem por ano:\n\n" + tabela_ano
    return _item(
        "06", PERGUNTAS["06"], curta,
        _bloco(
            porques, tabela,
            metodo="margem = lucro ÷ prêmio ganho = 100% − sinistralidade − resseguro líquido − despesa comercial.",
            atencao="resseguro líquido = despesa com resseguro − receita com resseguro; quando negativo, a recuperação superou o custo.",
            extra=extra,
        ),
    )


def _q07(c: _Ctx) -> dict:
    if c.cresc.empty:
        return _item("07", PERGUNTAS["07"], "Selecione pelo menos dois anos para calcular crescimento.")
    d = c.cresc
    pct_top = d["pct"].idxmax()
    abs_top = d["abs"].idxmax()
    if pct_top == abs_top:
        curta = f"{pct_top} lidera nos dois critérios: {_pct(d.loc[pct_top, 'pct'])} e +{A.f_bi(d.loc[pct_top, 'abs'])}."
    else:
        curta = (
            f"Em porcentagem, {pct_top} ({_pct(d.loc[pct_top, 'pct'])}); "
            f"em valor absoluto, {abs_top} (+{A.f_bi(d.loc[abs_top, 'abs'])})."
        )

    porques = []
    if pct_top != abs_top:
        vezes = d.loc[abs_top, "primeiro"] / d.loc[pct_top, "primeiro"] if d.loc[pct_top, "primeiro"] else math.inf
        vezes_txt = f"{vezes:.1f}".replace(".", ",") if math.isfinite(vezes) else "muitas"
        porques.append(
            f"{pct_top} partiu de {A.f_bi(d.loc[pct_top, 'primeiro'])} em {int(d.loc[pct_top, 'ano_ini'])}."
        )
        porques.append(
            f"{abs_top} cresceu menos em porcentagem, mas sobre uma base cerca de {vezes_txt} vezes maior."
        )
    if "cagr" in d.columns:
        cagr_top = d["cagr"].idxmax()
        porques.append(f"No ritmo médio anual (CAGR), {cagr_top} lidera, com {_pct(d.loc[cagr_top, 'cagr'])}.")

    tabela = _tabela(
        ["LOB", f"Prêmio {c.a0}", f"Prêmio {c.a1}", "Variação R$", "Variação %", "Crescimento ao ano"],
        [
            [l, A.f_bi(r["primeiro"]), A.f_bi(r["ultimo"]), A.f_bi(r["abs"]), _pct(r["pct"]), _pct(r["cagr"])]
            for l, r in d.sort_values("pct", ascending=False).iterrows()
        ],
    )
    return _item(
        "07", PERGUNTAS["07"], curta,
        _bloco(
            porques, tabela,
            metodo="variação de 2025 contra 2020; crescimento ao ano = taxa média composta (CAGR).",
            atencao="valores nominais: parte do crescimento é inflação. O SES não publica IPCA, então não há deflação na base.",
        ),
    )

# --------------------------------------------------------------------------
# Q8
# --------------------------------------------------------------------------

def _q08(c: _Ctx) -> dict:
    linhas, cauda_linhas = [], []
    maiores_gaps = []
    n80s = []
    for l in c.lobs:
        mesa, n, mercado = A.relevantes(c.base, l)
        if mesa.empty:
            continue
        n80s.append(n)
        codigos = set(mesa["codigo_susep"])
        relev = c.base[(c.base["lob"] == l) & (c.base["codigo_susep"].isin(codigos))]
        resto = c.base[(c.base["lob"] == l) & (~c.base["codigo_susep"].isin(codigos))]
        mr, mc = A.metricas(resto), A.metricas(relev)
        if not resto.empty:
            cauda_linhas.append([
                l, int(len(resto)), A.f_bi(mr["premio"]),
                _pct(mr["sinistralidade"]), _pct(mr["margem"]),
                A.f_pp(mr["sinistralidade"] - mc["sinistralidade"]),
                A.f_pp(mr["margem"] - mc["margem"]),
            ])
        for _, r in mesa.sort_values("premio", ascending=False).iterrows():
            linhas.append([
                l, A.nome_curto(r["seguradora"]), _pct(r["share"]),
                _pct(r["sinistralidade"]), _pct(r["margem"]),
                A.f_pp(r["sinistralidade"] - mercado["sinistralidade"]),
                A.f_pp(r["margem"] - mercado["margem"]),
            ])
        if len(mesa) > 1:
            acima = mesa.loc[(mesa["sinistralidade"] - mercado["sinistralidade"]).idxmax()]
            abaixo = mesa.loc[(mesa["sinistralidade"] - mercado["sinistralidade"]).idxmin()]
            maiores_gaps.append(
                (l, A.nome_curto(acima["seguradora"]),
                 acima["sinistralidade"] - mercado["sinistralidade"],
                 A.nome_curto(abaixo["seguradora"]),
                 abaixo["sinistralidade"] - mercado["sinistralidade"])
            )

    if not linhas:
        return _item("08", PERGUNTAS["08"], "Sem seguradoras com prêmio positivo.")

    maiores_gaps.sort(key=lambda x: abs(x[2]), reverse=True)
    l0, nome_alto, d_alto, nome_baixo, d_baixo = maiores_gaps[0]
    curta = (
        f"De {min(n80s)} a {max(n80s)} seguradoras concentram 80% do prêmio de cada LOB; "
        f"em {l0}, {nome_baixo} opera {_pp_abs(d_baixo)} abaixo do mercado e {nome_alto} "
        f"{_pp_abs(d_alto)} acima."
    )

    porques = []
    for l, alto, d1, baixo, d2 in maiores_gaps[:3]:
        porques.append(
            f"{l}: {baixo} tem sinistralidade {_pp_abs(d2)} abaixo do mercado; "
            f"{alto}, {_pp_abs(d1)} acima."
        )
    porques.append(
        "Em bloco, as relevantes têm indicadores próximos do mercado, porque somam 80% dele; "
        "o contraste útil é contra a cauda de 20%."
    )

    tabela = _tabela(
        ["LOB", "Seguradora", "Participação", "Sinistralidade", "Margem", "Δ sin.", "Δ margem"],
        linhas, esq={0, 1},
    )
    tabela_cauda = _tabela(
        ["LOB", "Seguradoras na cauda", "Prêmio", "Sinistralidade", "Margem", "Δ sin.", "Δ margem"],
        cauda_linhas, esq={0},
    )
    extra = "Relevantes contra a cauda (as que ficam fora dos 80%):\n\n" + tabela_cauda

    return _item(
        "08", PERGUNTAS["08"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "relevantes = as maiores seguradoras que, somadas em ordem de prêmio, chegam a "
                "80% da LOB; Δ compara cada uma com o mercado inteiro da LOB, em pontos percentuais."
            ),
            atencao="a lista completa, com busca e gráfico, está na aba Concorrência.",
            extra=extra,
        ),
    )


# --------------------------------------------------------------------------
# Q9
# --------------------------------------------------------------------------

def _rotulo_tendencia(slope: float, vol: float = math.nan, anos: int = 0) -> str:
    if _nan(slope):
        return "–"
    if anos > 1 and not _nan(vol) and abs(slope) * (anos - 1) < vol:
        return f"sem tendência clara ({A.f_pp(slope)}/ano)"
    if slope < -0.005:
        return f"queda de {A.f_pp(-slope)}/ano"
    if slope > 0.005:
        return f"alta de {A.f_pp(slope)}/ano"
    return "estável"


def _q09(c: _Ctx) -> dict:
    t = c.trend.loc[[l for l in c.lobs if l in c.trend.index]]
    if len(t) == 0:
        return _item("09", PERGUNTAS["09"], "Sem dados suficientes.")

    span = c.a1 - c.a0
    pior = {}
    for l in t.index:
        g = c.lob_ano[(c.lob_ano["lob"] == l)].dropna(subset=["sinistralidade"])
        if not g.empty:
            r = g.loc[g["sinistralidade"].idxmax()]
            pior[l] = (int(r["ano"]), float(r["sinistralidade"]))

    menor_nivel = c.lob["sinistralidade"].idxmin()
    atrativa = c.lob["margem"].idxmax() if not c.cresc.empty else menor_nivel
    if not c.cresc.empty and c.cresc["pct"].idxmax() != atrativa:
        atrativa = c.lob["margem"].idxmax()
    curta = f"{menor_nivel} tem o menor risco, com sinistralidade de {_pct(c.lob.loc[menor_nivel, 'sinistralidade'])}."
    if atrativa != menor_nivel:
        slope_atr = t.loc[atrativa, "slope"] if atrativa in t.index else math.nan
        if _nan(slope_atr):
            qual = "sem tendência clara"
        elif slope_atr < -0.005:
            qual = "em queda"
        elif slope_atr > 0.005:
            qual = "em alta"
        else:
            qual = "estável"
        curta += f" {atrativa} é a mais atrativa: maior margem e sinistralidade {qual}."

    porques = []
    melhora = [l for l in t.index if not _nan(t.loc[l, "slope"]) and t.loc[l, "slope"] < -0.005
               and abs(t.loc[l, "slope"]) * max(span, 1) >= t.loc[l, "vol"]]
    piora = [l for l in t.index if not _nan(t.loc[l, "slope"]) and t.loc[l, "slope"] > 0.005
             and abs(t.loc[l, "slope"]) * max(span, 1) >= t.loc[l, "vol"]]
    semtend = [l for l in t.index if l not in melhora and l not in piora]
    if melhora:
        porques.append(f"A sinistralidade cai de forma consistente em {_lista(melhora)}.")
    if piora:
        porques.append(f"Sobe em {_lista(piora)}.")
    if semtend:
        porques.append(f"Sem tendência clara em {_lista(semtend)}: a oscilação anual é maior que a inclinação da reta.")
    t_vol = t.dropna(subset=["vol"])
    if len(t_vol) > 1:
        vol_max = t_vol["vol"].idxmax()
        porques.append(
            f"{vol_max} é a mais instável: oscila {_pct(t_vol.loc[vol_max, 'vol'])} de um ano para outro"
            + (f" e chegou a {_pct(pior[vol_max][1])} em {pior[vol_max][0]}" if vol_max in pior else "")
            + "."
        )
        estavel = t_vol["vol"].idxmin()
        porques.append(f"{estavel} é a mais previsível, mas fica sempre perto de {_pct(c.lob.loc[estavel, 'sinistralidade'])}.")

    tabela = _tabela(
        ["LOB", "Sinistralidade do período", "Tendência", "Oscilação anual", "Pior ano"],
        [
            [
                l,
                _pct(c.lob.loc[l, "sinistralidade"]),
                _rotulo_tendencia(r["slope"], r["vol"], max(span, 1)),
                _pct(r["vol"]),
                f"{pior[l][0]} ({_pct(pior[l][1])})" if l in pior else "–",
            ]
            for l, r in t.sort_values("sin_media").iterrows()
        ],
        esq={0, 2, 4},
    )

    # matriz de atratividade com pesos iguais
    ranks = pd.DataFrame(index=t.index)
    ranks["Margem"] = c.lob.loc[t.index, "margem"].rank(ascending=False)
    ranks["Sinistralidade"] = c.lob.loc[t.index, "sinistralidade"].rank(ascending=True)
    if not c.cresc.empty:
        ranks["Crescimento"] = c.cresc.loc[[l for l in t.index if l in c.cresc.index], "pct"].rank(ascending=False)
    ranks["Média"] = ranks.mean(axis=1)
    tabela_rank = _tabela(
        ["LOB"] + list(ranks.columns),
        [[l] + [f"{v:.1f}".replace(".", ",") for v in row] for l, row in ranks.iterrows()],
        esq={0},
    )
    extra = (
        "Critérios da LOB mais atrativa (1 = melhor em cada critério, pesos iguais):\n\n"
        + tabela_rank
    )

    return _item(
        "09", PERGUNTAS["09"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "sinistralidade do período por razão de somas; tendência = inclinação da reta da "
                "sinistralidade anual; oscilação = desvio-padrão anual. Quando a inclinação vezes "
                "o número de anos fica abaixo do desvio, a tendência é tratada como não clara."
            ),
            atencao="a média simples dos anos aparece só na tendência e na oscilação; o nível do período é a razão de somas.",
            extra=extra,
        ),
    )


# --------------------------------------------------------------------------
# Q10
# --------------------------------------------------------------------------

def _margem_akad_ano(base: pd.DataFrame, lob: str, ano: int) -> float:
    g = base[(base["lob"] == lob) & (base["ano"] == ano) & (base["codigo_susep"] == AKAD)]
    return A.metricas(g)["margem"] if not g.empty else math.nan


def _q10(c: _Ctx) -> dict:
    if c.akad.empty:
        return _item("10", PERGUNTAS["10"], "A Akad não aparece nas LOBs selecionadas.")
    ak = c.akad.loc[[l for l in c.lobs if l in c.akad.index]]
    a0, a1 = c.a0, c.a1

    def peso(r) -> bool:
        return (not _nan(r["rank1"]) and r["rank1"] <= 5) or r["share1"] >= 0.05

    rel = [l for l, r in ak.iterrows() if peso(r)]
    sub = [l for l in ak.index if l not in rel]

    def desc(l: str) -> str:
        r = ak.loc[l]
        pos = f", {int(r['rank1'])}ª" if not _nan(r["rank1"]) else ""
        return f"{_pct(r['share1'])}{pos}"

    rel_ord = sorted(rel, key=lambda x: ak.loc[x, "share1"], reverse=True)
    curta = f"A Akad é relevante em {_lista([f'{l} ({desc(l)})' for l in rel_ord])}"
    if sub:
        curta += f"; nas demais é subescala: {_lista([f'{l} ({desc(l)})' for l in sub])}"
    curta += "."

    tr = ak.loc["Transportes"] if "Transportes" in ak.index else None
    if tr is not None and a0 != a1:
        m0 = _margem_akad_ano(c.base, "Transportes", a0)
        m1 = _margem_akad_ano(c.base, "Transportes", a1)
        if not _nan(m0) and not _nan(m1):
            curta = (
                f"A Akad é relevante em {_lista([f'{l} ({desc(l)})' for l in rel_ord])}; "
                f"em Transportes, cresceu {_x(_mult(tr['premio0'], tr['premio1']))} "
                f"enquanto a margem caiu de {_pct(m0)} para {_pct(m1)}."
            )

    porques = []
    linhas = []
    for l, r in ak.iterrows():
        porques_l = None
        linhas.append([
            l, A.f_mi(r["premio0"]), A.f_mi(r["premio1"]), _pct(r["share0"]), _pct(r["share1"]),
            f"{int(r['rank0'])}ª" if not _nan(r["rank0"]) else "–",
            f"{int(r['rank1'])}ª" if not _nan(r["rank1"]) else "–",
        ])

    melhorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] < r["rank0"]]
    if melhorou:
        porques.append(f"A posição sobe em {len(melhorou)} de {len(ak)} LOBs ({_lista(melhorou)}).")
    if "E&O" in ak.index:
        eo = ak.loc["E&O"]
        porques.append(
            f"Em E&O, a Akad é a {int(eo['rank1'])}ª, com {_pct(eo['share1'])} de participação."
        )
    if tr is not None:
        tot_ak = sum(c.premio_ano(x, c.a1, True) for x in ak.index)
        mix_tr = c.premio_ano("Transportes", c.a1, True) / tot_ak if tot_ak else math.nan
        porques.append(
            f"Transportes é {_pct(tr['share1'])} da LOB e {_pct(mix_tr, 0)} do prêmio da Akad."
        )

    # 2021: último ano da Argo
    if 2021 in c.base["ano"].values:
        g21 = c.base[(c.base["ano"] == 2021) & (c.base["codigo_susep"] == AKAD)]
        if not g21.empty:
            agg = g21.groupby("lob")[["sinistro_ocorrido", "premio_ganho"]].sum()
            ratio = (agg["sinistro_ocorrido"] / agg["premio_ganho"]).dropna().sort_values(ascending=False)
            if not ratio.empty:
                piores = [f"{_pct(v)} em {l}" for l, v in ratio.head(3).items()]
                porques.append(
                    "Em 2021, último ano antes da marca, a sinistralidade era de " + _lista(piores) + "."
                )

    tabela = _tabela(
        ["LOB", f"Prêmio {a0}", f"Prêmio {a1}", f"Participação {a0}", f"Participação {a1}",
         f"Posição {a0}", f"Posição {a1}"],
        linhas,
    )
    contexto = (
        "Aquisição anunciada em 2021 e concluída em 2022 (GP Investments e CyberLabs); "
        "a marca Akad existe desde junho de 2022. O código SUSEP 02798 é o mesmo da Argo, "
        "então a série é contínua."
    )
    hipotese = (
        "Uma explicação provável para a mudança de patamar: a carteira herdada tinha sinistralidade "
        "alta em 2021 e foi reprecificada na virada; a partir de 2022, a nova subscrição e o foco em "
        "corretores digitais mudaram o perfil. Para confirmar a causa, seriam necessários dados internos."
    )
    return _item(
        "10", PERGUNTAS["10"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "relevante aqui = estar entre as 5 maiores em prêmio ou ter pelo menos 5% da LOB; "
                f"critério mais exigente que o top 80% da Q8, porque a pergunta é sobre peso competitivo. {contexto}"
            ),
            atencao=hipotese,
        ),
    )


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
        [
            l, _pct(r["akad_mg"]), _pct(r["mercado_mg"]),
            f"{_pct(r['peers_mg'])} ({int(r['peers_n'])})",
            f"{_pct(r['relev_mg'])} ({int(r['relev_n'])})",
            _pct(r["akad_sin"]), _pct(r["mercado_sin"]), _pct(r["peers_sin"]), _pct(r["relev_sin"]),
        ]
        for l, r in comp.iterrows()
    ]
    return _tabela(
        ["LOB", "Margem Akad", "Mercado", "Pares (n)", "Relevantes (n)",
         "Sinistr. Akad", "Sinistr. mercado", "Sinistr. pares", "Sinistr. relevantes"],
        linhas,
    )


def _comparacao(base: pd.DataFrame, lobs: list[str]) -> pd.DataFrame:
    comp = A.comparacao_akad(base)
    if comp.empty:
        return comp
    comp = comp.set_index("lob")
    return comp.loc[[l for l in lobs if l in comp.index]]


def _contribuicoes(df: pd.DataFrame, lob: str) -> dict:
    g = df[df["lob"] == lob]
    a, m = A.componentes(g[g["codigo_susep"] == AKAD]), A.componentes(g)
    out = {k: -(a[k] - m[k]) for k in ("sin", "resseg", "com")}
    out["total"] = a["margem"] - m["margem"]
    return out


def _driver(contrib: dict) -> str:
    k = max(("sin", "resseg", "com"), key=lambda x: abs(contrib[x]) if not _nan(contrib[x]) else 0)
    return f"{NOME_COMPONENTE[k]} ({A.f_pp(contrib[k])})"


def _q11(c: _Ctx) -> dict:
    comp = _comparacao(c.base, c.lobs)
    if comp.empty:
        return _item("11", PERGUNTAS["11"], "A Akad não aparece nas LOBs selecionadas.")

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
            f"{l}: margem {_frase(r['akad_mg'], mg, False)}; "
            f"sinistralidade {_frase(r['akad_sin'], sn, True)}."
        )

    partes = []
    if consistentes:
        partes.append(f"supera mercado, pares e relevantes em margem em {_lista(consistentes)}")
    if abaixo:
        partes.append(f"fica atrás dos três em margem em {_lista(abaixo)}")
    if mistas:
        partes.append(f"tem resultado misto em {_lista(mistas)}")
    curta = "A Akad " + "; ".join(partes) + "."

    # fase Akad como tabela principal
    comp_f = _comparacao(c.fase, c.lobs) if c.tem_fase else comp
    tabela = _tabela_comparacao(comp_f)
    corpo_extra = ""

    # decomposição (fase Akad)
    ref = c.fase if c.tem_fase else c.base
    ref_rot = c.fase_rotulo if c.tem_fase else c.periodo
    linhas, notas, lobs_resseg = [], [], []
    for l in comp.index:
        k = _contribuicoes(ref, l)
        if any(_nan(k[x]) for x in k):
            continue
        linhas.append([l, A.f_pp(k["sin"]), A.f_pp(k["resseg"]), A.f_pp(k["com"]), A.f_pp(k["total"])])
        notas.append(f"{l}: {A.f_pp(k['total'])}, puxado por {_driver(k)}")
        if k["resseg"] > 0:
            lobs_resseg.append(l)
    if linhas:
        corpo_extra = (
            f"De onde vem a diferença de margem ({ref_rot}): contribuição de cada componente, "
            "em pontos percentuais do prêmio; positivo ajuda a Akad.\n\n"
            + _tabela(["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Diferença de margem"], linhas)
            + "\n\n" + "\n".join(f"- {n}." for n in notas)
        )

    # pares: mediana e n (para o caso de distorção)
    nota_pares = ""
    if c.tem_fase:
        piores = []
        for l in comp_f.index:
            g = c.fase[c.fase["lob"] == l]
            ult = g[g["ano"] == c.f1].groupby("codigo_susep").premio_ganho.sum()
            alvo = ult.get(AKAD, 0)
            peers = [x for x in ult[(ult >= alvo / 3) & (ult <= alvo * 3)].index if x != AKAD]
            seg = A.por_seguradora(g[g["codigo_susep"].isin(peers)])
            if len(seg) >= 3:
                med = seg["sinistralidade"].median()
                if abs(med - comp_f.loc[l, "peers_sin"]) > 0.05:
                    piores.append((l, med, comp_f.loc[l, "peers_sin"]))
        if piores:
            nota_pares = "Mediana dos pares muito diferente da média ponderada: " + "; ".join(
                f"{l} tem mediana de {_pct(med)} contra {_pct(pond)} da média"
                for l, med, pond in piores
            ) + ". Poucos pares pequenos ou em run-off distorcem a média."

    nota_resseg = ""
    if lobs_resseg:
        nota_resseg = (
            f"O resseguro líquido ajuda a margem em {_lista(lobs_resseg)}; nesses casos, a Akad cede "
            "menos risco, o que eleva a margem nos anos bons e aumenta a volatilidade."
        )

    porques = veredito[:3]
    if nota_resseg:
        porques.append(nota_resseg)
    if nota_pares:
        porques.append(nota_pares)

    extra = f"Período completo ({c.periodo}), para referência:\n\n" + _tabela_comparacao(comp)
    return _item(
        "11", PERGUNTAS["11"], curta,
        _bloco(
            porques, tabela,
            metodo=(
                "pares = seguradoras com prêmio entre 1/3 e 3 vezes o da Akad no último ano; "
                "relevantes = as que somam 80% da LOB; diferenças de até 1 pp contam como em linha."
            ),
            atencao="a tabela principal usa a fase Akad (2022 em diante); o período completo aparece no fim.",
            extra=corpo_extra + "\n\n" + extra,
        ),
    )


# --------------------------------------------------------------------------
# Q12
# --------------------------------------------------------------------------

PAPEL = {
    "E&O": ("Núcleo", "defender e expandir"),
    "Transportes": ("Corrigir", "rentabilizar antes de crescer"),
    "RCG": ("Aposta seletiva", "crescer em nicho, com limite de exposição"),
    "Garantia": ("Opcional", "manter em nicho e rever o resseguro"),
    "Empresarial": ("Opcional", "manter o tamanho até a margem melhorar"),
}


def _q12(c: _Ctx) -> dict:
    if not c.tem_fase:
        return _item(
            "12", PERGUNTAS["12"],
            "A fase Akad começa em 2022. Selecione pelo menos um ano de 2022 em diante.",
            _bloco(
                ["A marca Akad foi criada em junho de 2022, depois da compra concluída em 2022."],
                metodo="sem anos de 2022 em diante, não há base para recomendar foco com a estratégia atual.",
            ),
        )

    fase = c.fase
    lobs = [l for l in c.lobs if not fase[(fase["lob"] == l) & (fase["codigo_susep"] == AKAD)].empty]
    if not lobs:
        return _item("12", PERGUNTAS["12"], "A Akad não aparece nas LOBs selecionadas.")

    def share(l: str, ano: int) -> float:
        tot = c.premio_ano(l, ano)
        return c.premio_ano(l, ano, True) / tot if tot > 0 else 0.0

    tot_akad_f1 = sum(c.premio_ano(l, c.f1, True) for l in c.lobs)
    dados = {}
    for l in lobs:
        g = fase[fase["lob"] == l]
        a = g[g["codigo_susep"] == AKAD]
        m_ak, m_mk = A.metricas(a), A.metricas(g)
        m_sem = A.metricas(g[g["codigo_susep"] != AKAD]) if not g[g["codigo_susep"] != AKAD].empty else m_mk
        dados[l] = {
            "s1": share(l, c.f1),
            "mg_a": m_ak["margem"], "mg_m": m_mk["margem"], "mg_sem": m_sem["margem"],
            "sin_a": m_ak["sinistralidade"], "sin_m": m_mk["sinistralidade"],
            "lucro_a": m_ak["lucro"], "premio_a": m_ak["premio"],
            "mix": c.premio_ano(l, c.f1, True) / tot_akad_f1 if tot_akad_f1 > 0 else math.nan,
            "k": _contribuicoes(fase, l),
        }

    tr = dados.get("Transportes")
    eo = dados.get("E&O")

    impacto = math.nan
    if tr:
        impacto = (tr["mg_sem"] - tr["mg_a"]) * tr["premio_a"]

    if eo and tr:
        curta = (
            "Crescer em E&O, onde a Akad lidera com a melhor margem, e recuperar a margem de "
            f"Transportes, que é {_pct(tr['mix'], 0)} do prêmio."
        )
    elif eo:
        curta = "Expandir E&O, onde a Akad lidera com a melhor margem entre as LOBs selecionadas."
    elif tr:
        onde = f", que é {_pct(tr['mix'], 0)} do prêmio da Akad," if len(lobs) > 1 else ", que concentra o prêmio da Akad,"
        curta = f"Recuperar a margem de Transportes{onde} antes de buscar crescimento."
    else:
        pior = max(dados.items(), key=lambda kv: kv[1]["mg_sem"] - kv[1]["mg_a"])
        curta = f"Priorizar {pior[0]}, onde a distância para a margem dos concorrentes é a maior."

    porques = []
    if eo:
        porques.append(
            f"E&O deu à Akad {A.f_din(eo['lucro_a'])} de lucro com {A.f_din(eo['premio_a'])} de prêmio na fase Akad."
        )
    if tr and not _nan(impacto):
        porques.append(
            f"Transportes é {_pct(tr['mix'], 0)} do prêmio da Akad, com margem de {_pct(tr['mg_a'])}. "
            f"Se chegasse à margem dos concorrentes ({_pct(tr['mg_sem'])}), o lucro seria cerca de "
            f"{A.f_din(impacto)} maior."
        )
    if eo and not _nan(impacto):
        porques.append(
            f"Esse ganho é maior que todo o lucro de E&O na fase ({A.f_din(eo['lucro_a'])})."
        )
    rcg = dados.get("RCG")
    if rcg:
        porques.append(
            f"RCG é pequena ({_pct(rcg['s1'])} de participação) e lucrativa, mas instável; crescer com limite de exposição."
        )

    linhas = []
    for l in lobs:
        d = dados[l]
        papel, acao = PAPEL.get(l, ("–", "–"))
        linhas.append([
            l, f"{_pct(d['s1'])}", f"{_pct(d['mg_a'])} vs {_pct(d['mg_sem'])}",
            f"{_pct(d['sin_a'])} vs {_pct(d['sin_m'])}", A.f_din(d["lucro_a"]),
            _pct(d["mix"], 0), f"{papel}: {acao}",
        ])
    tabela = _tabela(
        ["LOB", "Participação", "Margem Akad vs concorrentes", "Sinistralidade Akad vs mercado",
         "Lucro Akad", "% do prêmio da Akad", "Papel"],
        linhas, esq={0, 6},
    )

    execucao = (
        "Como executar:\n\n"
        "- Canais: ampliar corretores e parcerias digitais para baixar o custo de venda em Empresarial.\n"
        "- Preço e subscrição: precificar Transportes por rota e tipo de carga.\n"
        "- Sinistros: prevenção a roubo de carga em Transportes.\n"
        "- Resseguro e capital: rever a retenção em E&O conforme a carteira cresce."
    )

    cenario = ""
    if eo and not c.cresc.empty and "E&O" in c.cresc.index:
        cagr = c.cresc.loc["E&O", "cagr"]
        mercado_2025 = c.premio_ano("E&O", c.f1)
        if math.isfinite(cagr) and mercado_2025 > 0:
            proj = mercado_2025 * (1 + cagr) ** 5 * eo["s1"]
            cenario = (
                f"Cenário: se o mercado de E&O mantiver o crescimento médio de {_pct(cagr)} ao ano "
                f"e a Akad mantiver {_pct(eo['s1'])} de participação, o prêmio dela em E&O chegaria a "
                f"cerca de {A.f_din(proj)} em 2030."
            )

    return _item(
        "12", PERGUNTAS["12"], curta,
        _bloco(
            porques, tabela,
            metodo=f"fase Akad ({c.fase_rotulo}); margem e sinistralidade por razão de somas; concorrentes = mercado sem a Akad.",
            atencao=(
                "o papel de cada LOB é opinião apoiada na tabela, a validar com dados internos de preço, "
                "comissão e resseguro. Gatilho de revisão: se a sinistralidade de E&O voltar acima de 45%, "
                "rever a retenção de risco."
            ),
            extra=(execucao + ("\n\n" + cenario if cenario else "")),
        ),
    )


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------

def gerar(base: pd.DataFrame) -> list[dict]:
    """Q1–Q12 para a base recebida (já filtrada por LOB e ano)."""
    if base.empty:
        return [
            {"n": f"{i:02d}", "pergunta": "", "curta": "Sem dados.", "corpo": "Sem dados.", "resposta": "Sem dados."}
            for i in range(1, 13)
        ]
    c = _Ctx(base)
    return [
        _q01(c), _q02(c), _q03(c), _q04(c), _q05(c), _q06(c),
        _q07(c), _q08(c), _q09(c), _q10(c), _q11(c), _q12(c),
    ]
