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

# --------------------------------------------------------------------------
# Helpers de redacao (prosa): numeros por extenso, plural e artigo
# --------------------------------------------------------------------------

MASCULINAS = {"BTG", "BRADESCO", "ITAU", "ITAÚ", "SAFRA", "IRB", "BANCO", "CHUBB"}


def _fmt(v: float, dec: int) -> str:
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _brl(v: float) -> str:
    """Valor por extenso: 'R$ 29,3 bilhões', 'R$ 198,3 milhões', 'R$ 5 mil'."""
    if _nan(v):
        return "–"
    sinal = "−" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        n = a / 1e9
        unidade = "bilhão" if round(n, 1) == 1.0 else "bilhões"
        return f"{sinal}R$ {_fmt(n, 1)} {unidade}"
    if a >= 1e6:
        n = a / 1e6
        unidade = "milhão" if round(n, 1) == 1.0 else "milhões"
        return f"{sinal}R$ {_fmt(n, 1)} {unidade}"
    if a >= 1e3:
        return f"{sinal}R$ {_fmt(a / 1e3, 0)} mil"
    return f"{sinal}R$ {_fmt(a, 0)}"


def _pp(v: float, primeira: bool = True) -> str:
    """Pontos percentuais por extenso. Recebe a diferenca em fracao (0,131 -> '13,1 pontos')."""
    if _nan(v):
        return "–"
    a = abs(v) * 100
    singular = a < 1.0 or round(a, 1) == 1.0
    if singular:
        unidade = "ponto percentual" if primeira else "ponto"
    else:
        unidade = "pontos percentuais" if primeira else "pontos"
    return f"{_fmt(a, 1)} {unidade}"


NUMEROS = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco",
           6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez"}


NUMEROS_FEM = {1: "uma", 2: "duas"}


def _num_txt(n: int, fem: bool = False) -> str:
    if fem and n in NUMEROS_FEM:
        return NUMEROS_FEM[n]
    return NUMEROS.get(n, str(n))


def _artigo(nome: str) -> str:
    primeira = (nome or "").split(" ")[0].upper().strip(",.")
    return "o" if primeira in MASCULINAS else "a"


def _com_artigo(nome: str) -> str:
    return f"{_artigo(nome)} {A.nome_curto(nome)}"


def _cap(nome: str) -> str:
    """Maiuscula apenas a primeira letra, preservando siglas (BTG, HDI)."""
    return nome[:1].upper() + nome[1:] if nome else nome


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _prosa(paragrafos, tabelas=()) -> str:
    texto = [p.strip() for p in paragrafos if p and p.strip()]
    corpo = "\n\n".join(texto)
    for t in tabelas:
        if t:
            corpo += "\n\n" + t.strip()
    return corpo


# --------------------------------------------------------------------------
# Q1–Q3
# --------------------------------------------------------------------------

def _q01(c: _Ctx) -> dict:
    lob, total = c.lob, float(c.lob["premio"].sum())
    top = lob.index[0]
    share = lob.loc[top, "premio"] / total if total else math.nan
    seg = lob.index[1] if len(lob) > 1 else None
    menor = lob.index[-1] if len(lob) > 1 else None
    s0, s1 = c.premio_ano(top, c.a0), c.premio_ano(top, c.a1)
    t0 = sum(c.premio_ano(l, c.a0) for l in c.lobs)
    t1 = sum(c.premio_ano(l, c.a1) for l in c.lobs)
    p0, p1 = (s0 / t0 if t0 else math.nan), (s1 / t1 if t1 else math.nan)

    curta = (
        f"Transportes é a maior linha de negócio do período, com {_brl(lob.loc[top, 'premio'])} "
        f"de prêmio ganho entre {c.a0} e {c.a1}."
    )
    p1_txt = (
        f"Esse valor equivale a {_pct(share, 0)} de tudo o que as {_num_txt(len(lob))} LOBs faturaram."
        if len(lob) > 1 else ""
    )
    p2 = ""
    if seg:
        p2 = (
            f"{seg} vem em segundo lugar, com {_brl(lob.loc[seg, 'premio'])}, e a distância para "
            f"Transportes é grande: a líder fatura {_fmt(lob.loc[top, 'premio'] / lob.loc[seg, 'premio'], 1)} vezes mais."
        )
        if menor:
            p2 += f" Na outra ponta, {menor} soma {_brl(lob.loc[menor, 'premio'])}, pouco mais de um décimo da líder."
    p3 = ""
    if c.a0 != c.a1:
        p3 = (
            f"A liderança, porém, está encolhendo em termos relativos: a participação de Transportes no prêmio "
            f"das LOBs passou de {_pct(p0)} em {c.a0} para {_pct(p1)} em {c.a1}. "
        )
    p3 += (
        "Vale notar que prêmio ganho mede tamanho de carteira, não rentabilidade; como mostram as perguntas 5 e 6, "
        "Transportes é justamente a LOB de menor margem. Todos os valores são nominais, como publicados pela SUSEP."
    )
    tabela = _tabela(
        ["LOB", "Prêmio ganho", "Participação no total"],
        [[l, A.f_bi(r["premio"]), _pct(r["premio"] / total if total else math.nan)] for l, r in lob.iterrows()],
    )
    return _item("01", PERGUNTAS["01"], curta, _prosa([p1_txt, p2, p3], [tabela]))


def _q02(c: _Ctx) -> dict:
    atv = A.ativas_por_ano(c.base, "premio")
    pres = A.ativas_por_ano(c.base, "presenca")
    mat = (c.base[c.base["premio_ganho"] >= 1_000_000]
           .groupby(["lob", "ano"]).codigo_susep.nunique().unstack())
    a0, a1 = c.a0, c.a1
    l0, l1 = atv[a0].idxmax(), atv[a1].idxmax()

    if a0 == a1:
        curta = f"{l0} tem o maior número de seguradoras ativas em {a0}: {int(atv[a0].max())}."
    elif l0 == l1:
        curta = (f"{l0} é a LOB com mais seguradoras ativas nos dois anos, com "
                 f"{int(atv.loc[l0, a0])} empresas em {a0} e {int(atv.loc[l0, a1])} em {a1}.")
    else:
        curta = (f"{l0} lidera em {a0}, com {int(atv[a0].max())} seguradoras ativas, e {l1} "
                 f"assume a liderança em {a1}, com {int(atv[a1].max())}.")

    paras = []
    if not mat.empty and a0 in mat.columns and a1 in mat.columns:
        ml0, ml1 = mat[a0].idxmax(), mat[a1].idxmax()
        if ml0 == ml1:
            paras.append(
                f"A liderança se mantém quando se exige um prêmio mínimo de R$ 1 milhão no ano: por esse critério, "
                f"{ml0} passa de {int(mat.loc[ml0, a0])} para {int(mat.loc[ml0, a1])} seguradoras."
            )
    if a0 != a1:
        var = (atv[a1] - atv[a0]).sort_values(ascending=False)
        quem = var.index[0]
        if var.iloc[0] > 0:
            paras.append(
                f"O movimento de entrada mais forte, no entanto, aconteceu em {quem}, que ganhou "
                f"{_num_txt(int(var.iloc[0]))} {'concorrente' if int(var.iloc[0]) == 1 else 'concorrentes'} no período e passou de "
                f"{int(atv.loc[quem, a0])} para {int(atv.loc[quem, a1])} empresas ativas."
            )
        menor = atv[a1].idxmin()
        top5 = c.conc.loc[menor, "top5"] if menor in c.conc.index else math.nan
        paras.append(
            f"No extremo oposto está {menor}, que manteve {_plural(int(atv.loc[menor, a1]), 'empresa ativa', 'empresas ativas')} "
            f"e é também a carteira mais concentrada: as cinco maiores detêm {_pct(top5)} do prêmio. "
            "Isso sugere que operar nessa LOB exige estrutura de subscrição e de sinistros que poucos concorrentes têm."
        )
    pl0 = pres[a0].idxmax()
    paras.append(
        f"Consideramos ativa a seguradora que registrou prêmio ganho positivo no ano. A ressalva é necessária porque o SES "
        f"também lista empresas que não venderam nada e apenas administram sinistros antigos; se todas fossem contadas, "
        f"{pl0} apareceria na liderança em {a0}, o que distorceria a leitura da concorrência real."
    )
    tabela = _tabela(
        ["LOB", f"Ativas {a0}", f"Ativas {a1}", "Variação"],
        [[l, int(atv.loc[l, a0]), int(atv.loc[l, a1]), f"{int(atv.loc[l, a1] - atv.loc[l, a0]):+d}"] for l in c.lobs],
    )
    return _item("02", PERGUNTAS["02"], curta, _prosa(paras, [tabela]))


def _q03(c: _Ctx) -> dict:
    d = c.lob.sort_values("sinistralidade", ascending=False)
    top = d.index[0]
    segundo = d.index[1] if len(d) > 1 else None
    curta = f"{top} tem a maior sinistralidade do período, com {_pct(d.loc[top, 'sinistralidade'])}."
    paras = []
    if segundo:
        gap = d.loc[top, "sinistralidade"] - d.loc[segundo, "sinistralidade"]
        if gap < 0.005:
            paras.append(
                f"A diferença para {segundo} ({_pct(d.loc[segundo, 'sinistralidade'])}) é de apenas {_pp(gap)}, "
                "o que, na prática, configura um empate: nas duas carteiras, mais da metade de cada real de prêmio "
                "foi consumida pelo pagamento de sinistros."
            )
        else:
            paras.append(
                f"{segundo} vem em segundo, com {_pct(d.loc[segundo, 'sinistralidade'])}, "
                f"{_pp(gap)} abaixo da líder."
            )
    if c.a0 != c.a1 and top in c.lob_ano["lob"].values:
        serie = c.lob_ano[c.lob_ano["lob"] == top].set_index("ano")["sinistralidade"]
        pior = serie.idxmax()
        sem = c.base[c.base["ano"] != pior]
        if not sem.empty:
            d_sem = A.por_lob(sem).set_index("lob")["sinistralidade"].sort_values(ascending=False)
            novo = d_sem.index[0]
            paras.append(
                f"Esse resultado depende de um único ano. Em {int(pior)}, a sinistralidade de {top} saltou para "
                f"{_pct(serie.loc[pior])}, puxada por sinistros de grande porte. Se esse ano for excluído, o índice "
                f"cai para {_pct(d_sem.get(top, math.nan))} e {novo} passa a ser a LOB mais sinistrada, com "
                f"{_pct(d_sem.loc[novo])}. A diferença entre as duas é, portanto, de natureza: em {top} o risco aparece "
                "em picos concentrados; em Transportes, de forma mais constante."
            )
    if len(d) > 1:
        menor = d.index[-1]
        paras.append(
            f"No outro extremo está {menor}, com {_pct(d.loc[menor, 'sinistralidade'])}. O seguro garantia funciona como "
            "uma fiança: a seguradora analisa o crédito do cliente antes de emitir a apólice e pode cobrar dele o valor "
            "indenizado, o que mantém os sinistros baixos."
        )
    paras.append(
        "A sinistralidade foi calculada como a soma dos sinistros dividida pela soma dos prêmios do período, "
        "para que anos ou empresas pequenas não pesem tanto quanto as grandes."
    )
    tabela = _tabela(
        ["LOB", "Sinistro ocorrido", "Prêmio ganho", "Sinistralidade"],
        [[l, A.f_bi(r["sinistro"]), A.f_bi(r["premio"]), _pct(r["sinistralidade"])] for l, r in d.iterrows()],
    )
    return _item("03", PERGUNTAS["03"], curta, _prosa(paras, [tabela]))


# --------------------------------------------------------------------------
# Q4
# --------------------------------------------------------------------------

def q4_curta(base: pd.DataFrame, min_share: float = 0.01) -> str:
    tab = A.q4(base, min_share=min_share, top=1)
    if tab.empty:
        return "Sem seguradoras acima do corte."
    extremos = tab.nlargest(2, "sinistralidade")
    nomes = " e ".join(
        f"{_com_artigo(r.seguradora)} em {r.lob} ({_pct(r.sinistralidade, 0)})" for r in extremos.itertuples()
    )
    if len(tab) > 2:
        return f"Com corte de {_pct(min_share, 0)} de participação, os extremos são {nomes}."
    partes = [f"{_com_artigo(r.seguradora)} em {r.lob} ({_pct(r.sinistralidade, 0)})" for r in tab.itertuples()]
    return "Com corte de materialidade, as maiores são " + "; ".join(partes) + "."


def _q04(c: _Ctx) -> dict:
    com = A.q4(c.base, min_share=0.01, top=1).set_index("lob")
    sem = A.q4(c.base, min_share=0.0, top=1).set_index("lob")
    curta = q4_curta(c.base, 0.01)

    nomes = []
    for l in c.lobs:
        if l in com.index:
            r = com.loc[l]
            artigo = "do" if _artigo(r["seguradora"]) == "o" else "da"
            nomes.append(f"{artigo} {A.nome_curto(r['seguradora'])} em {l} ({_pct(r['sinistralidade'], 0)})")
    paras = []
    if nomes:
        paras.append(
            "Considerando apenas as seguradoras com pelo menos 1% do prêmio da LOB, as maiores sinistralidades "
            "do período são " + ", ".join(nomes[:-1]) + " e " + nomes[-1] + "."
        )
    altos = com.sort_values("sinistralidade", ascending=False).head(2)
    detalhes = []
    for lob_nome, r in altos.iterrows():
        g = c.base[(c.base["lob"] == lob_nome) & (c.base["codigo_susep"] == r["codigo_susep"])]
        agg = g[g["premio_ganho"] > 0].groupby("ano")[["sinistro_ocorrido", "premio_ganho"]].sum()
        ratio = (agg["sinistro_ocorrido"] / agg["premio_ganho"]).replace([math.inf, -math.inf], math.nan).dropna()
        if not ratio.empty:
            pior = ratio.idxmax()
            detalhes.append(
                f"{_cap(A.nome_curto(r['seguradora']))} chegou a {_pct(ratio.loc[pior], 0)} em {int(pior)}"
            )
    if detalhes:
        paras.append(
            "Os casos mais extremos se explicam por anos específicos: " + "; ".join(detalhes) + "."
        )
    if not sem.empty:
        extremo = sem.sort_values("sinistralidade", ascending=False).iloc[0]
        paras.append(
            f"O corte de 1% foi adotado porque, sem ele, o ranking passa a ser dominado por empresas quase sem operação. "
            f"{_cap(A.nome_curto(extremo['seguradora']))} registra sinistralidade de {_pct(extremo['sinistralidade'], 0)}, "
            f"mas sobre um prêmio de apenas {_brl(extremo['premio'])}; o número é matematicamente extremo e "
            "economicamente irrelevante. A tabela traz as duas leituras."
        )
    ak = sem[sem["codigo_susep"] == AKAD] if not sem.empty else pd.DataFrame()
    if not ak.empty:
        r = ak.iloc[0]
        paras.append(
            f"Vale notar que, em {r['lob']}, a própria Akad aparece entre as três maiores sinistralidades, com "
            f"{_pct(r['sinistralidade'], 0)}. Esse ponto é retomado nas perguntas 10 e 11, porque é o principal "
            "problema da carteira da empresa."
        )
    linhas = []
    for l in c.lobs:
        if l in com.index and l in sem.index:
            a, b = com.loc[l], sem.loc[l]
            linhas.append([
                l, A.nome_curto(a["seguradora"]), _pct(a["sinistralidade"], 0), _pct(a["share"]),
                A.nome_curto(b["seguradora"]), _pct(b["sinistralidade"], 0), A.f_din(b["premio"]),
            ])
    tabela = _tabela(
        ["LOB", "Com corte ≥ 1%", "Sinistr.", "Participação", "Sem corte", "Sinistr.", "Prêmio"],
        linhas, esq={0, 1, 4},
    )
    return _item("04", PERGUNTAS["04"], curta, _prosa(paras, [tabela]))

# --------------------------------------------------------------------------
# Q5–Q7
# --------------------------------------------------------------------------

def _q05(c: _Ctx) -> dict:
    d = c.lob.sort_values("lucro", ascending=False)
    top = d.index[0]
    total = float(d["lucro"].sum())
    pos = int(c.lob["premio"].rank(ascending=False).loc[top])
    curta = f"As cinco LOBs somaram {_brl(total)} de lucro no período, e {top} foi a mais lucrativa, com {_brl(d.loc[top, 'lucro'])}."

    g = c.base[c.base["lob"] == top]
    p = float(g["premio_ganho"].sum())
    rr = float(g["receita_resseguro"].sum())
    so = float(g["sinistro_ocorrido"].sum())
    dr = float(g["despesa_resseguro"].sum())
    dc = float(g["despesa_comercial"].sum())

    paras = []
    if len(d) > 1:
        segundo, terceiro = d.index[1], d.index[2] if len(d) > 2 else None
        txt = (
            f"{top} é apenas a {pos}ª em prêmio, mas a sinistralidade de {_pct(d.loc[top, 'sinistralidade'])} "
            f"mais do que compensa o custo de resseguro dessa carteira."
        )
        if terceiro:
            txt += (
                f" {segundo} ficou em segundo lugar, com {_brl(d.loc[segundo, 'lucro'])}, seguida de perto por "
                f"{terceiro}, com {_brl(d.loc[terceiro, 'lucro'])}."
            )
        paras.append(txt)
    paras.append(
        f"Neste trabalho, lucro corresponde ao resultado da operação de seguros, como pede o case: prêmio ganho mais "
        f"receita de resseguro, menos sinistros, despesa de resseguro e despesa comercial. Em {top}, por exemplo, a conta "
        f"é R$ {_fmt(p/1e9, 2)} bilhões + R$ {_fmt(rr/1e9, 2)} bilhões − R$ {_fmt(so/1e9, 2)} bilhões "
        f"− R$ {_fmt(dr/1e9, 2)} bilhões − R$ {_fmt(dc/1e9, 2)} bilhões, o que resulta em {_brl(p + rr - so - dr - dc)}. "
        "Ficam de fora as despesas administrativas, os impostos e o resultado financeiro, que não fazem parte das colunas do case."
    )
    tabela = _tabela(
        ["LOB", "Lucro", "Participação no total", "Prêmio ganho"],
        [[l, A.f_bi(r["lucro"]), _pct(r["lucro"] / total if total else math.nan), A.f_bi(r["premio"])] for l, r in d.iterrows()],
    )
    return _item("05", PERGUNTAS["05"], curta, _prosa(paras, [tabela]))


def _q06(c: _Ctx) -> dict:
    d = c.lob.sort_values("margem", ascending=False)
    top, bot = d.index[0], d.index[-1]
    curta = f"E&O tem a maior margem do período, de {_pct(d.loc[top, 'margem'])}: de cada R$ 100 de prêmio, sobram R$ {_fmt(d.loc[top, 'margem'] * 100, 2)} de lucro."

    comp = {l: A.componentes(c.base[c.base["lob"] == l]) for l in d.index}
    paras = []
    if len(d) > 1:
        paras.append(
            f"Na outra ponta está {bot}, com {_pct(d.loc[bot, 'margem'])}, o que significa que a maior LOB em volume é "
            "também a menos rentável."
        )
        contrib = {k: -(comp[top][k] - comp[bot][k]) for k in ("sin", "resseg", "com")}
        partes = []
        if contrib["sin"] > 0:
            partes.append(f"da sinistralidade, que é {_pp(contrib['sin'], primeira=False)} menor em {top}")
        if contrib["com"] > 0:
            partes.append(f"da despesa comercial mais baixa, que soma {_pp(contrib['com'], primeira=False)} a favor de {top}")
        contra = [f"{'o' if k == 'resseg' else 'a'} {NOME_COMPONENTE[k]} joga contra, com {_pp(-contrib[k], primeira=False)}"
                  for k in ("sin", "resseg", "com") if contrib[k] < 0]
        txt = f"A diferença de {_pp(d.loc[top, 'margem'] - d.loc[bot, 'margem'])} entre as duas vem "
        txt += " e ".join(partes) if partes else "de vários fatores"
        if contra:
            txt += ", enquanto " + " e ".join(contra)
        paras.append(txt + ".")
        terceira = d.index[1] if len(d) > 1 else None
        if terceira:
            paras.append(
                f"{terceira} ilustra o efeito oposto: tem sinistralidade de {_pct(comp[terceira]['sin'])}, mas o resseguro "
                f"consome {_pct(abs(comp[terceira]['resseg']))} do prêmio, e por isso ela não chega à maior margem."
            )
    # evolucao anual
    if c.a0 != c.a1:
        melhor = {}
        for l in c.lobs:
            g = c.lob_ano[c.lob_ano["lob"] == l].set_index("ano")
            if c.a0 in g.index and c.a1 in g.index:
                melhor[l] = g.loc[c.a1, "margem"] - g.loc[c.a0, "margem"]
        if melhor:
            subiu = max(melhor, key=melhor.get)
            caiu = min(melhor, key=melhor.get)
            paras.append(
                f"Ao longo dos anos, a margem melhorou de forma consistente em {subiu}, que saiu de "
                f"{_pct(c.lob_ano[(c.lob_ano['lob'] == subiu) & (c.lob_ano['ano'] == c.a0)]['margem'].iloc[0])} em {c.a0} "
                f"para {_pct(c.lob_ano[(c.lob_ano['lob'] == subiu) & (c.lob_ano['ano'] == c.a1)]['margem'].iloc[0])} em {c.a1}. "
                f"{caiu} seguiu o caminho inverso e fechou {c.a1} em "
                f"{_pct(c.lob_ano[(c.lob_ano['lob'] == caiu) & (c.lob_ano['ano'] == c.a1)]['margem'].iloc[0])}."
            )
    tabela = _tabela(
        ["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Margem"],
        [[l, _pct(comp[l]["sin"]), _pct(comp[l]["resseg"]), _pct(comp[l]["com"]), _pct(comp[l]["margem"])] for l in d.index],
    )
    linhas = []
    for l in c.lobs:
        g = c.lob_ano[c.lob_ano["lob"] == l].set_index("ano")
        linhas.append([l] + [_pct(g.loc[a, "margem"]) if a in g.index else "–" for a in c.anos])
    tabela_ano = _tabela(["LOB"] + [str(a) for a in c.anos], linhas)
    return _item("06", PERGUNTAS["06"], curta, _prosa(paras, [tabela, tabela_ano]))


def _q07(c: _Ctx) -> dict:
    if c.cresc.empty:
        return _item("07", PERGUNTAS["07"], "É preciso selecionar pelo menos dois anos para calcular crescimento.")
    d = c.cresc
    pct_top = d["pct"].idxmax()
    abs_top = d["abs"].idxmax()
    curta = (
        f"Em porcentagem, {pct_top} foi a LOB que mais cresceu; em valor absoluto, a liderança é de {abs_top}."
    )
    paras = []
    r = d.loc[pct_top]
    paras.append(
        f"O prêmio de {pct_top} passou de {_brl(r['primeiro'])} em {int(r['ano_ini'])} para {_brl(r['ultimo'])} em "
        f"{int(r['ano_fim'])}, uma alta de {_pct(r['pct'])}, ou {_pct(r['cagr'])} ao ano."
    )
    a = d.loc[abs_top]
    if abs_top != pct_top:
        paras.append(
            f"Em valor absoluto, {abs_top} adicionou {_brl(a['abs'])} ao mercado, ao passar de {_brl(a['primeiro'])} para "
            f"{_brl(a['ultimo'])}. As duas leituras não se contradizem: {pct_top} cresce mais rápido porque parte de uma base "
            f"pequena, enquanto {abs_top} cresce {_pct(a['pct'])} sobre uma base cerca de "
            f"{_fmt(a['primeiro'] / r['primeiro'], 1)} vezes maior, o que gera muito mais dinheiro novo."
        )
    paras.append(
        f"Para a Akad, as duas informações têm valor: {pct_top} mostra onde o mercado se expande mais rápido, e {abs_top}, "
        "onde está o volume. Como os valores são nominais, parte desse crescimento reflete a inflação do período."
    )
    tabela = _tabela(
        ["LOB", f"Prêmio {c.a0}", f"Prêmio {c.a1}", "Variação R$", "Variação %", "Crescimento ao ano"],
        [[l, A.f_bi(x["primeiro"]), A.f_bi(x["ultimo"]), A.f_bi(x["abs"]), _pct(x["pct"]), _pct(x["cagr"])]
         for l, x in d.sort_values("pct", ascending=False).iterrows()],
    )
    return _item("07", PERGUNTAS["07"], curta, _prosa(paras, [tabela]))


# --------------------------------------------------------------------------
# Q8
# --------------------------------------------------------------------------

def _q08(c: _Ctx) -> dict:
    linhas, cauda_linhas, gaps = [], [], []
    n80s = []
    for l in c.lobs:
        mesa, n, mercado = A.relevantes(c.base, l)
        if mesa.empty:
            continue
        n80s.append(n)
        codigos = set(mesa["codigo_susep"])
        relev = c.base[(c.base["lob"] == l) & (c.base["codigo_susep"].isin(codigos))]
        resto = c.base[(c.base["lob"] == l) & (~c.base["codigo_susep"].isin(codigos))]
        mr = A.metricas(resto)
        mc = A.metricas(relev)
        if not resto.empty:
            cauda_linhas.append([
                l, int(resto["codigo_susep"].nunique()), A.f_bi(mr["premio"]),
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
            ref = mercado["sinistralidade"]
            acima = mesa.loc[(mesa["sinistralidade"] - ref).idxmax()]
            abaixo = mesa.loc[(mesa["sinistralidade"] - ref).idxmin()]
            gaps.append((l, acima, abaixo, ref))

    if not linhas:
        return _item("08", PERGUNTAS["08"], "Não há seguradoras com prêmio positivo nas LOBs selecionadas.")

    curta = (
        f"Entre {min(n80s)} e {max(n80s)} seguradoras concentram 80% do prêmio de cada LOB, e esse grupo tem "
        "indicadores próximos da média do mercado."
    )
    paras = []
    lideres = []
    for l in c.lobs:
        mesa, _, _ = A.relevantes(c.base, l)
        if not mesa.empty:
            lideres.append(f"{l} ({_com_artigo(mesa.sort_values('premio', ascending=False).iloc[0]['seguradora'])})")
    if lideres:
        paras.append(
            "Os líderes mudam de uma LOB para outra: " + ", ".join(lideres[:-1]) + " e " + lideres[-1] + ". "
            "Como as relevantes somam 80% do prêmio, a média do grupo fica naturalmente próxima da média do mercado; "
            "a comparação que revela diferenças é feita empresa a empresa."
        )
    exemplos = []
    for l, acima, abaixo, ref in sorted(gaps, key=lambda x: abs(x[1]["sinistralidade"] - x[2]["sinistralidade"]), reverse=True)[:3]:
        exemplos.append(
            f"em {l}, {_com_artigo(abaixo['seguradora'])} opera com {_pct(abaixo['sinistralidade'])} de sinistralidade, "
            f"contra {_pct(ref)} do mercado, enquanto {_com_artigo(acima['seguradora'])} chega a {_pct(acima['sinistralidade'])}"
        )
    if exemplos:
        paras.append("A dispersão é grande: " + "; ".join(exemplos) + ".")
    if cauda_linhas:
        piores = [x for x in cauda_linhas if x[6].startswith(("−", "-"))]
        paras.append(
            f"Fora desse grupo, as demais seguradoras têm margem inferior à do mercado em {len(piores)} das "
            f"{len(cauda_linhas)} LOBs, o que sugere ganho de escala entre as líderes. A exceção é "
            f"{', '.join(x[0] for x in cauda_linhas if x not in piores) or 'nenhuma'}, onde a cauda tem margem melhor."
        )
    tabela = _tabela(
        ["LOB", "Seguradora", "Participação", "Sinistralidade", "Margem", "Δ sin.", "Δ margem"],
        linhas, esq={0, 1},
    )
    tabela_cauda = _tabela(
        ["LOB", "Seguradoras na cauda", "Prêmio", "Sinistralidade", "Margem", "Δ sin.", "Δ margem"],
        cauda_linhas, esq={0},
    )
    return _item("08", PERGUNTAS["08"], curta, _prosa(paras, [tabela, tabela_cauda]))


# --------------------------------------------------------------------------
# Q9
# --------------------------------------------------------------------------

def _q09(c: _Ctx) -> dict:
    t = c.trend.loc[[l for l in c.lobs if l in c.trend.index]]
    if t.empty:
        return _item("09", PERGUNTAS["09"], "Não há dados suficientes para analisar tendência.")
    span = max(c.a1 - c.a0, 1)

    def serie(l: str, col: str) -> pd.Series:
        g = c.lob_ano[c.lob_ano["lob"] == l].set_index("ano")[col]
        return g.dropna()

    nivel = c.lob["sinistralidade"].idxmin()
    atrativa = c.lob["margem"].idxmax()
    curta = (
        f"As LOBs seguem trajetórias diferentes, e, na minha avaliação, {atrativa} é a mais saudável e atrativa."
    )

    paras = []
    if "Transportes" in t.index:
        s = serie("Transportes", "sinistro")
        p = serie("Transportes", "premio")
        if len(s) >= 2:
            paras.append(
                f"Em Transportes, os sinistros passaram de {_brl(s.iloc[0])} em {int(s.index[0])} para {_brl(s.iloc[-1])} "
                f"em {int(s.index[-1])}, crescendo {_pct(t.loc['Transportes', 'cresc_sinistro'])} ao ano, praticamente no mesmo "
                f"ritmo do prêmio. Por isso a sinistralidade quase não se mexe e permanece perto de "
                f"{_pct(c.lob.loc['Transportes', 'sinistralidade'], 0)}: é uma carteira previsível, mas estruturalmente cara."
            )
    if "Empresarial" in t.index:
        s = serie("Empresarial", "sinistro")
        if len(s) >= 2:
            paras.append(
                f"Empresarial mostra o movimento oposto: os sinistros ficaram quase estáveis, com alta de "
                f"{_pct(t.loc['Empresarial', 'cresc_sinistro'])} ao ano, enquanto o prêmio avançou "
                f"{_pct(c.cresc.loc['Empresarial', 'cagr']) if 'Empresarial' in c.cresc.index else '–'} ao ano. Como resultado, "
                f"a sinistralidade caiu de {_pct(serie('Empresarial', 'sinistralidade').iloc[0])} para "
                f"{_pct(serie('Empresarial', 'sinistralidade').iloc[-1])}, a maior melhora do período."
            )
    outros = [l for l in ("Garantia", "RCG", "E&O") if l in t.index]
    if outros:
        frases = []
        for l in outros:
            sl = serie(l, "sinistralidade")
            if len(sl) < 2:
                continue
            if l == "RCG":
                pior = sl.idxmax()
                frases.append(
                    f"{l} é o caso mais instável: a sinistralidade oscilou até {_pct(sl.loc[pior])} em {int(pior)}."
                )
            elif l == "Garantia":
                frases.append(
                    f"{l} tem o menor nível do grupo, com {_pct(sl.iloc[-1])}, apesar de picos como "
                    f"{_pct(sl.max())} em {int(sl.idxmax())}."
                )
            else:
                frases.append(
                    f"Em {l}, a sinistralidade recuou de {_pct(sl.iloc[0])} em {int(sl.index[0])} para "
                    f"{_pct(sl.iloc[-1])} em {int(sl.index[-1])}."
                )
        if frases:
            paras.append(" ".join(frases))

    if atrativa != nivel:
        paras.append(
            f"Na minha avaliação, {atrativa} é a mais atrativa. {nivel} tem o menor nível de sinistralidade, com "
            f"{_pct(c.lob.loc[nivel, 'sinistralidade'])}, mas é a que menos cresce e não mostra melhora ao longo do período. "
            f"{atrativa} é a única que reúne as três características desejáveis: o crescimento mais rápido, uma sinistralidade "
            f"em queda e a maior margem do conjunto, de {_pct(c.lob.loc[atrativa, 'margem'])}."
        )
    else:
        paras.append(
            f"Na minha avaliação, {atrativa} reúne o melhor conjunto: menor sinistralidade, maior margem e crescimento consistente."
        )

    tabela = _tabela(
        ["LOB", "Sinistros início", "Sinistros fim", "Sinistros ao ano", "Prêmio ao ano", "Sinistralidade início → fim"],
        [
            [
                l,
                A.f_bi(serie(l, "sinistro").iloc[0]) if not serie(l, "sinistro").empty else "–",
                A.f_bi(serie(l, "sinistro").iloc[-1]) if not serie(l, "sinistro").empty else "–",
                _pct(t.loc[l, "cresc_sinistro"]),
                _pct(c.cresc.loc[l, "cagr"]) if l in c.cresc.index else "–",
                f"{_pct(serie(l, 'sinistralidade').iloc[0])} → {_pct(serie(l, 'sinistralidade').iloc[-1])}"
                if not serie(l, "sinistralidade").empty else "–",
            ]
            for l in t.sort_values("sin_media").index
        ],
        esq={0, 5},
    )
    return _item("09", PERGUNTAS["09"], curta, _prosa(paras, [tabela]))


# --------------------------------------------------------------------------
# Q10
# --------------------------------------------------------------------------

def _margem_akad_ano(base: pd.DataFrame, lob: str, ano: int) -> float:
    g = base[(base["lob"] == lob) & (base["ano"] == ano) & (base["codigo_susep"] == AKAD)]
    return A.metricas(g)["margem"] if not g.empty else math.nan


def _posicao(base: pd.DataFrame, lob: str, ano: int):
    g = base[(base["lob"] == lob) & (base["ano"] == ano) & (base["premio_ganho"] > 0)]
    p = g.groupby("codigo_susep")["premio_ganho"].sum()
    if AKAD not in p.index:
        return None
    return int(p.rank(ascending=False, method="min").loc[AKAD])


def _q10(c: _Ctx) -> dict:
    if c.akad.empty:
        return _item("10", PERGUNTAS["10"], "A Akad não aparece nas LOBs selecionadas.")
    ak = c.akad.loc[[l for l in c.lobs if l in c.akad.index]]
    a0, a1 = c.a0, c.a1

    def peso(r) -> bool:
        return (not _nan(r["rank1"]) and r["rank1"] <= 5) or r["share1"] >= 0.05

    rel = [l for l, r in ak.iterrows() if peso(r)]
    sub = [l for l in ak.index if l not in rel]
    rel_ord = sorted(rel, key=lambda x: ak.loc[x, "share1"], reverse=True)

    curta = f"A Akad é relevante em {_num_txt(len(rel_ord), fem=True)} LOBs: " + " e ".join(
        f"{l} ({_pct(ak.loc[l, 'share1'])})" for l in rel_ord
    ) + "."

    paras = []
    if sub:
        paras.append(
            "Nas demais carteiras, a participação ainda é pequena: "
            + ", ".join(f"{_pct(ak.loc[l, 'share1'])} em {l}" for l in sub) + "."
        )
    melhorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] < r["rank0"]]
    if melhorou:
        detalhes = []
        for l in melhorou:
            r = ak.loc[l]
            detalhes.append(f"em {l}, da {int(r['rank0'])}ª para a {int(r['rank1'])}ª posição")
        paras.append(
            f"A posição da empresa melhorou em {_num_txt(len(melhorou))} das {_num_txt(len(ak))} LOBs, mas não de forma "
            "gradual: ela avançou em saltos, " + ", ".join(detalhes[:-1]) + " e " + detalhes[-1] + "."
        )
    piorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] > r["rank0"]]
    if piorou:
        l = piorou[0]
        r = ak.loc[l]
        paras.append(
            f"{l} foi a exceção: a participação da Akad ficou estável, em torno de {_pct(r['share0'])}, enquanto o mercado "
            f"recebia novos concorrentes, e a empresa caiu da {int(r['rank0'])}ª para a {int(r['rank1'])}ª posição."
        )

    if 2021 in c.base["ano"].values:
        g21 = c.base[(c.base["ano"] == 2021) & (c.base["codigo_susep"] == AKAD)]
        if not g21.empty:
            agg = g21.groupby("lob")[["sinistro_ocorrido", "premio_ganho"]].sum()
            ratio = (agg["sinistro_ocorrido"] / agg["premio_ganho"]).dropna().sort_values(ascending=False)
            if not ratio.empty:
                piores = [f"{_pct(v)} em {l}" for l, v in ratio.head(3).items()]
                paras.append(
                    "O momento das mudanças ajuda a entender as causas. O primeiro salto coincide com a troca de controle: "
                    "a GP Investments e a CyberLabs concluíram a compra da Argo em 2022 e lançaram a marca Akad em junho "
                    f"daquele ano. A nova gestão herdou uma carteira com resultados ruins: em 2021, a sinistralidade havia "
                    f"chegado a {piores[0]}, {piores[1]} e {piores[2]}."
                )

    tr = ak.loc["Transportes"] if "Transportes" in ak.index else None
    if tr is not None and a0 != a1:
        m0 = _margem_akad_ano(c.base, "Transportes", a0)
        m1 = _margem_akad_ano(c.base, "Transportes", a1)
        if not _nan(m0) and not _nan(m1):
            paras.append(
                f"Em Transportes, porém, o crescimento teve um custo. A margem caiu de {_pct(m0)} em {a0} para {_pct(m1)} em "
                f"{a1}, e a sinistralidade da Akad chegou a "
                f"{_pct(A.metricas(c.base[(c.base['lob'] == 'Transportes') & (c.base['ano'] == a1) & (c.base['codigo_susep'] == AKAD)])['sinistralidade'])}. "
                "Os dados sugerem que a empresa ganhou participação aceitando preços menores ou riscos piores. Como o SES "
                "mostra o resultado e não a causa, essa explicação deve ser confirmada com dados internos."
            )

    linhas = []
    for l, r in ak.iterrows():
        linhas.append([
            l, A.f_mi(r["premio0"]), A.f_mi(r["premio1"]), _pct(r["share0"]), _pct(r["share1"]),
            f"{int(r['rank0'])}ª" if not _nan(r["rank0"]) else "–",
            f"{int(r['rank1'])}ª" if not _nan(r["rank1"]) else "–",
        ])
    tabela = _tabela(
        ["LOB", f"Prêmio {a0}", f"Prêmio {a1}", f"Participação {a0}", f"Participação {a1}", f"Posição {a0}", f"Posição {a1}"],
        linhas,
    )
    return _item("10", PERGUNTAS["10"], curta, _prosa(paras, [tabela]))


# --------------------------------------------------------------------------
# Q11
# --------------------------------------------------------------------------

def _status(akad: float, ref: float, menor_melhor: bool) -> str:
    d = (ref - akad) if menor_melhor else (akad - ref)
    return "melhor" if d > TOL else ("pior" if d < -TOL else "em linha")


def _frase_status(akad: float, refs: list[tuple[str, float]], menor_melhor: bool) -> str:
    grupos: dict[str, list[str]] = {"melhor": [], "em linha": [], "pior": []}
    for nome, v in refs:
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
    ref = c.fase if c.tem_fase else c.base
    rot = c.fase_rotulo if c.tem_fase else c.periodo
    comp_f = _comparacao(ref, c.lobs) if not ref.empty else comp

    consistentes, abaixo, mistas = [], [], []
    for l, r in comp_f.iterrows():
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

    curta = (
        f"Na fase atual ({rot}), a Akad é melhor que o mercado"
        + (f" em {_lista(consistentes)}" if consistentes else "")
        + (f" e fica atrás nas demais" if abaixo or mistas else "") + "."
    )
    paras = []
    if consistentes:
        partes = []
        for l in consistentes:
            r = comp_f.loc[l]
            partes.append(
                f"em {l}, a margem da Akad foi de {_pct(r['akad_mg'])}, contra {_pct(r['mercado_mg'])} do mercado, "
                f"e a sinistralidade de {_pct(r['akad_sin'])}, contra {_pct(r['mercado_sin'])}"
            )
        paras.append("Os números confirmam a diferença: " + "; ".join(partes) + ".")
    if abaixo or mistas:
        frases = []
        if abaixo:
            frases.append("fica atrás do mercado nas duas métricas em " + _lista(abaixo))
        if mistas:
            frases.append("tem resultado misto em " + _lista(mistas))
        paras.append("Nas demais LOBs, a situação se inverte: a Akad " + " e ".join(frases) + ".")
    # pares e relevantes
    nuances = []
    for l in c.lobs:
        if l not in comp_f.index:
            continue
        r = comp_f.loc[l]
        if not _nan(r["peers_sin"]) and _status(r["akad_sin"], r["peers_sin"], True) == "melhor" \
                and _status(r["akad_mg"], r["peers_mg"], False) == "pior":
            k = _contribuicoes(ref, l)
            fator = "a despesa comercial" if abs(k["com"]) >= abs(k["resseg"]) else "o resseguro"
            valor = _pp(k["com"] if abs(k["com"]) >= abs(k["resseg"]) else -k["resseg"])
            nuances.append(
                f"em {l}, a sinistralidade da Akad ({_pct(r['akad_sin'])}) é melhor que a dos pares "
                f"({_pct(r['peers_sin'])}), embora a margem seja pior; isso indica que o problema não está na seleção "
                f"de risco, mas no custo, já que {fator} tira {valor} da margem"
            )
    if nuances:
        paras.append(
            "A comparação com seguradoras do mesmo porte, isto é, com prêmio entre um terço e o triplo do da Akad, "
            "confirma o quadro em margem, mas traz uma nuance na sinistralidade: " + "; ".join(nuances) + "."
        )
    if "Transportes" in comp_f.index:
        r = comp_f.loc["Transportes"]
        paras.append(
            f"Diante das relevantes, o resultado repete o do mercado: a maior distância aparece em Transportes, onde a "
            f"margem da Akad ({_pct(r['akad_mg'])}) fica {_pp(r['relev_mg'] - r['akad_mg'], primeira=False)} abaixo da média "
            f"das relevantes ({_pct(r['relev_mg'])}) e a sinistralidade ({_pct(r['akad_sin'])}) supera a delas "
            f"({_pct(r['relev_sin'])}). Em resumo, a Akad tem uma operação de excelência nas carteiras de responsabilidade "
            "civil e, em Transportes, o seu principal ponto fraco."
        )

    # tabelas: sinais e valores
    sinais = []
    for l, r in comp_f.iterrows():
        sinais.append([
            l,
            _status(r["akad_mg"], r["mercado_mg"], False),
            _status(r["akad_mg"], r["peers_mg"], False),
            _status(r["akad_mg"], r["relev_mg"], False),
            _status(r["akad_sin"], r["mercado_sin"], True),
            _status(r["akad_sin"], r["peers_sin"], True),
            _status(r["akad_sin"], r["relev_sin"], True),
        ])
    tabela_sinais = _tabela(
        ["LOB", "Margem vs mercado", "vs pares", "vs relevantes",
         "Sinistr. vs mercado", "vs pares", "vs relevantes"],
        sinais, esq={0},
    )
    tabela_valores = _tabela_comparacao(comp_f)

    # decomposicao
    linhas, notas = [], []
    for l in comp_f.index:
        k = _contribuicoes(ref, l)
        if any(_nan(k[x]) for x in k):
            continue
        linhas.append([l, A.f_pp(k["sin"]), A.f_pp(k["resseg"]), A.f_pp(k["com"]), A.f_pp(k["total"])])
        notas.append(f"{l}: {A.f_pp(k['total'])}, puxado por {_driver(k)}")
    tabela_dec = ""
    if linhas:
        tabela_dec = (
            "De onde vem a diferença de margem, em pontos percentuais do prêmio:\n\n"
            + _tabela(["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Diferença de margem"], linhas)
        )
    return _item(
        "11", PERGUNTAS["11"], curta,
        _prosa(paras, [tabela_sinais, tabela_valores, tabela_dec]),
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
            "A fase Akad começa em 2022; é preciso selecionar pelo menos um ano a partir de 2022.",
            "A marca Akad foi criada em junho de 2022, depois da compra concluída naquele ano. Sem anos da fase atual, "
            "não há base para recomendar foco com a estratégia vigente.",
        )

    fase = c.fase
    lobs = [l for l in c.lobs if not fase[(fase["lob"] == l) & (fase["codigo_susep"] == AKAD)].empty]
    if not lobs:
        return _item("12", PERGUNTAS["12"], "A Akad não aparece nas LOBs selecionadas.")

    def share(l: str, ano: int) -> float:
        tot = c.premio_ano(l, ano)
        return c.premio_ano(l, ano, True) / tot if tot > 0 else 0.0

    tot_akad = sum(c.premio_ano(l, c.f1, True) for l in c.lobs)
    dados = {}
    for l in lobs:
        g = fase[fase["lob"] == l]
        a = g[g["codigo_susep"] == AKAD]
        m_ak, m_mk = A.metricas(a), A.metricas(g)
        dados[l] = {
            "s1": share(l, c.f1),
            "mg_a": m_ak["margem"], "mg_m": m_mk["margem"],
            "sin_a": m_ak["sinistralidade"], "sin_m": m_mk["sinistralidade"],
            "lucro_a": m_ak["lucro"], "premio_a": m_ak["premio"],
            "mix": c.premio_ano(l, c.f1, True) / tot_akad if tot_akad else math.nan,
        }

    eo, tr = dados.get("E&O"), dados.get("Transportes")
    impacto = (tr["mg_m"] - tr["mg_a"]) * tr["premio_a"] if tr else math.nan
    curta = "Na minha opinião, a Akad deveria focar em E&O."

    paras = []
    if eo:
        paras.append(
            f"E&O é a LOB em que a empresa já lidera, em que obtém a melhor margem e cujo mercado cresce mais rápido. "
            f"Entre {c.f0} e {c.f1}, a carteira gerou {_brl(eo['lucro_a'])} de lucro sobre {_brl(eo['premio_a'])} de prêmio, "
            f"uma margem de {_pct(eo['mg_a'])}"
            + (f", enquanto o mercado de E&O cresceu, em média, {_pct(c.cresc.loc['E&O', 'cagr'])} ao ano."
               if not c.cresc.empty and "E&O" in c.cresc.index else ".")
        )
    if tr and not _nan(impacto):
        paras.append(
            f"Uma objeção natural é que Transportes tem mais dinheiro em jogo. Se a Akad tivesse operado essa carteira com "
            f"a margem média do mercado, seu lucro teria sido cerca de {_brl(impacto)} maior"
            + (f", um valor superior a todo o lucro gerado por E&O no período." if eo and impacto > eo["lucro_a"] else ".")
            + f" Mesmo assim, Transportes não deve ser o foco de crescimento: recuperar margem exige reprecificar e reduzir a "
            f"exposição aos segmentos deficitários, o que provavelmente significa crescer menos ou até perder participação. "
            f"É uma prioridade de correção, cujo resultado ajudará a financiar a expansão de E&O."
        )
    if eo:
        mercado_2025 = c.premio_ano("E&O", c.f1)
        proj = ""
        if not c.cresc.empty and "E&O" in c.cresc.index and math.isfinite(c.cresc.loc["E&O", "cagr"]):
            proj = (
                f" Se mantiver os {_pct(eo['s1'])} atuais e o mercado continuar crescendo no ritmo recente, a carteira de "
                f"E&O da Akad chegaria a cerca de {_brl(mercado_2025 * (1 + c.cresc.loc['E&O', 'cagr']) ** 5 * eo['s1'])} em 2030."
            )
        paras.append(
            f"Em termos de crescimento, o desafio de E&O é o tamanho do mercado, que somou {_brl(mercado_2025)} em {c.f1}. "
            "Por isso a Akad precisa ampliar o mercado, e não apenas ganhar participação: levar o seguro a novas profissões "
            "e a pequenas e médias empresas, e oferecer coberturas complementares à mesma base de clientes." + proj
        )
    if tr:
        paras.append(
            f"Do lado da lucratividade, a meta em Transportes deveria ser sair dos {_pct(tr['mg_a'])} de margem atuais para "
            "pelo menos 10% em dois anos, com preços calculados por rota e tipo de carga e o abandono dos segmentos que dão "
            "prejuízo."
        )
    paras.append(
        "Os canais de venda e a infraestrutura tornam essa estratégia viável. O corretor deve continuar no centro da "
        "distribuição, apoiado por cotação e emissão automáticas, integradas por API, que reduzam o custo de cada venda. "
        "A esse canal se soma o seguro embarcado em parceiros, como plataformas de serviços profissionais, fintechs e varejo, "
        "especialmente útil em Empresarial, onde a despesa comercial é hoje o principal obstáculo à rentabilidade. A "
        "infraestrutura de dados também precisa sustentar modelos de preço mais finos e uma regulação de sinistros mais ágil."
    )
    if eo:
        paras.append(
            "Por fim, há uma questão de capital. Parte da vantagem de margem da Akad em E&O vem de reter mais risco do que o "
            "mercado, o que funciona bem nos anos bons, mas exige capital e aumenta a exposição a sinistros grandes. À medida "
            "que a carteira crescer, recomendo revisar a política de resseguro e definir um gatilho claro: se a "
            "sinistralidade de E&O voltar a superar 45%, a empresa deve ampliar a cessão de risco. Essas recomendações partem "
            "dos dados públicos do SES e precisam ser validadas com informações internas de preço, comissões e resseguro."
        )

    linhas = []
    for l in lobs:
        d = dados[l]
        papel, acao = PAPEL.get(l, ("–", "–"))
        linhas.append([
            l, _pct(d["s1"]), f"{_pct(d['mg_a'])} vs {_pct(d['mg_m'])}",
            f"{_pct(d['sin_a'])} vs {_pct(d['sin_m'])}", A.f_din(d["lucro_a"]),
            _pct(d["mix"], 0), f"{papel}: {acao}",
        ])
    tabela = _tabela(
        ["LOB", "Participação", "Margem Akad vs mercado", "Sinistralidade Akad vs mercado",
         "Lucro Akad", "Peso no prêmio da Akad", "Papel recomendado"],
        linhas, esq={0, 6},
    )
    return _item("12", PERGUNTAS["12"], curta, _prosa(paras, [tabela]))


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
