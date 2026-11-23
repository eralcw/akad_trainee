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

def _q01(c: _Ctx) -> dict:
    lob = c.lob
    total = float(lob["premio"].sum())
    top = lob.index[0]
    bot = lob.index[-1]
    if len(lob) == 1:
        curta = f"{top} soma {A.f_bi(lob.loc[top, 'premio'])} de prêmio ganho em {c.periodo}."
    else:
        curta = (
            f"{top} lidera com {A.f_bi(lob.loc[top, 'premio'])}, "
            f"{_pct(lob.loc[top, 'premio'] / total, 0)} de todo o prêmio das {len(lob)} LOBs em {c.periodo}."
        )

    explicacao = [
        f"**O que os dados mostram:** somando as {len(lob)} linhas de negócio em {c.periodo}, o mercado "
        f"movimentou **{A.f_bi(total)}** em prêmio ganho (receita de seguros já reconhecida no período)."
    ]
    if len(lob) > 1:
        seg = lob.index[1]
        explicacao.append(
            f"{top} ocupa a liderança com folga ({A.f_bi(lob.loc[top, 'premio'])}, {_pct(lob.loc[top, 'premio'] / total)} do total), "
            f"à frente de {seg} ({A.f_bi(lob.loc[seg, 'premio'])}, {_pct(lob.loc[seg, 'premio'] / total)}). "
            f"Na outra ponta, {bot} é o menor mercado ({A.f_bi(lob.loc[bot, 'premio'])}, {_pct(lob.loc[bot, 'premio'] / total)})."
        )

    linhas = [[l, A.f_bi(r["premio"]), _pct(r["premio"] / total)] for l, r in lob.iterrows()]
    nota = (
        "**Leitura de negócio:** prêmio ganho mede **tamanho (faturamento)**, não lucro — "
        "a maior LOB em volume não é necessariamente a mais rentável (ver Q5 e Q6). "
        "Os valores são nominais (conforme publicados pela SUSEP, sem correção pela inflação)."
    )
    corpo = "\n\n".join(explicacao) + "\n\n" + _tabela(["LOB", "Prêmio ganho", "% do total"], linhas) + "\n\n" + nota
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
        dinamica = (
            f"**O que os dados mostram:** considerando apenas seguradoras que efetivamente operaram "
            f"(prêmio ganho > 0), {l0} concentra o maior número de concorrentes ({n0} empresas)."
        )
    else:
        cab = ["LOB", f"Ativas {a0}", f"Ativas {a1}", "Variação", f"Linhas no SES {a0}", f"Linhas no SES {a1}"]
        linhas = [
            [
                l, int(atv.loc[l, a0]), int(atv.loc[l, a1]),
                f"{int(atv.loc[l, a1]) - int(atv.loc[l, a0]):+d}",
                int(pres.loc[l, a0]), int(pres.loc[l, a1]),
            ]
            for l in c.lobs
        ]
        leitura_pres = f"{pl0} em {a0} e {pl1} em {a1}"
        deltas = {l: int(atv.loc[l, a1]) - int(atv.loc[l, a0]) for l in c.lobs}
        maior_entrada = max(deltas, key=deltas.get)
        menor_l = min(c.lobs, key=lambda l: int(atv.loc[l, a1]))
        dinamica = (
            f"**O que os dados mostram:** {l1} é o mercado mais disputado em número de players ({n1} ativas em {a1}). "
            f"No período, **{maior_entrada}** foi quem mais atraiu novos entrantes "
            f"({int(atv.loc[maior_entrada, a0])} → {int(atv.loc[maior_entrada, a1])}, {deltas[maior_entrada]:+d} seguradoras). "
            f"Já **{menor_l}** tem o menor grupo de ativas ({int(atv.loc[menor_l, a1])} em {a1}), sugerindo barreiras "
            "técnicas ou operacionais mais altas para entrar."
        )

    nota = (
        "**Por que definimos 'ativa = prêmio ganho > 0'?** O SES lista seguradoras apenas registradas "
        "no ramo, mesmo sem vender nada no ano (ou só pagando sinistros antigos). Se contássemos todas "
        f"as linhas da tabela, o líder mudaria para **{leitura_pres}** — mas isso mede cadastro, não operação real."
    )
    corpo = dinamica + "\n\n" + _tabela(cab, linhas) + "\n\n" + nota
    return _item("02", "Qual a LOB com mais seguradoras ativas em 2020? E em 2025?", curta, corpo)


def _q03(c: _Ctx) -> dict:
    d = c.lob.sort_values("sinistralidade", ascending=False)
    top = d.index[0]
    curta = f"{top} tem a maior sinistralidade do período: {_pct(d.loc[top, 'sinistralidade'])}"
    empate_txt = ""
    if len(d) > 1:
        seg = d.index[1]
        gap = d.loc[top, "sinistralidade"] - d.loc[seg, "sinistralidade"]
        if gap < 0.005:
            gap_str = f"{gap * 100:.1f}".replace(".", ",")
            curta += f", em empate técnico com {seg} ({_pct(d.loc[seg, 'sinistralidade'])}; diferença de {gap_str} pp)"
            empate_txt = (
                f"Na prática, **{top} ({_pct(d.loc[top, 'sinistralidade'])})** e **{seg} ({_pct(d.loc[seg, 'sinistralidade'])})** "
                f"estão empatadas no topo (diferença de apenas {gap_str} pp) — em ambas, mais da metade de cada real "
                "arrecadado é consumida por indenizações. "
            )
    curta += "."

    explicacao = (
        "**O que é sinistralidade:** mede qual fração do prêmio ganho foi gasta pagando sinistros "
        "(acidentes, roubos, processos ou indenizações cobertas). **Quanto menor, melhor.** "
        + empate_txt
    )
    if len(d) > 1:
        low = d.index[-1]
        explicacao += (
            f"Na outra ponta, **{low}** opera em um patamar completamente diferente "
            f"(**{_pct(d.loc[low, 'sinistralidade'])}**)"
        )
        if low == "Garantia":
            explicacao += (
                ": o Seguro Garantia funciona como uma fiança contratual/judicial, com análise de crédito "
                "prévia e direito de cobrança de volta caso o cliente descumpra o contrato, o que mantém "
                "a frequência de sinistros muito baixa."
            )
        else:
            explicacao += "."

    linhas = [
        [l, A.f_bi(r["sinistro"]), A.f_bi(r["premio"]), _pct(r["sinistralidade"])]
        for l, r in d.iterrows()
    ]
    nota = (
        "**Método:** calculada sempre como `soma(sinistros ocorridos) ÷ soma(prêmios ganhos)` "
        "(razão de somas). Nunca usamos média simples de percentuais, pois isso daria peso igual "
        "a anos ou ramos pequenos e distorceria o resultado."
    )
    corpo = explicacao + "\n\n" + _tabela(["LOB", "Sinistros ocorridos", "Prêmio ganho", "Sinistralidade"], linhas) + "\n\n" + nota
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
           "Sem corte (literal)", "Sinistr.", "Prêmio da seguradora"]
    curta = q4_curta(c.base, 0.01)
    extremo = max(
        (sem.loc[l] for l in c.lobs if l in sem.index),
        key=lambda r: r["sinistralidade"],
        default=None,
    )

    intro = (
        "**Por que mostramos duas colunas (com corte e sem corte)?** "
        "No mercado de seguros existem empresas em *run-off* (pararam de vender, mas ainda pagam "
        "sinistros antigos) ou com operação minúscula. Quando o prêmio é quase zero, um único sinistro "
        "faz a sinistralidade explodir matematicamente"
    )
    if extremo is not None:
        intro += (
            f" — é o caso da **{A.nome_curto(extremo['seguradora'])}**, que aparece com "
            f"**{_pct(extremo['sinistralidade'], 0)}** sobre um prêmio de apenas **{A.f_din(extremo['premio'])}**"
        )
    intro += (
        ". Por isso, apresentamos o ranking **com corte de materialidade (share ≥ 1% da LOB)** "
        "como resposta principal de negócio, e o ranking **sem corte** ao lado para responder literalmente."
    )

    nota = (
        "**Nota técnica:** o cálculo soma sinistros e prêmios da seguradora no período inteiro "
        "(sobre linhas com prêmio > 0). Algumas empresas apresentam sinistralidade **negativa** — "
        "isso não é erro, mas **reversão de reserva** (a seguradora havia provisionado um valor para "
        "sinistros antigos e acabou pagando menos), motivo pelo qual nunca aparecem como a maior."
    )
    corpo = intro + "\n\n" + _tabela(cab, linhas, esq={0, 1, 4}) + "\n\n" + nota
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

    explicacao = (
        "**O que é Resultado Técnico:** é o \"lucro da operação pura de seguros\" — quanto sobra do "
        "prêmio ganho depois de pagar sinistros, comissão de corretores e o saldo líquido de resseguro. "
        f"No total do período ({c.periodo}), as {len(d)} LOBs geraram **{A.f_bi(total)}**."
    )
    if len(d) > 1:
        maior_prem = c.lob.index[0]
        if top != maior_prem:
            explicacao += (
                f"\n\n**Por que {top} vence mesmo não sendo a maior em prêmio?** "
                f"{top} combina escala relevante ({A.f_bi(d.loc[top, 'premio'])}) com sinistralidade muito baixa "
                f"({_pct(d.loc[top, 'sinistralidade'])}), o que preserva uma margem alta ({_pct(d.loc[top, 'margem'])}). "
                f"Já {maior_prem} fatura muito mais ({A.f_bi(c.lob.loc[maior_prem, 'premio'])}), mas entrega uma margem "
                f"bem mais apertada ({_pct(c.lob.loc[maior_prem, 'margem'])}), gerando {A.f_bi(c.lob.loc[maior_prem, 'lucro'])}."
            )

    linhas = [
        [l, A.f_bi(r["lucro"]), _pct(r["lucro"] / total) if total > 0 else "–", A.f_bi(r["premio"]), _pct(r["margem"])]
        for l, r in d.iterrows()
    ]
    nota = (
        "**Fórmula e limite:** `Prêmio ganho + Receita de resseguro − Sinistro ocorrido − "
        "Despesa de resseguro − Despesa comercial`. Não é lucro líquido contábil: ficam de fora "
        "despesas administrativas (salários, TI, estrutura), impostos e o resultado financeiro (juros sobre o caixa)."
    )
    corpo = (
        explicacao
        + "\n\n"
        + _tabela(["LOB", "Resultado técnico", "% do total", "Prêmio ganho", "Margem"], linhas)
        + "\n\n"
        + nota
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
    explicacao = (
        "**Como ler a margem:** mostra quantos centavos sobram de cada R$ 1,00 de prêmio ganho "
        f"(em {top}, sobram **{_pct(d.loc[top, 'margem'])}**; em {bot}, apenas **{_pct(d.loc[bot, 'margem'])}**). "
        "A margem é sempre o que resta após três blocos de custo: "
        "`100% − Sinistralidade − Resseguro líquido − Despesa comercial`."
    )
    if len(d) > 1:
        dif = {k: comp[top][k] - comp[bot][k] for k in ("sin", "resseg", "com")}
        gap_pp = f"{(d.loc[top, 'margem'] - d.loc[bot, 'margem']) * 100:.1f}".replace(".", ",")
        explicacao += (
            f"\n\n**O que explica os {gap_pp} pp de vantagem de {top} sobre {bot}:** "
            f"sinistralidade ({A.f_pp(-dif['sin'])}), resseguro líquido ({A.f_pp(-dif['resseg'])}) "
            f"e despesa comercial ({A.f_pp(-dif['com'])}) a favor de {top}. "
        )
        if "Garantia" in comp:
            explicacao += (
                f"Vale notar também **Garantia**: mesmo com sinistralidade muito baixa ({_pct(comp['Garantia']['sin'])}), "
                f"ela cede bastante risco ao ressegurador ({_pct(comp['Garantia']['resseg'])} de resseguro líquido), "
                f"fechando em {_pct(comp['Garantia']['margem'])} de margem."
            )

    linhas = [
        [l, _pct(comp[l]["sin"]), _pct(comp[l]["resseg"]), _pct(comp[l]["com"]), _pct(comp[l]["margem"])]
        for l in d.index
    ]
    nota = (
        "**Leitura conjunta:** margem alta em mercado pequeno não resolve escala sozinha "
        "(por isso Q6 deve ser lida sempre junto com Q1 e Q5). "
        "Resseguro líquido = despesa com resseguro − receita com resseguro."
    )
    corpo = (
        explicacao
        + "\n\n"
        + _tabela(["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Margem"], linhas)
        + "\n\n"
        + nota
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

    if pct_top != abs_top:
        vezes = d.loc[abs_top, "abs"] / max(d.loc[pct_top, "abs"], 1.0)
        explicacao = (
            "**Por que porcentagem e valor absoluto apontam líderes diferentes (efeito base pequena)?** "
            "Porcentagem mede **velocidade**; valor absoluto mede **volume de dinheiro novo**.\n\n"
            f"- **{pct_top} (1º em %):** cresceu **{_pct(d.loc[pct_top, 'pct'])}** ({_pct(d.loc[pct_top, 'cagr'])} ao ano), "
            f"mas partiu de uma base pequena ({A.f_bi(d.loc[pct_top, 'primeiro'])} em {c.a0}), somando **{A.f_bi(d.loc[pct_top, 'abs'])}**.\n"
            f"- **{abs_top} (1º em R$):** cresceu num ritmo percentual menor ({_pct(d.loc[abs_top, 'pct'])}), "
            f"mas sobre uma base muito maior ({A.f_bi(d.loc[abs_top, 'primeiro'])}), adicionando **{A.f_bi(d.loc[abs_top, 'abs'])}** "
            f"— cerca de **{vezes:.1f}×** o volume em reais que {pct_top} trouxe ao mercado.".replace(".", ",")
        )
    else:
        explicacao = (
            f"**{pct_top}** lidera tanto em velocidade ({_pct(d.loc[pct_top, 'pct'])}) "
            f"quanto em volume adicionado (+{A.f_bi(d.loc[pct_top, 'abs'])})."
        )

    linhas = [
        [l, A.f_bi(r["primeiro"]), A.f_bi(r["ultimo"]), A.f_bi(r["abs"]), _pct(r["pct"]), _pct(r["cagr"])]
        for l, r in d.sort_values("pct", ascending=False).iterrows()
    ]
    nota = (
        "**Nota:** CAGR é a taxa média composta de crescimento por ano no intervalo selecionado. "
        "Os valores são nominais, portanto o crescimento inclui a inflação do período."
    )
    corpo = (
        explicacao
        + "\n\n"
        + _tabela(
            ["LOB", f"Prêmio {c.a0}", f"Prêmio {c.a1}", "Variação absoluta", "Variação %", "Ao ano (CAGR)"],
            linhas,
        )
        + "\n\n"
        + nota
    )
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
        curta += f"operam próximas do mercado, exceto em {_lista(partes)}."
    else:
        curta += "operam muito próximas da média do mercado (diferenças menores que 2 pp)."

    explicacao = (
        "**Como definimos 'relevante':** ordenamos todas as seguradoras ativas da maior para a menor em prêmio "
        "e selecionamos o grupo que soma **80% do mercado (regra de Pareto)**. Em vez de olhar 50+ empresas, "
        f"vemos que apenas **{intervalo} seguradoras** concentram a maior parte do volume em cada LOB.\n\n"
        f"**Estrutura competitiva:** a concentração é **moderada** (Top 5 entre {_pct(min(top5s), 0)} e {_pct(max(top5s), 0)}): "
        "nenhuma LOB é um monopólio fechado, mas também nenhuma é totalmente pulverizada. "
        "Na comparação contra o mercado inteiro, as relevantes tendem a acompanhar a média (já que compõem 80% dela), "
        "com vantagens de escala/seleção mais visíveis onde o diferencial passa de 2 pp."
    )

    nota = (
        "**Onde aprofundar:** na aba **Concorrência**, você pode escolher qualquer LOB para ver a lista "
        "completa das seguradoras do top 80%, a curva acumulada de Pareto e o gráfico de dispersão "
        "(Sinistralidade × Margem) destacando a estrela da Akad."
    )
    corpo = (
        explicacao
        + "\n\n"
        + _tabela(
            ["LOB", "Ativas no período", "Relevantes (80%)", "Top 5", "Sinistralidade das relevantes (vs mercado)",
             "Margem das relevantes (vs mercado)", "Líderes (Top 3)"],
            linhas,
            esq={0, 6},
        )
        + "\n\n"
        + nota
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

    nivel = t["sin_media"].idxmin()
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
            f"{nivel} é a mais saudável em nível puro de sinistralidade ({_pct(t.loc[nivel, 'sin_media'])} em média); "
            f"no conjunto margem + sinistralidade + crescimento, {atrativa} é a mais atrativa."
        )

    melhora = [f"{l} ({A.f_pp(r['slope'])}/ano)" for l, r in t.iterrows() if not _nan(r["slope"]) and r["slope"] < -0.005]
    piora = [f"{l} ({A.f_pp(r['slope'])}/ano)" for l, r in t.iterrows() if not _nan(r["slope"]) and r["slope"] > 0.005]
    estavel = [l for l, r in t.iterrows() if not _nan(r["slope"]) and abs(r["slope"]) <= 0.005]

    tem_serie = bool(t["slope"].notna().any())
    intro = (
        "**Por que olhar 3 dimensões (nível, tendência e volatilidade)?** "
        "Uma LOB saudável não é apenas a que tem média baixa hoje: é preciso ver se o risco está "
        "**melhorando ou piorando** ano a ano e o quanto ele **oscila (volatilidade)** — porque picos "
        "repentinos de sinistralidade consomem capital e geram prejuízos inesperados."
    )

    pontos = []
    if tem_serie:
        pontos.append(
            "**Direção da sinistralidade:** "
            + "; ".join(
                x for x in [
                    f"melhora consistente em {_lista(melhora)}" if melhora else "",
                    f"tendência de piora em {_lista(piora)}" if piora else "",
                    f"estável em {_lista(estavel)}" if estavel else "",
                ] if x
            )
            + ". Quando os sinistros crescem menos que o prêmio ao ano, a sinistralidade cai (e vice-versa)."
        )
        if len(t) > 1:
            estavel_top, volatil = t["vol"].idxmin(), t["vol"].idxmax()
            pontos.append(
                f"**Previsibilidade vs risco de susto:** **{estavel_top}** é a mais previsível "
                f"(desvio anual de apenas {_pct(t.loc[estavel_top, 'vol'])}), mas estabilizada em patamar alto "
                f"({_pct(t.loc[estavel_top, 'sin_media'])}). Já **{volatil}** é a mais imprevisível "
                f"(desvio de {_pct(t.loc[volatil, 'vol'])}; {pior_txt.get(volatil, '')})."
            )
        if len(t) > 1 and nivel != atrativa:
            cresc_atr = (
                f" e crescimento de {_pct(c.cresc.loc[atrativa, 'pct'])}"
                if not c.cresc.empty and atrativa in c.cresc.index else ""
            )
            pontos.append(
                f"**Qual escolher como mais saudável/atrativa?** **{nivel}** vence em nível absoluto de risco "
                f"({_pct(t.loc[nivel, 'sin_media'])}), mas apresenta {_rotulo_tendencia(t.loc[nivel, 'slope'])}. "
                f"Olhando o pacote completo de atratividade, **{atrativa}** se destaca por combinar a maior margem "
                f"({_pct(c.lob.loc[atrativa, 'margem'])}), sinistralidade controlada ({_pct(c.lob.loc[atrativa, 'sinistralidade'])}, "
                f"com {_rotulo_tendencia(t.loc[atrativa, 'slope'])}){cresc_atr}."
            )
    else:
        pontos.append("Selecione pelo menos dois anos no filtro para medir tendência e volatilidade.")

    linhas = [
        [l, _pct(r["sin_media"]), _pct(r["vol"]), _rotulo_tendencia(r["slope"]), pior.get(l, "–"),
         _pct(r["cresc_sinistro"]), _pct(cagr_premio.get(l, math.nan))]
        for l, r in t.sort_values("sin_media").iterrows()
    ]
    tabela = _tabela(
        ["LOB", "Sinistralidade média anual", "Volatilidade (desvio)", "Tendência", "Pior ano",
         "Sinistros ao ano", "Prêmio ao ano"],
        linhas,
        esq={0, 3, 4},
    )
    nota = (
        "**Método:** aqui usamos a média simples das sinistralidades anuais apenas para medir volatilidade "
        "(desvio-padrão) e tendência (inclinação da reta em pp/ano; entre −0,5 e +0,5 pp/ano = estável). "
        "Para o nível oficial acumulado do período (soma ÷ soma), consulte a Q3."
    )
    corpo = intro + "\n\n" + "\n".join(f"- {p}" for p in pontos) + "\n\n" + tabela + "\n\n" + nota
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
        curta += f"; nas demais ainda é subescala: {_lista([desc(l) for l in sub])}." if sub else "."
    else:
        curta = f"A Akad é subescala em todas as LOBs selecionadas: {_lista([desc(l) for l in ak.index])}."

    marca = (
        "**Contexto indispensável (a virada de 2022):** a operação começou no Brasil em 2012 como "
        "**Argo Seguros**, foi comprada em **2021** por um consórcio liderado pela **GP Investments** e "
        "rebatizada como **Akad Seguros em junho de 2022**. Como o código SUSEP (`02798`) é o mesmo, os "
        "dados de 2020–2025 formam uma série contínua, mas misturam duas gestões: **2020–2021 é Argo** "
        "e **2022 em diante é Akad**."
    )

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

    if a0 == a1:
        corpo = marca + "\n\n" + tabela + "\n\nRelevante = top 5 em prêmio na LOB ou share ≥ 5% no último ano."
        return _item("10", pergunta, curta, corpo)

    melhorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] < r["rank0"]]
    piorou = [l for l, r in ak.iterrows() if not _nan(r["rank0"]) and not _nan(r["rank1"]) and r["rank1"] > r["rank0"]]
    traj = (
        f"**Evolução da posição:** a Akad ganhou posições em **{len(melhorou)} de {len(ak)} LOBs** ({_lista(melhorou)})"
        if melhorou else "**Evolução da posição:** nenhuma LOB ganhou posições"
    )
    if piorou:
        det = []
        atv = A.ativas_por_ano(c.base, "premio")
        for l in piorou:
            r = ak.loc[l]
            det.append(
                f"**{l}**, onde o posto caiu de {int(r['rank0'])}º para {int(r['rank1'])}º mesmo com o share "
                f"subindo ({_pct(r['share0'])} → {_pct(r['share1'])}), porque o mercado recebeu mais concorrentes "
                f"({int(atv.loc[l, a0])} → {int(atv.loc[l, a1])} ativas)"
            )
        traj += "; única exceção: " + "; ".join(det)
    traj += "."

    fase_txt = ""
    if c.fase_distinta and c.f0 != c.f1:
        partes = []
        for l in ak.index:
            s0 = c.premio_ano(l, c.f0, True) / max(c.premio_ano(l, c.f0), 1)
            s1 = c.premio_ano(l, c.f1, True) / max(c.premio_ano(l, c.f1), 1)
            partes.append(f"{l}: {_pct(s0)} → {_pct(s1)}")
        fase_txt = f"**Recorte da fase Akad ({c.f0}–{c.f1}):** " + " | ".join(partes) + "."

    fatos = []
    for l, r in ak.iterrows():
        mult_ak = _mult(r["premio0"], r["premio1"])
        mult_mk = _mult(c.premio_ano(l, a0), c.premio_ano(l, a1))
        m0, m1 = _margem_akad_ano(c.base, l, a0), _margem_akad_ano(c.base, l, a1)
        linha = (
            f"**{l}:** prêmio {A.f_mi(r['premio0'])} → {A.f_mi(r['premio1'])} "
            f"({_x(mult_ak)} vs {_x(mult_mk)} do mercado); margem Akad {_pct(m0)} → {_pct(m1)}."
        )
        if math.isfinite(mult_ak) and mult_ak >= 8:
            linha += " Partiu de base quase zero — na prática, reflete lançamento/ativação comercial da linha."
        elif relevante(r) and not _nan(m0) and not _nan(m1):
            if m1 < m0 - 0.05:
                linha += " **Atenção:** acelerou volume, mas sacrificando a margem."
            elif m1 > m0 + 0.05:
                linha += " **Destaque:** ganhou liderança e ainda expandiu a margem."
        fatos.append(linha)

    hip = (
        "**O que pode explicar as mudanças (hipóteses de negócio):** o SES registra o resultado, mas não "
        "prova a causa interna. Os movimentos são consistentes com o reposicionamento pós-2022 da Akad "
        "(foco digital em corretores e PMEs, novo apetite de risco, lançamento de produtos como Empresarial "
        "e política própria de preço e resseguro). Confirmar causalidade exige dados internos."
    )

    blocos = [marca, traj]
    if fase_txt:
        blocos.append(fase_txt)
    blocos.append(tabela)
    blocos.append("**Raio-X do movimento por LOB:**\n\n" + "\n".join(f"- {f}" for f in fatos))
    blocos.append(hip)
    blocos.append("Critério de relevância na Q10: top 5 em prêmio na LOB ou share ≥ 5% no último ano.")
    return _item("10", pergunta, curta, "\n\n".join(blocos))


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
            f"supera mercado, pares e relevantes em margem (sem piorar a sinistralidade) em {_lista(consistentes)}"
        )
    if abaixo:
        partes.append(f"fica abaixo dos três grupos em margem em {_lista(abaixo)}")
    if mistas:
        partes.append(f"tem desempenho misto em {_lista(mistas)}")
    curta = "A Akad " + "; ".join(partes) + "."

    intro = (
        "**Como comparamos:** avaliamos a Akad contra **3 réguas** em **margem** e **sinistralidade**: "
        "(1) **Mercado inteiro** da LOB; (2) **Pares de porte** (seguradoras com prêmio entre 1/3× e 3× o da Akad "
        "no último ano); e (3) **Relevantes** (top 80% do prêmio, excluindo a Akad). "
        "Diferenças de até 1 pp são tratadas como *em linha*."
    )

    blocos = [
        intro,
        f"**Comparação no período {c.periodo}:**",
        _tabela_comparacao(comp),
        "\n".join(f"- {v}" for v in veredito),
    ]

    if c.fase_distinta and c.f0 != c.f1:
        comp_f = _comparacao(c.fase, c.lobs)
        if not comp_f.empty:
            blocos.append(f"**Recorte da fase Akad ({c.f0}–{c.f1}):**")
            blocos.append(_tabela_comparacao(comp_f))

    # Decomposição da diferença de margem
    ref_df = c.fase
    ref_rot = f"{c.f0}–{c.f1}" if c.f0 != c.f1 else str(c.f0)
    linhas, notas = [], []
    for l in comp.index:
        k = _contribuicoes(ref_df, l)
        if any(_nan(k[x]) for x in k):
            continue
        linhas.append([l, A.f_pp(k["sin"]), A.f_pp(k["resseg"]), A.f_pp(k["com"]), A.f_pp(k["total"])])
        notas.append(f"**{l} ({A.f_pp(k['total'])} vs mercado):** principal motor = {_driver(k)}.")

    if linhas:
        blocos.append(
            f"**De onde vem a diferença de margem ({ref_rot})?** "
            "Para entender *por que* a Akad ganha ou perde margem frente ao mercado, abrimos a diferença nos 3 componentes "
            "(valores positivos ajudam a Akad; negativos prejudicam):"
        )
        blocos.append(
            _tabela(["LOB", "Sinistralidade", "Resseguro líquido", "Despesa comercial", "Diferença de margem"], linhas)
        )
        blocos.append("\n".join(f"- {n}" for n in notas))
        blocos.append(
            "**Atenção ao resseguro:** um efeito positivo em *resseguro líquido* (como em E&O) significa que a Akad "
            "cede menos risco ao ressegurador do que a média do mercado. Isso eleva a margem nos anos bons, mas exige "
            "mais capital e aumenta a exposição a sinistros grandes."
        )

    return _item("11", pergunta, curta, "\n\n".join(blocos))


# --------------------------------------------------------------------------
# Q12
# --------------------------------------------------------------------------

PAPEL = {
    "E&O": ("Núcleo", "defender liderança e expandir o mercado"),
    "Transportes": ("Corrigir (urgente)", "rentabilizar antes de crescer"),
    "RCG": ("Aposta seletiva", "crescer em nichos com controle de acumulação"),
    "Garantia": ("Opcional", "só via parceria ou nicho específico"),
    "Empresarial": ("Opcional", "só se reduzir o custo comercial via digital"),
}


def _q12(c: _Ctx) -> dict:
    pergunta = "Em qual LOB a Akad deveria focar nos próximos anos? Qual deve ser a estratégia?"
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
            A.f_din(d["lucro_a"]), _pct(d["mix"], 0), f"**{papel}**: {acao}",
        ])
    tabela = _tabela(
        ["LOB", "Share", "Margem Akad vs mercado", "Sinistr. Akad vs mercado",
         "Resultado técnico Akad", f"% do prêmio em {c.f1}", "Papel estratégico"],
        linhas,
        esq={0, 6},
    )

    curta = (
        "Focar em E&O como núcleo de crescimento, corrigir urgentemente a rentabilidade de Transportes, "
        "crescer seletivamente em RCG e manter Garantia e Empresarial como opcionais."
    )

    partes = [
        f"**Base da decisão:** olhamos a fase Akad (**{c.fase_rotulo}**), pois a estratégia atual nasce após "
        "a compra pela GP (2021) e a troca de marca (junho de 2022).",
        tabela,
    ]

    def d(l: str) -> dict | None:
        return dados.get(l)

    eo, tr = d("E&O"), d("Transportes")
    if eo:
        txt = (
            f"**1. E&O — Núcleo (defender e expandir o mercado):** a Akad já é líder ({_pct(eo['s1'])} em {c.f1}), "
            f"com margem de **{_pct(eo['mg_a'])}** (vs {_pct(eo['mg_m'])} do mercado) e sinistralidade controlada "
            f"({_pct(eo['sin_a'])} vs {_pct(eo['sin_m'])})."
        )
        if tr and tr["premio_a"] > 0 and eo["premio_a"] > 0:
            txt += (
                f" Em {c.fase_rotulo}, E&O gerou **{A.f_din(eo['lucro_a'])}** de resultado técnico com "
                f"{A.f_din(eo['premio_a'])} de prêmio — quase 3× o resultado de Transportes "
                f"({A.f_din(tr['lucro_a'])}), que precisou de {A.f_din(tr['premio_a'])} de prêmio!"
            )
        partes.append(txt)
        partes.append(
            "**3 pontos de atenção em E&O (para antecipar perguntas críticas):**\n"
            f"- **Resseguro e capital:** a vantagem de margem vem sobretudo de ceder pouco risco "
            f"(resseguro contribui com {A.f_pp(eo['k']['resseg'])}; sinistralidade com {A.f_pp(eo['k']['sin'])}). "
            "É preciso monitorar solvência e apetite de risco.\n"
            "- **Cauda longa:** em carteiras jovens que crescem rápido, sinistros podem demorar anos para aparecer — "
            "validar periodicamente a suficiência das reservas.\n"
            f"- **Teto de mercado:** E&O ainda é pequena ({A.f_bi(c.premio_ano('E&O', c.f1))} em {c.f1}) e a Akad já "
            f"tem {_pct(eo['s1'], 0)}. Crescer exige **criar mercado** (novas profissões, PMEs digitais, cross-sell "
            "com Cyber), não apenas brigar por share."
        )

    if tr:
        partes.append(
            f"**2. Transportes — Corrigir antes de crescer:** representa **{_pct(tr['mix'], 0)}** do prêmio da Akad "
            f"em {c.f1}, mas a margem na fase caiu para **{_pct(tr['mg_a'])}** (vs {_pct(tr['mg_m'])} do mercado). "
            f"A diferença ({A.f_pp(tr['k']['total'])}) vem de **sinistralidade ({A.f_pp(tr['k']['sin'])})** e "
            f"**despesa comercial ({A.f_pp(tr['k']['com'])})**, parcialmente aliviadas pelo resseguro "
            f"({A.f_pp(tr['k']['resseg'])}). Como essa LOB domina o faturamento, recuperar margem aqui é o que "
            "mais move o resultado total: reprecificar por rota/carga, investir em gestão de risco/antifraude, "
            "revisar comissões e cortar segmentos deficitários."
        )

    rcg = d("RCG")
    if rcg:
        vol_rcg = c.trend.loc["RCG", "vol"] if "RCG" in c.trend.index else math.nan
        partes.append(
            f"**3. RCG — Aposta seletiva:** ainda pequena ({_pct(rcg['s1'])} de share), mas muito rentável "
            f"({_pct(rcg['mg_a'])} vs {_pct(rcg['mg_m'])} do mercado) e com sinistralidade bem menor "
            f"({_pct(rcg['sin_a'])} vs {_pct(rcg['sin_m'])}). Como o mercado é volátil"
            + (f" (desvio anual de {_pct(vol_rcg)})" if not _nan(vol_rcg) else "")
            + ", a estratégia é crescer em nichos selecionados com limites rígidos de acumulação e resseguro."
        )

    gar, emp = d("Garantia"), d("Empresarial")
    if gar or emp:
        itens_op = []
        if gar:
            itens_op.append(
                f"**Garantia ({_pct(gar['s1'])} de share):** mercado grande e lucrativo, mas a Akad opera abaixo "
                f"({_pct(gar['mg_a'])} vs {_pct(gar['mg_m'])}), puxada por {_driver(gar['k'])}. Só entrar com nicho/parceria."
            )
        if emp:
            itens_op.append(
                f"**Empresarial ({_pct(emp['s1'])} de share):** margem baixa ({_pct(emp['mg_a'])} vs {_pct(emp['mg_m'])}) "
                f"puxada por {_driver(emp['k'])} (custo de distribuição alto de produto novo). Só escalar via canal digital "
                "de PMEs com comissão menor."
            )
        partes.append("**4. Garantia e Empresarial — Opcionais:**\n" + "\n".join(f"- {x}" for x in itens_op))

    partes.append(
        "**5 alavancas transversais de execução:**\n"
        "- **Canais de venda:** manter o corretor no centro, usando plataforma digital/APIs para baratear aquisição em Empresarial e Transportes.\n"
        "- **Pricing e subscrição:** modelos granulares por rota, segmento e perfil de risco.\n"
        "- **Gestão de sinistros:** prevenção a roubos/acidentes em Transportes e regulação ágil.\n"
        "- **Resseguro:** calibrar retenção em E&O (proteção de capital) e custo de cessão em Garantia.\n"
        "- **Infraestrutura e capital:** sustentar solvência para o crescimento em E&O e RCG."
    )
    partes.append(
        "**Limites da análise:** dados nominais do SES (sem despesas administrativas, impostos e resultado financeiro). "
        "As ações devem ser validadas com dados internos de preço, comissionamento por canal e tratados de resseguro."
    )
    return _item("12", pergunta, curta, "\n\n".join(partes))


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
