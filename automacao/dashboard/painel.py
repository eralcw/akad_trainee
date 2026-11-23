"""Dashboard interativo do case: mercado, rentabilidade, risco, concorrência e Akad."""

from __future__ import annotations

import html as html_lib

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import analise
from . import respostas as respostas_mod

INK = "#143057"
MUTED = "#5B6485"
RULE = "#E4E6F4"
PINE = "#E9256A"
LILAC = "#6B72D8"
PINK = "#F7A3BF"
NAVY = "#143057"
SIGNAL = "#6B72D8"
NEGATIVO = "#9AA0B5"
CFG = {
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": "reset",
    "modeBarButtonsToRemove": [
        "lasso2d", "select2d", "autoScale2d", "toggleSpikelines",
        "hoverCompareCartesian", "hoverClosestCartesian", "zoomIn2d", "zoomOut2d",
    ],
    "toImageButtonOptions": {"filename": "akad-grafico", "scale": 2},
}


# --------------------------------------------------------------------------
# Helpers visuais
# --------------------------------------------------------------------------

def _layout(fig, height: int = 330, ytitle: str | None = None, xtitle: str | None = None,
            legend: bool = True, topo: int = 44, base: int = 8):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=13, color=INK),
        separators=",.",
        margin=dict(l=8, r=8, t=topo, b=base),
        height=height,
        showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=12),
                    bgcolor="rgba(0,0,0,0)", title=dict(text="")),
        hoverlabel=dict(font_family="IBM Plex Mono"),
    )
    fig.update_xaxes(showgrid=False, linecolor=RULE, tickfont=dict(size=12), automargin=True)
    fig.update_yaxes(gridcolor="rgba(18,32,29,0.08)", zeroline=False, tickfont=dict(size=12),
                     automargin=True)
    if ytitle:
        fig.update_yaxes(title=dict(text=ytitle, font=dict(size=12, color=MUTED)))
    if xtitle:
        fig.update_xaxes(title=dict(text=xtitle, font=dict(size=12, color=MUTED)))
    return fig


def _titulo(fig, principal: str, sub: str = ""):
    """Titulo que diz a conclusao; o tema vai no subtitulo."""
    texto = f"<b>{principal}</b>"
    if sub:
        texto += f"<br><span style='font-size:12px;color:{MUTED}'>{sub}</span>"
    fig.update_layout(title=dict(text=texto, x=0, xanchor="left",
                                 font=dict(size=15, color=INK)))
    return fig


def _plot(fig, height: int = 330, ytitle: str | None = None, xtitle: str | None = None,
          legend: bool = True, topo: int = 44, titulo: str | None = None, sub: str = "",
          base: int | None = None):
    if titulo:
        _titulo(fig, titulo, sub)
        topo = max(topo, 74 if sub else 58)
    abaixo = bool(legend and titulo)
    if abaixo:
        base = 96 if base is None else base
    fig = _layout(fig, height, ytitle, xtitle, legend, topo, base or 8)
    if abaixo:
        fig.update_layout(legend=dict(orientation="h", y=-0.26, x=0.0,
                                      font=dict(size=12), title=dict(text="")))
    st.plotly_chart(fig, width="stretch", config=CFG)


def _maior_no_topo(fig):
    """Nas barras horizontais, coloca a maior categoria no topo."""
    fig.update_yaxes(categoryorder="total ascending", title=None)
    return fig


def _folga_x(fig, valores, folga: float = 0.22):
    """Abre espaco no eixo X para rotulos escritos fora das barras."""
    vals = [float(v) for v in valores if pd.notna(v)]
    if not vals:
        return fig
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    span = (hi - lo) or 1.0
    esq = lo - span * folga if lo < 0 else 0.0
    fig.update_xaxes(range=[esq, hi + span * folga])
    return fig


def _heatmap_html(lob_ano: pd.DataFrame) -> str:
    """Mapa de calor em tabela HTML: estavel e legivel em qualquer navegador."""
    pv = lob_ano.pivot(index="lob", columns="ano", values="sinistralidade")
    pv = pv.reindex([l for l in analise.LOB_ORDEM if l in pv.index])
    faixas = [(0.20, "#FCE9EF", "#143057"), (0.35, "#F7A3BF", "#143057"),
              (0.50, "#E9749F", "#FFFFFF"), (0.65, "#C84572", "#FFFFFF"),
              (99.0, "#8C1D45", "#FFFFFF")]

    def estilo(v):
        if pd.isna(v):
            return "#F4F5FD", "#5B6485"
        for limite, fundo, tinta in faixas:
            if float(v) < limite:
                return fundo, tinta
        return "#8C1D45", "#FFFFFF"

    cab = "".join(f"<th>{int(c)}</th>" for c in pv.columns)
    linhas = []
    for lob, row in pv.iterrows():
        cels = [f'<th class="rowh">{html_lib.escape(lob)}</th>']
        for v in row:
            fundo, tinta = estilo(v)
            texto = "–" if pd.isna(v) else analise.f_pct(float(v))
            cels.append(f'<td style="background:{fundo};color:{tinta}">{texto}</td>')
        linhas.append("<tr>" + "".join(cels) + "</tr>")
    return ('<table class="heatmap"><thead><tr><th></th>' + cab + "</tr></thead><tbody>"
            + "".join(linhas) + "</tbody></table>")


def _secao(num: str, titulo: str) -> None:
    st.markdown(
        f'<div class="secao"><span class="qtag">{html_lib.escape(num)}</span>'
        f'<h4>{html_lib.escape(titulo)}</h4></div>',
        unsafe_allow_html=True,
    )


def _sub(titulo: str) -> None:
    st.markdown(f'<div class="subsecao"><h5>{html_lib.escape(titulo)}</h5></div>',
                unsafe_allow_html=True)


def _ledger(itens) -> None:
    blocos = []
    for i, (lab, val, nota) in enumerate(itens):
        blocos.append(
            f'<div><span class="lab">{html_lib.escape(lab)}</span>'
            f'<span class="val">{html_lib.escape(str(val))}</span>'
            f'<span class="nota">{html_lib.escape(str(nota))}</span></div>'
        )
    st.markdown('<div class="ledger">' + "".join(blocos) + "</div>", unsafe_allow_html=True)


def _tab(df: pd.DataFrame, cols, fmts, headers) -> None:
    d = df.copy()
    for c, f in fmts.items():
        if c in d.columns:
            d[c] = d[c].map(f)
    st.dataframe(
        d[cols].rename(columns=headers),
        hide_index=True,
        width="stretch",
    )


@st.cache_data(show_spinner=False)
def _base_cache() -> pd.DataFrame:
    return analise.carregar_base()


# --------------------------------------------------------------------------
# Abas
# --------------------------------------------------------------------------

def _visao(lob: pd.DataFrame, lob_ano: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    m = analise.metricas(base_f)
    _ledger(
        [
            ("Prêmio ganho", analise.f_bi(m["premio"]), "período filtrado"),
            ("Sinistralidade", analise.f_pct(m["sinistralidade"]), "soma de sinistros ÷ soma de prêmios"),
            ("Resultado técnico", analise.f_bi(m["lucro"]), "não é lucro contábil"),
            ("Margem", analise.f_pct(m["margem"]), "resultado técnico ÷ prêmio"),
        ]
    )

    d = lob_ano.copy()
    d["premio_bi"] = d["premio"] / 1e9
    fig = px.line(
        d, x="ano", y="premio_bi", color="lob", markers=True,
        color_discrete_map=analise.LOB_COR,
        labels={"ano": "ano", "premio_bi": "prêmio ganho (R$ bi)", "lob": "LOB"},
    )
    fig.update_traces(line=dict(width=2.2), marker=dict(size=5))
    fig.update_xaxes(dtick=1)
    topo = lob["lob"].iloc[0]
    cresceu = all(
        g.sort_values("ano")["premio"].iloc[-1] >= g.sort_values("ano")["premio"].iloc[0]
        for _, g in lob_ano.groupby("lob")
    )
    titulo = f"{topo} lidera em todos os anos" + ("; todas as LOBs cresceram" if cresceu else "")
    _plot(fig, 360, ytitle="R$ bilhões", legend=True,
          titulo=titulo, sub="prêmio ganho por LOB e ano, valores nominais")

    pv = lob_ano.pivot(index="lob", columns="ano", values="sinistralidade")
    pv = pv.reindex([l for l in analise.LOB_ORDEM if l in pv.index])
    if not pv.empty and pv.notna().any().any():
        pico_lob, pico_ano = pv.stack().idxmax()
        _sub(f"Sinistralidade por LOB e ano — pior ponto: {pico_lob} em {pico_ano} "
             f"({analise.f_pct(float(pv.loc[pico_lob, pico_ano]))})")
        st.markdown(_heatmap_html(lob_ano), unsafe_allow_html=True)
        st.caption("Cor mais escura = maior parcela do prêmio consumida por sinistro. "
                   "Cada célula é a razão de somas do ano: sinistro ÷ prêmio ganho.")
    else:
        st.info("Sem anos suficientes para o mapa de calor.")

    st.markdown("#### Leitura rápida")
    for item in resp[:3] + [resp[6], resp[8]]:
        st.markdown(f"**{item['n']}.** {item['pergunta']}  \n{item['curta']}")


def _mercado(lob: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    # ---------------- Q1 ----------------
    _secao("Q1", "prêmio ganho por LOB")
    total = float(lob["premio"].sum())
    top = lob["lob"].iloc[0]
    d = lob.sort_values("premio").copy()
    d["premio_bi"] = d["premio"] / 1e9
    d["rotulo"] = [f"{analise.f_bi(v)}  ({analise.f_pct(v / total, 0)})" for v in d["premio"]]
    fig = px.bar(
        d, x="premio_bi", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text="rotulo",
        labels={"premio_bi": "prêmio ganho (R$ bi)", "lob": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    _maior_no_topo(fig)
    _folga_x(fig, d["premio_bi"], 0.34)
    _plot(fig, 310, legend=False,
          titulo=f"{top} é a maior LOB: {analise.f_bi(lob['premio'].max())} ({analise.f_pct(lob['premio'].max() / total, 0)})",
          sub=f"prêmio ganho acumulado, {periodo_de(base_f)}; porcentagem do total das LOBs")
    st.caption(resp[0]["curta"])

    # ---------------- Q2 ----------------
    _secao("Q2", "seguradoras ativas em cada ano")
    ativas = analise.ativas_por_ano(base_f)
    ativas_pres = analise.ativas_por_ano(base_f, "presenca")
    anos = sorted(ativas.columns)
    if len(anos) >= 2:
        a0, a1 = anos[0], anos[-1]
        cats = [l for l in analise.LOB_ORDEM if l in ativas.index]
        linhas = []
        for lname in cats:
            linhas.append({"lob": lname, "ano": str(a0), "ativas": int(ativas.loc[lname, a0])})
            linhas.append({"lob": lname, "ano": str(a1), "ativas": int(ativas.loc[lname, a1])})
        df = pd.DataFrame(linhas)
        fig = px.bar(
            df, x="lob", y="ativas", color="ano", barmode="group",
            color_discrete_sequence=[NEGATIVO, NAVY],
            labels={"lob": "", "ativas": "seguradoras ativas", "ano": "ano"},
        )
        fig.update_traces(texttemplate="%{y}", textposition="outside", cliponaxis=False)
        alturas = df.groupby("lob")["ativas"].max()
        for lname in cats:
            var = int(ativas.loc[lname, a1] - ativas.loc[lname, a0])
            fig.add_annotation(
                x=lname, y=alturas.get(lname, 0) * 1.16,
                text=f"{var:+d}", showarrow=False,
                font=dict(size=11, color=INK if var >= 0 else MUTED),
            )
        fig.update_yaxes(range=[0, float(alturas.max()) * 1.28])
        lider = ativas[a1].idxmax()
        maior_var = (ativas[a1] - ativas[a0]).idxmax()
        var_max = int((ativas[a1] - ativas[a0]).max())
        _plot(fig, 330, legend=True,
              titulo=f"{lider} tem mais concorrentes ativos ({int(ativas.loc[lider, a1])})",
              sub=f"{maior_var} foi a que mais ganhou concorrentes: {var_max:+d} entre {a0} e {a1}")
        _tab(
            pd.DataFrame([
                {
                    "lob": l,
                    "ativas0": int(ativas.loc[l, a0]),
                    "ativas1": int(ativas.loc[l, a1]),
                    "var": f"{int(ativas.loc[l, a1] - ativas.loc[l, a0]):+d}",
                }
                for l in cats
            ]),
            ["lob", "ativas0", "ativas1", "var"], {},
            {"lob": "LOB", "ativas0": f"Ativas {a0}", "ativas1": f"Ativas {a1}", "var": "Variação"},
        )
        with st.expander("Empresas apenas cadastradas no SES (sem venda no ano)"):
            _tab(
                pd.DataFrame([
                    {"lob": l, "presenca0": int(ativas_pres.loc[l, a0]), "presenca1": int(ativas_pres.loc[l, a1])}
                    for l in cats
                ]),
                ["lob", "presenca0", "presenca1"], {},
                {"lob": "LOB", "presenca0": f"Linhas {a0}", "presenca1": f"Linhas {a1}"},
            )
        st.caption(resp[1]["curta"])

    # ---------------- Q7 ----------------
    _secao("Q7", "crescimento do prêmio no período")
    cresc = analise.crescimento(base_f)
    if cresc.empty:
        st.info("Selecione pelo menos dois anos para calcular crescimento.")
        return
    ini_ano, fim_ano = int(cresc["ano_ini"].iloc[0]), int(cresc["ano_fim"].iloc[0])
    fig = go.Figure()
    for lname, r in cresc.sort_values("pct").iterrows():
        cor = analise.LOB_COR.get(lname, PINE)
        fig.add_trace(go.Scatter(
            x=[r["primeiro"] / 1e9, r["ultimo"] / 1e9], y=[lname, lname],
            mode="lines", line=dict(color=cor, width=3), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[r["primeiro"] / 1e9], y=[lname], mode="markers",
            marker=dict(color=cor, size=8, line=dict(color="#FFFFFF", width=1)),
            showlegend=False,
            hovertemplate=f"{lname} {ini_ano}: R$ %{{x:.2f}} bi<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=[r["ultimo"] / 1e9], y=[lname], mode="markers+text",
            marker=dict(color=cor, size=12, line=dict(color="#FFFFFF", width=1)),
            text=[f"{analise.f_pct(r['pct'])}  |  {analise.f_bi(r['abs'])}"],
            textposition="middle right", textfont=dict(size=11),
            showlegend=False,
            hovertemplate=f"{lname} {fim_ano}: R$ %{{x:.2f}} bi<extra></extra>",
        ))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                             marker=dict(color=MUTED, size=8), name=str(ini_ano)))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                             marker=dict(color=INK, size=12), name=str(fim_ano)))
    _folga_x(fig, list(cresc["primeiro"] / 1e9) + list(cresc["ultimo"] / 1e9), 0.45)
    pct_top = cresc["pct"].idxmax()
    abs_top = cresc["abs"].idxmax()
    _plot(fig, 340, legend=True, xtitle="prêmio ganho, R$ bilhões",
          titulo=f"{pct_top} cresce mais em %; {abs_top} adiciona mais em reais",
          sub=f"cada linha liga {ini_ano} a {fim_ano}; rótulo à direita = variação % e valor absoluto")
    _tab(
        cresc.reset_index(),
        ["lob", "primeiro", "ultimo", "abs", "pct", "cagr"],
        {"primeiro": analise.f_bi, "ultimo": analise.f_bi, "abs": analise.f_bi,
         "pct": analise.f_pct, "cagr": analise.f_pct},
        {"lob": "LOB", "primeiro": str(ini_ano), "ultimo": str(fim_ano),
         "abs": "Variação R$", "pct": "Variação %", "cagr": "CAGR"},
    )
    st.caption(resp[6]["curta"])


def periodo_de(base_f: pd.DataFrame) -> str:
    anos = sorted(int(a) for a in base_f["ano"].unique())
    return f"{anos[0]}–{anos[-1]}" if len(anos) > 1 else str(anos[0])


def _rentabilidade(lob: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    # ordem unica para os dois graficos: maior premio no topo
    ordem = list(lob.sort_values("premio")["lob"])
    base_lob = lob.set_index("lob")

    _secao("Q5", "resultado técnico por LOB")
    d = base_lob.loc[ordem].reset_index().copy()
    d["lucro_bi"] = d["lucro"] / 1e9
    d["rotulo"] = d["lucro"].map(analise.f_bi)
    fig = px.bar(
        d, x="lucro_bi", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text="rotulo",
        labels={"lucro_bi": "resultado técnico (R$ bi)", "lob": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    _maior_no_topo(fig)
    _folga_x(fig, d["lucro_bi"], 0.28)
    top = lob.loc[lob["lucro"].idxmax(), "lob"]
    _plot(fig, 310, legend=False,
          titulo=f"{top} gera o maior resultado técnico: {analise.f_bi(lob['lucro'].max())}",
          sub=f"resultado técnico acumulado, {periodo_de(base_f)}")
    st.caption(resp[4]["curta"])

    _secao("Q6", "margem e composição do prêmio")
    d = base_lob.loc[ordem].reset_index().copy()
    fig = px.bar(
        d, x="margem", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["margem"].map(analise.f_pct),
        labels={"margem": "margem", "lob": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(tickformat=".0%")
    _maior_no_topo(fig)
    _folga_x(fig, d["margem"], 0.30)
    _plot(fig, 310, legend=False,
          titulo=f"{base_lob['margem'].idxmax()} tem a maior margem ({analise.f_pct(base_lob['margem'].max())})",
          sub="margem = resultado técnico ÷ prêmio ganho")
    st.caption(resp[5]["curta"])

    # composicao do premio: 100% empilhado (sinistralidade + resseguro + comissao + margem)
    comp = {l: analise.componentes(base_f[base_f["lob"] == l]) for l in ordem}
    dc = pd.DataFrame([
        {
            "lob": l,
            "Sinistralidade": comp[l]["sin"],
            "Resseguro líquido": comp[l]["resseg"],
            "Despesa comercial": comp[l]["com"],
            "Margem": comp[l]["margem"],
        }
        for l in ordem
    ])
    long = dc.melt(id_vars="lob", var_name="componente", value_name="valor")
    cores = {
        "Sinistralidade": "#D9668F",
        "Resseguro líquido": "#6B72D8",
        "Despesa comercial": "#B4723A",
        "Margem": "#2E7D5B",
    }
    fig = px.bar(
        long, x="valor", y="lob", color="componente", orientation="h",
        color_discrete_map=cores,
        labels={"valor": "% do prêmio ganho", "lob": "", "componente": ""},
    )
    fig.update_yaxes(categoryorder="array", categoryarray=ordem)
    fig.update_xaxes(tickformat=".0%")
    _plot(fig, 330, legend=True,
          titulo="De cada R$ 100 de prêmio, quanto vai para sinistro, resseguro, comissão e margem",
          sub="valores em % do prêmio; resseguro negativo (recuperação maior que o custo) soma a favor")
    st.caption(
        "Resultado técnico = prêmio ganho + receita com resseguro − sinistro ocorrido "
        "− despesa com resseguro − despesa comercial."
    )

    _tab(
        lob,
        ["lob", "premio", "lucro", "margem", "sinistralidade"],
        {"premio": analise.f_bi, "lucro": analise.f_bi, "margem": analise.f_pct,
         "sinistralidade": analise.f_pct},
        {"lob": "LOB", "premio": "Prêmio ganho", "lucro": "Resultado técnico",
         "margem": "Margem", "sinistralidade": "Sinistralidade"},
    )


def _sinistralidade(lob: pd.DataFrame, lob_ano: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    # ---------------- Q3 ----------------
    _secao("Q3", "sinistralidade agregada por LOB")
    d = lob.sort_values("sinistralidade").copy()
    fig = px.bar(
        d, x="sinistralidade", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["sinistralidade"].map(analise.f_pct),
        labels={"sinistralidade": "sinistralidade", "lob": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(tickformat=".0%")
    _maior_no_topo(fig)
    _folga_x(fig, d["sinistralidade"], 0.30)
    top = lob.loc[lob["sinistralidade"].idxmax(), "lob"]
    _plot(fig, 310, legend=False,
          titulo=f"{top} tem a maior sinistralidade: {analise.f_pct(lob['sinistralidade'].max())}",
          sub=f"sinistro ocorrido ÷ prêmio ganho, {periodo_de(base_f)}")
    st.caption(resp[2]["curta"])

    # ---------------- Q9: pequenos multiplos ----------------
    _secao("Q9", "tendência anual da sinistralidade")
    trend = analise.tendencias(base_f).set_index("lob")
    anos = sorted(int(a) for a in lob_ano["ano"].unique())
    span = max(anos[-1] - anos[0], 1)

    def rotulo_painel(l: str) -> str:
        if l not in trend.index or pd.isna(trend.loc[l, "slope"]):
            return l
        v = trend.loc[l, "slope"]
        if abs(v) * span < trend.loc[l, "vol"]:
            return f"{l} · sem tendência clara"
        return f"{l} · {'−' if v < 0 else '+'}{abs(v)*100:.1f} pp/ano".replace(".", ",")

    d9 = lob_ano.copy()
    d9["painel"] = d9["lob"].map(rotulo_painel)
    fig = px.line(
        d9, x="ano", y="sinistralidade", color="lob", facet_col="painel",
        facet_col_wrap=3, markers=True, color_discrete_map=analise.LOB_COR,
        labels={"ano": "", "sinistralidade": "", "lob": ""},
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=4))
    fig.update_yaxes(matches=None, tickformat=".1%", showticklabels=True, nticks=4)
    fig.update_xaxes(dtick=max(1, span // 2 if span > 1 else 1))
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font=dict(size=12)))
    fig.update_layout(showlegend=False)
    melhora = [l for l in trend.index if pd.notna(trend.loc[l, "slope"])
               and trend.loc[l, "slope"] < -0.005
               and abs(trend.loc[l, "slope"]) * span >= trend.loc[l, "vol"]]
    vol_max = trend["vol"].idxmax() if trend["vol"].notna().any() else None
    pedacos = []
    if melhora:
        pedacos.append(f"{', '.join(melhora)} {'melhora' if len(melhora) == 1 else 'melhoram'}")
    if vol_max is not None:
        pedacos.append(f"{vol_max} é a mais instável")
    titulo_q9 = "; ".join(pedacos) if pedacos else "Tendência da sinistralidade por LOB"
    _plot(fig, 560, legend=False,
          titulo=titulo_q9,
          sub="um painel por LOB, escala própria; título do painel = tendência anual")

    _tab(
        trend.reset_index(),
        ["lob", "sin_media", "vol", "slope", "cresc_sinistro", "margem_media"],
        {"sin_media": analise.f_pct, "vol": analise.f_pct,
         "slope": lambda v: f"{v*100:+.1f} pp/ano".replace(".", ",") if pd.notna(v) else "–",
         "cresc_sinistro": analise.f_pct, "margem_media": analise.f_pct},
        {"lob": "LOB", "sin_media": "Média anual", "vol": "Oscilação",
         "slope": "Tendência", "cresc_sinistro": "Crescimento do sinistro",
         "margem_media": "Margem média"},
    )

    # ---------------- Q9: volatilidade ----------------
    tr = analise.tendencias(base_f).merge(lob[["lob", "premio"]], on="lob", how="left")
    fig = px.scatter(
        tr, x="vol", y="sin_media", size="premio", color="lob", text="lob",
        color_discrete_map=analise.LOB_COR, size_max=45,
        labels={"vol": "oscilação (desvio-padrão)", "sin_media": "média anual", "lob": ""},
    )
    fig.update_traces(textposition="top center", textfont=dict(size=12))
    xmax, ymax = float(tr["vol"].max()), float(tr["sin_media"].max())
    xmin, ymin = float(tr["vol"].min()), float(tr["sin_media"].min())
    fig.update_xaxes(tickformat=".0%", range=[max(0, xmin - xmax * 0.22), xmax * 1.18])
    fig.update_yaxes(tickformat=".0%", range=[max(0, ymin * 0.55), ymax * 1.24])
    mx, my = float(tr["vol"].mean()), float(tr["sin_media"].mean())
    fig.add_vline(x=mx, line_dash="dot", line_color=RULE)
    fig.add_hline(y=my, line_dash="dot", line_color=RULE)
    for x, y, txt in [
        (max(0, xmin - xmax * 0.2), ymax * 1.2, "risco baixo · previsível"),
        (xmax * 1.14, ymax * 1.2, "risco alto · instável"),
    ]:
        fig.add_annotation(x=x, y=y, text=txt, showarrow=False,
                           font=dict(size=11, color=MUTED), xanchor="left" if x < mx else "right")
    _plot(fig, 400, legend=False,
          titulo="Garantia tem o menor risco; RCG é a mais instável",
          sub="tamanho = prêmio; eixo Y = média simples dos anos (a Q3 usa razão de somas)")
    st.caption(resp[8]["curta"])

    # ---------------- Q4 ----------------
    _secao("Q4", "maior sinistralidade por LOB")
    thr = st.slider("Participação mínima no prêmio da LOB (%)", 0, 5, 1, 1, format="%d%%") / 100
    q4 = analise.q4(base_f, min_share=thr)
    if q4.empty:
        st.info("Sem seguradoras acima do corte.")
    else:
        _maior = q4.sort_values(["lob", "sinistralidade"], ascending=[True, False]).groupby("lob").head(1)
        _tab(
            _maior,
            ["lob", "seguradora", "premio", "share", "sinistralidade", "margem"],
            {"premio": analise.f_mi, "share": analise.f_pct,
             "sinistralidade": analise.f_pct, "margem": analise.f_pct},
            {"lob": "LOB", "seguradora": "Maior sinistralidade", "premio": "Prêmio",
             "share": "Participação", "sinistralidade": "Sinistralidade", "margem": "Margem"},
        )
        akad_q4 = q4[q4["codigo_susep"] == analise.AKAD]
        if not akad_q4.empty:
            partes = ", ".join(
                f"{r.lob} ({analise.f_pct(r.sinistralidade)})" for r in akad_q4.itertuples()
            )
            st.caption(f"A própria Akad aparece entre as maiores sinistralidades em {partes}.")
        with st.expander("Ver as três maiores de cada LOB"):
            _tab(
                q4,
                ["lob", "seguradora", "premio", "share", "sinistralidade", "margem"],
                {"premio": analise.f_mi, "share": analise.f_pct,
                 "sinistralidade": analise.f_pct, "margem": analise.f_pct},
                {"lob": "LOB", "seguradora": "Seguradora", "premio": "Prêmio",
                 "share": "Participação", "sinistralidade": "Sinistralidade", "margem": "Margem"},
            )
        st.caption(respostas_mod.q4_curta(base_f, thr))
    st.caption("Sinistralidade negativa tipicamente reflete reversão de reserva; o corte de materialidade evita que empresas minúsculas dominem o ranking.")


def _concorrencia(base_f: pd.DataFrame, resp: list[dict]) -> None:
    _secao("Q8", "seguradoras relevantes e comparação com o mercado")
    lob_sel = st.selectbox("LOB", analise.LOB_ORDEM, index=0, key="concorrencia_lob")
    mesa, n, mercado = analise.relevantes(base_f, lob_sel)
    if mesa.empty:
        st.info("Sem seguradoras com prêmio positivo nesta LOB.")
        return

    st.caption(
        f"{n} seguradoras explicam 80% do prêmio de {lob_sel}. "
        f"Mercado: margem {analise.f_pct(mercado['margem'])} e sinistralidade {analise.f_pct(mercado['sinistralidade'])}."
    )

    busca = st.text_input(
        "Buscar seguradora (código SUSEP ou nome)", value="", key="conc_busca",
        placeholder="ex.: 02798 ou AKAD",
    ).strip()
    destaques = set()
    mesa_exibir = mesa
    if busca:
        q = busca.upper()
        achou = mesa[
            mesa["codigo_susep"].astype(str).str.contains(q, na=False)
            | mesa["seguradora"].astype(str).str.upper().str.contains(q, na=False)
        ]
        if achou.empty:
            st.warning("Nenhuma seguradora relevante desta LOB corresponde à busca.")
        else:
            mesa_exibir = achou
            destaques = set(achou["codigo_susep"])

    _tab(
        mesa_exibir,
        ["seguradora", "premio", "share", "sinistralidade", "margem", "delta_sin", "delta_margem"],
        {
            "premio": analise.f_mi, "share": analise.f_pct,
            "sinistralidade": analise.f_pct, "margem": analise.f_pct,
            "delta_sin": lambda v: f"{v*100:+.1f} pp".replace(".", ",") if pd.notna(v) else "–",
            "delta_margem": lambda v: f"{v*100:+.1f} pp".replace(".", ",") if pd.notna(v) else "–",
        },
        {"seguradora": "Seguradora", "premio": "Prêmio", "share": "Share", "sinistralidade": "Sinistralidade", "margem": "Margem", "delta_sin": "Δ sin. vs mercado", "delta_margem": "Δ margem vs mercado"},
    )

    seg = analise.por_seguradora(base_f[(base_f["lob"] == lob_sel) & (base_f["premio_ganho"] > 0)])
    seg = seg.sort_values("premio", ascending=False).reset_index(drop=True)
    seg["rank"] = range(1, len(seg) + 1)
    seg["cum"] = seg["share"].cumsum()

    # ---------------- Pareto ----------------
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=seg["rank"], y=seg["cum"], mode="lines+markers",
                             line=dict(color=LILAC, width=2), marker=dict(size=4),
                             name="share acumulado", hoverinfo="skip"))
    fig.add_hline(y=0.8, line_dash="dash", line_color=MUTED)
    fig.add_vline(x=n, line_dash="dot", line_color=RULE)
    fig.add_annotation(
        x=n, y=0.8, text=f"{n} seguradoras = 80%",
        showarrow=True, arrowhead=0, ax=28, ay=-24,
        font=dict(size=12, color=INK), bgcolor="rgba(255,255,255,0.9)",
    )
    fig.update_yaxes(tickformat=".0%", range=[0, 1.04])
    fig.update_xaxes(range=[0.5, len(seg) + 0.5])
    top5_total = float(seg["share"].head(5).sum())
    _plot(fig, 300, xtitle="seguradoras ordenadas por prêmio", ytitle="share acumulado",
          legend=False,
          titulo=f"{n} seguradoras fazem 80% do prêmio de {lob_sel}",
          sub=f"{len(seg)} empresas com prêmio positivo; as 5 maiores somam {analise.f_pct(top5_total, 0)}")

    # ---------------- mapa risco x rentabilidade ----------------
    _sub("Posicionamento: risco × rentabilidade")
    mostrar_todas = st.checkbox(
        "Incluir as demais seguradoras da LOB (pontos pequenos, sem rótulo)", value=False
    )
    relevantes_ids = set(mesa["codigo_susep"])
    base_mapa = (seg if mostrar_todas else mesa.copy()).sort_values("premio", ascending=False).head(24).copy()
    base_mapa["grupo"] = [
        "Akad" if c == analise.AKAD else ("Relevantes" if c in relevantes_ids else "Demais")
        for c in base_mapa["codigo_susep"]
    ]
    base_mapa["rotulo"] = [
        analise.nome_curto(nm) if (c == analise.AKAD or c in set(base_mapa.nlargest(5, "premio")["codigo_susep"])) else ""
        for c, nm in zip(base_mapa["codigo_susep"], base_mapa["seguradora"])
    ]

    # escala: ajustada aos pontos visíveis, com 10% de folga
    xmin, xmax = float(base_mapa["sinistralidade"].min()), float(base_mapa["sinistralidade"].max())
    ymin, ymax = float(base_mapa["margem"].min()), float(base_mapa["margem"].max())
    fx = (xmax - xmin) * 0.12 or 0.05
    fy = (ymax - ymin) * 0.18 or 0.05
    x_lo, x_hi = xmin - fx, xmax + fx
    y_lo, y_hi = ymin - fy, ymax + fy
    if not mostrar_todas:
        x_lo, x_hi = max(x_lo, 0.0), max(x_hi, 0.1)
        y_lo = max(y_lo, -0.05)

    base_mapa["x"] = base_mapa["sinistralidade"].clip(x_lo, x_hi)
    base_mapa["y"] = base_mapa["margem"].clip(y_lo, y_hi)
    base_mapa["fora"] = (base_mapa["sinistralidade"].ne(base_mapa["x"])
                         | base_mapa["margem"].ne(base_mapa["y"]))

    cores_grupo = {"Akad": analise.COR_AKAD, "Relevantes": LILAC, "Demais": NEGATIVO}
    fig = px.scatter(
        base_mapa, x="x", y="y", size="premio", color="grupo", text="rotulo",
        hover_name="seguradora", color_discrete_map=cores_grupo, size_max=40,
        labels={"x": "sinistralidade", "y": "margem", "grupo": ""},
        custom_data=["premio", "share", "sinistralidade", "margem"],
    )
    posicoes = ["top center" if i % 2 == 0 else "bottom center" for i in range(len(base_mapa))]
    fig.update_traces(
        textposition=posicoes,
        textfont=dict(size=11, color=INK),
        marker=dict(line=dict(width=1, color="#FFFFFF")),
        hovertemplate=(
            "<b>%{hovertext}</b><br>prêmio R$ %{customdata[0]:,.0f}<br>"
            "participação %{customdata[1]:.1%}<br>sinistralidade %{customdata[2]:.1%}<br>"
            "margem %{customdata[3]:.1%}<extra></extra>"
        ),
    )
    xm, ym = mercado["sinistralidade"], mercado["margem"]
    fig.add_vline(x=xm, line_dash="dash", line_color=MUTED, line_width=1)
    fig.add_hline(y=ym, line_dash="dash", line_color=MUTED, line_width=1)
    fig.add_annotation(x=x_lo, y=y_hi, text="risco baixo · margem alta", showarrow=False,
                       font=dict(size=11.5, color="#2E7D5B"), xanchor="left", yanchor="top")
    fig.add_annotation(x=x_hi, y=y_lo, text="risco alto · margem baixa", showarrow=False,
                       font=dict(size=11.5, color="#C8451F"), xanchor="right", yanchor="bottom")
    fig.update_xaxes(tickformat=".0%", range=[x_lo, x_hi])
    fig.update_yaxes(tickformat=".0%", range=[y_lo, y_hi])
    _plot(fig, 420, legend=True,
          titulo=f"Em {lob_sel}, quem combina menos sinistro com mais margem",
          sub="linhas tracejadas = média do mercado; tamanho = prêmio; rótulo nas 5 maiores e na Akad")
    if base_mapa["fora"].any():
        fora = base_mapa[base_mapa["fora"]]
        nomes = "; ".join(
            f"{analise.nome_curto(r.seguradora)} ({analise.f_pct(r.sinistralidade)} / {analise.f_pct(r.margem)})"
            for r in fora.head(4).itertuples()
        )
        st.caption(f"Fora da escala, presos na borda (sinistralidade / margem): {nomes}.")

    # ---------------- margem contra o mercado, por relevante ----------------
    d = mesa.sort_values("delta_margem").copy()
    d["sinal"] = d["delta_margem"].map(lambda v: "acima do mercado" if v >= 0 else "abaixo do mercado")
    fig = px.bar(
        d, x="delta_margem", y="seguradora", orientation="h", color="sinal",
        color_discrete_map={"acima do mercado": "#2E7D5B", "abaixo do mercado": "#C8451F"},
        text=d["delta_margem"].map(lambda v: f"{v*100:+.1f} pp".replace(".", ",")),
        labels={"delta_margem": "margem menos a do mercado (pp)", "seguradora": "", "sinal": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False, textfont=dict(size=10.5))
    fig.add_vline(x=0, line_color=MUTED)
    _folga_x(fig, d["delta_margem"], 0.35)
    _plot(fig, max(320, 26 * len(d)), legend=False,
          titulo=f"Quem ganha e quem perde margem contra o mercado em {lob_sel}",
          sub="diferença em pontos percentuais; barra à direita = margem acima da média da LOB")
    st.caption(resp[7]["curta"])


def _akad(base_f: pd.DataFrame, resp: list[dict]) -> None:
    anos = sorted(int(a) for a in base_f["ano"].unique())
    ano_a, ano_b = anos[0], anos[-1]

    # ---------------- Q10 ----------------
    _secao("Q10", "posição da Akad")
    st.caption(
        "2020–2021: operação Argo. 2022 em diante: Akad Seguros (marca de junho de 2022). "
        "A série é contínua porque o código SUSEP 02798 não muda."
    )
    akad = analise.akad_tabela(base_f)
    tab = akad.copy()
    tab["cresc"] = tab.apply(
        lambda r: f"×{r['premio1']/r['premio0']:.1f}".replace(".", ",") if r["premio0"] > 0 else "–",
        axis=1,
    )
    _tab(
        tab,
        ["lob", "premio0", "premio1", "share0", "share1", "rank0", "rank1", "cresc"],
        {"premio0": analise.f_mi, "premio1": analise.f_mi,
         "share0": analise.f_pct, "share1": analise.f_pct,
         "rank0": lambda v: f"{int(v)}ª" if pd.notna(v) else "–",
         "rank1": lambda v: f"{int(v)}ª" if pd.notna(v) else "–"},
        {"lob": "LOB", "premio0": f"Prêmio {ano_a}", "premio1": f"Prêmio {ano_b}",
         "share0": f"Participação {ano_a}", "share1": f"Participação {ano_b}",
         "rank0": f"Posição {ano_a}", "rank1": f"Posição {ano_b}", "cresc": "Crescimento"},
    )

    linhas = []
    for lname in analise.LOB_ORDEM:
        for ano in anos:
            g = base_f[(base_f["lob"] == lname) & (base_f["ano"] == ano)]
            if g.empty:
                continue
            total = float(g["premio_ganho"].sum())
            ak = float(g.loc[g["codigo_susep"] == analise.AKAD, "premio_ganho"].sum())
            linhas.append({"lob": lname, "ano": ano, "share": ak / total if total > 0 else 0})
    df = pd.DataFrame(linhas)
    if not df.empty:
        fig = px.line(
            df, x="ano", y="share", color="lob", facet_col="lob", facet_col_wrap=3,
            markers=True, color_discrete_map=analise.LOB_COR,
            labels={"ano": "", "share": "", "lob": ""},
        )
        fig.update_traces(line=dict(width=2), marker=dict(size=4))
        fig.update_yaxes(matches=None, tickformat=".1%", showticklabels=True, nticks=4)
        fig.update_xaxes(dtick=max(1, (ano_b - ano_a) // 2))
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], font=dict(size=12)))
        fig.update_layout(showlegend=False)
        if 2022 in anos:
            fig.add_vrect(x0=ano_a - 0.4, x1=2021.5, fillcolor="#9AA0B5", opacity=0.10, line_width=0)
            fig.add_vline(x=2022, line_dash="dash", line_color=MUTED, line_width=1)
        ganhou = []
        for lname, g in df.groupby("lob"):
            g = g.sort_values("ano")
            if len(g) >= 2 and g["share"].iloc[-1] > g["share"].iloc[0] + 0.005:
                ganhou.append(lname)
        titulo_share = (
            f"A Akad ganhou participação em {', '.join(ganhou)}"
            if ganhou else "Participação da Akad por LOB e ano"
        )
        _plot(fig, 480, legend=False,
              titulo=titulo_share,
              sub="um painel por LOB, escala própria; faixa cinza = fase Argo; linha vertical = 2022 (marca Akad)")
    st.caption(resp[9]["curta"])

    # ---------------- grafico-chave: Transportes ----------------
    _sub("A história de Transportes: prêmio cresce, margem desaparece")
    tr = base_f[base_f["lob"] == "Transportes"]
    if not tr.empty:
        linhas = []
        for ano in anos:
            g = tr[tr["ano"] == ano]
            a = g[g["codigo_susep"] == analise.AKAD]
            m = g[g["codigo_susep"] != analise.AKAD]
            if a.empty or m.empty:
                continue
            ma, mm = analise.metricas(a), analise.metricas(m)
            linhas.append({"ano": ano, "serie": "Akad", "margem": ma["margem"], "sin": ma["sinistralidade"]})
            linhas.append({"ano": ano, "serie": "Concorrentes", "margem": mm["margem"], "sin": mm["sinistralidade"]})
        dt = pd.DataFrame(linhas)
        if not dt.empty:
            cores = {"Akad": analise.COR_AKAD, "Concorrentes": NEGATIVO}
            ak_mg = dt[dt["serie"] == "Akad"].sort_values("ano")["margem"]
            ini_txt = analise.f_pct(ak_mg.iloc[0]) if not ak_mg.empty else "–"
            fim_txt = analise.f_pct(ak_mg.iloc[-1]) if not ak_mg.empty else "–"
            c1, c2 = st.columns(2)
            with c1:
                fig = px.line(dt, x="ano", y="margem", color="serie", markers=True,
                              color_discrete_map=cores,
                              labels={"ano": "", "margem": "margem", "serie": ""})
                fig.update_traces(line=dict(width=2.4), marker=dict(size=5))
                fig.update_yaxes(tickformat=".1%")
                fig.update_xaxes(dtick=max(1, (ano_b - ano_a) // 2))
                _plot(fig, 300, legend=False,
                      titulo=f"Margem: de {ini_txt} para {fim_txt}",
                      sub="Akad contra os concorrentes (mercado sem a Akad)")
            with c2:
                fig = px.line(dt, x="ano", y="sin", color="serie", markers=True,
                              color_discrete_map=cores,
                              labels={"ano": "", "sin": "sinistralidade", "serie": ""})
                fig.update_traces(line=dict(width=2.4), marker=dict(size=5))
                fig.update_yaxes(tickformat=".0%")
                fig.update_xaxes(dtick=max(1, (ano_b - ano_a) // 2))
                _plot(fig, 300, legend=True,
                      titulo="Sinistralidade: Akad acima dos concorrentes",
                      sub="quanto maior, mais prêmio consumido por sinistro")
    st.caption("É a principal história do case: escala cresceu, rentabilidade não.")

    # ---------------- Q11 ----------------
    _secao("Q11", "Akad contra mercado, pares e relevantes")
    ref = base_f[base_f["ano"] >= 2022] if (base_f["ano"] >= 2022).any() else base_f
    rot_ref = f"{int(ref['ano'].min())}–{int(ref['ano'].max())}"
    comp = analise.comparacao_akad(ref)
    if comp.empty:
        st.info("A Akad não aparece nas LOBs selecionadas.")
        return
    comp["delta_mg"] = comp["akad_mg"] - comp["mercado_mg"]

    # margem e sinistralidade: faixa das referencias com a Akad em destaque
    def _faixa(col_akad: str, cols_ref: list[str], titulo: str, sub: str, fmt, menor_melhor: bool):
        base_idx = comp.set_index("lob")
        fig = go.Figure()
        for lob in base_idx.index:
            refs = [float(base_idx.loc[lob, c]) for c in cols_ref if pd.notna(base_idx.loc[lob, c])]
            if not refs:
                continue
            fig.add_trace(go.Scatter(
                x=[min(refs), max(refs)], y=[lob, lob], mode="lines",
                line=dict(color=NEGATIVO, width=9), opacity=0.45,
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=refs, y=[lob] * len(refs), mode="markers",
                marker=dict(size=7, color=MUTED, symbol="line-ns-open"),
                showlegend=False,
                customdata=[[c] for c in cols_ref[: len(refs)]],
                hovertemplate=f"{lob}<br>%{{x:.1%}}<extra></extra>",
            ))
        fig.add_trace(go.Scatter(
            x=base_idx[col_akad], y=base_idx.index, mode="markers+text",
            marker=dict(size=15, color=analise.COR_AKAD, line=dict(width=2, color="#FFFFFF")),
            text=[fmt(v) for v in base_idx[col_akad]],
            textposition="middle right", textfont=dict(size=11.5, color=INK),
            name="Akad", showlegend=False,
            hovertemplate="Akad em %{y}: %{x:.1%}<extra></extra>",
        ))
        ordem = base_idx[col_akad].sort_values().index  # melhor por ultimo = topo
        fig.update_xaxes(tickformat=".0%")
        fig.update_yaxes(categoryorder="array", categoryarray=list(ordem))
        _folga_x(fig, base_idx[col_akad], 0.22)
        _plot(fig, 340, legend=False, titulo=titulo, sub=sub)

    ganha_mg = [r.lob for r in comp.itertuples() if r.akad_mg > r.mercado_mg]
    titulo_mg = (
        f"Margem: a Akad ganha do mercado em {', '.join(ganha_mg)} ({rot_ref})"
        if ganha_mg else f"Margem: a Akad fica abaixo do mercado ({rot_ref})"
    )
    _faixa("akad_mg", ["mercado_mg", "peers_mg", "relev_mg"], titulo_mg,
           "ponto rosa = Akad; faixa cinza = intervalo entre mercado, pares e relevantes",
           analise.f_pct, menor_melhor=False)

    ganha_sin = [r.lob for r in comp.itertuples() if r.akad_sin < r.mercado_sin - 0.01]
    empata_sin = [r.lob for r in comp.itertuples() if abs(r.akad_sin - r.mercado_sin) <= 0.01]
    partes_sin = []
    if ganha_sin:
        partes_sin.append(f"ganha em {', '.join(ganha_sin)}")
    if empata_sin:
        partes_sin.append(f"empata em {', '.join(empata_sin)}")
    titulo_sin = ("Sinistralidade: a Akad " + " e ".join(partes_sin) + f" ({rot_ref})"
                  if partes_sin else f"Sinistralidade da Akad contra as referências ({rot_ref})")
    _faixa("akad_sin", ["mercado_sin", "peers_sin", "relev_sin"], titulo_sin,
           "ponto rosa = Akad; faixa cinza = intervalo das referências; mais à esquerda é melhor",
           analise.f_pct, menor_melhor=True)

    _tab(
        comp.reset_index() if "lob" not in comp.columns else comp,
        ["lob", "akad_mg", "mercado_mg", "peers_mg", "relev_mg",
         "akad_sin", "mercado_sin", "peers_sin", "relev_sin", "peers_n", "relev_n"],
        {"akad_mg": analise.f_pct, "mercado_mg": analise.f_pct,
         "peers_mg": analise.f_pct, "relev_mg": analise.f_pct,
         "akad_sin": analise.f_pct, "mercado_sin": analise.f_pct,
         "peers_sin": analise.f_pct, "relev_sin": analise.f_pct},
        {"lob": "LOB", "akad_mg": "Margem Akad", "mercado_mg": "Margem mercado",
         "peers_mg": "Margem pares", "relev_mg": "Margem relevantes",
         "akad_sin": "Sinistr. Akad", "mercado_sin": "Sinistr. mercado",
         "peers_sin": "Sinistr. pares", "relev_sin": "Sinistr. relevantes",
         "peers_n": "Nº pares", "relev_n": "Nº relevantes"},
    )
    st.caption(resp[10]["curta"])

    # de onde vem a diferenca de margem
    linhas = []
    for lname in analise.LOB_ORDEM:
        g = ref[ref["lob"] == lname]
        a = g[g["codigo_susep"] == analise.AKAD]
        if g.empty or a.empty:
            continue
        ca, cm = analise.componentes(a), analise.componentes(g)
        total = sum(-(ca[k] - cm[k]) for k in ("sin", "resseg", "com"))
        for chave, nome in (("sin", "Sinistralidade"), ("resseg", "Resseguro líquido"), ("com", "Despesa comercial")):
            linhas.append({"lob": lname, "componente": nome, "pp": -(ca[chave] - cm[chave]) * 100})
        linhas.append({"lob": lname, "componente": "Diferença total", "pp": total * 100})
    if linhas:
        dd = pd.DataFrame(linhas)
        st.markdown(f"##### De onde vem a diferença de margem ({rot_ref})")
        componentes = dd[dd["componente"] != "Diferença total"]
        fig = px.bar(
            componentes, x="pp", y="lob", color="componente", orientation="h", barmode="relative",
            color_discrete_map={"Sinistralidade": "#D9668F", "Resseguro líquido": LILAC,
                                "Despesa comercial": "#B4723A"},
            labels={"pp": "contribuição (pp)", "lob": "", "componente": ""},
        )
        fig.add_vline(x=0, line_color=MUTED)
        fig.update_layout(legend=dict(orientation="h", y=-0.18, x=0))
        totais = dd[dd["componente"] == "Diferença total"].set_index("lob")["pp"]
        for lname, v in totais.items():
            fig.add_annotation(x=v, y=lname, text=f"{v:+.1f} pp".replace(".", ","),
                               showarrow=False, xanchor="left" if v >= 0 else "right",
                               font=dict(size=11, color=INK))
        resseg = componentes[componentes["componente"] == "Resseguro líquido"]
        if not resseg.empty:
            melhor = resseg.loc[resseg["pp"].idxmax()]
            titulo_dec = (
                f"Resseguro responde por {melhor['pp']:+.1f} pp da vantagem de {melhor['lob']}".replace(".", ",")
                if melhor["pp"] > 0 else "De onde vem a diferença de margem"
            )
        else:
            titulo_dec = "De onde vem a diferença de margem"
        _plot(fig, 340, legend=True,
              titulo=titulo_dec,
              sub="contribuição de cada componente para (margem Akad − mercado); positivo ajuda a Akad")
        st.caption(
            "Resseguro líquido = despesa − receita com resseguro. Contribuição positiva significa que a "
            "Akad cede menos risco que o mercado: mais margem nos anos bons, mais capital e volatilidade retidos."
        )


def _recomendacao(base_f: pd.DataFrame, resp: list[dict]) -> None:
    """Q12: matriz strategica e barra de impacto, com numeros da base."""
    _secao("Q12", "onde focar nos próximos anos")
    fase = base_f[base_f["ano"] >= 2022] if (base_f["ano"] >= 2022).any() else base_f
    rot = f"{int(fase['ano'].min())}–{int(fase['ano'].max())}"
    f1 = int(fase["ano"].max())

    dados = []
    for l in analise.LOB_ORDEM:
        g = fase[fase["lob"] == l]
        a = g[g["codigo_susep"] == analise.AKAD]
        if a.empty:
            continue
        m = g[g["codigo_susep"] != analise.AKAD]
        ma, mm = analise.metricas(a), analise.metricas(m if not m.empty else g)
        tot_f1 = float(base_f[(base_f["lob"] == l) & (base_f["ano"] == f1)]["premio_ganho"].sum())
        ak_f1 = float(base_f[(base_f["lob"] == l) & (base_f["ano"] == f1) & (base_f["codigo_susep"] == analise.AKAD)]["premio_ganho"].sum())
        papel, acao = respostas_mod.PAPEL.get(l, ("–", "–"))
        dados.append({
            "lob": l,
            "share": ak_f1 / tot_f1 if tot_f1 else 0,
            "mg_a": ma["margem"],
            "mg_m": mm["margem"],
            "gap": ma["margem"] - mm["margem"],
            "premio": ma["premio"],
            "lucro": ma["lucro"],
            "papel": papel,
            "acao": acao,
        })
    if not dados:
        st.info("A Akad não aparece nas LOBs selecionadas.")
        return
    dd = pd.DataFrame(dados)

    cores = {"Núcleo": analise.COR_AKAD, "Corrigir": "#C8451F",
             "Aposta seletiva": LILAC, "Opcional": NEGATIVO}
    fig = px.scatter(
        dd, x="share", y="gap", size="premio", color="papel", text="lob",
        color_discrete_map=cores, size_max=50,
        labels={"share": "participação da Akad na LOB", "gap": "margem da Akad − concorrentes (pp)",
                "papel": ""},
        custom_data=["mg_a", "mg_m", "lucro", "papel"],
    )
    fig.update_traces(
        textposition="top center", textfont=dict(size=12),
        hovertemplate=(
            "<b>%{text}</b><br>participação %{x:.1%}<br>"
            "margem Akad %{customdata[0]:.1%} vs %{customdata[1]:.1%}<br>"
            "lucro %{customdata[2]:,.0f}<br>%{customdata[3]}<extra></extra>"
        ),
    )
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    fig.add_vline(x=0.05, line_dash="dash", line_color=RULE)
    fig.add_annotation(x=0.052, y=float(dd["gap"].max()), text="5% de participação",
                       showarrow=False, font=dict(size=10.5, color=MUTED), xanchor="left", yanchor="top")
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat="+.0f", ticksuffix=" pp")
    prioridade = [r.lob for r in sorted(dd.itertuples(), key=lambda x: -x.share) if r.share >= 0.02 and r.gap > 0]
    titulo_mat = (
        f"{', '.join(prioridade)}: participação relevante e margem acima dos concorrentes"
        if prioridade else "Participação e margem da Akad por LOB"
    )
    _plot(fig, 420, legend=True,
          titulo=titulo_mat,
          sub=f"fase Akad ({rot}); tamanho = prêmio; acima da linha = margem melhor que os concorrentes")

    # impacto de Transportes na margem dos concorrentes
    tr = dd[dd["lob"] == "Transportes"]
    eo = dd[dd["lob"] == "E&O"]
    if not tr.empty:
        t = tr.iloc[0]
        impacto = (t["mg_m"] - t["mg_a"]) * t["premio"]
        barras = [("Transportes na margem dos concorrentes", impacto, "#2E7D5B")]
        if not eo.empty:
            barras.append(("Lucro de E&O na fase Akad", float(eo.iloc[0]["lucro"]), analise.LOB_COR["E&O"]))
        fig = go.Figure(go.Bar(
            x=[b[1] for b in barras], y=[b[0] for b in barras], orientation="h",
            marker_color=[b[2] for b in barras],
            text=[analise.f_din(b[1]) for b in barras], textposition="outside",
        ))
        fig.update_xaxes(tickformat=",.0f", range=[0, max(b[1] for b in barras) * 1.25])
        fig.update_yaxes(title=None)
        _plot(fig, 240, legend=False, xtitle="R$",
              titulo=f"Corrigir Transportes vale {analise.f_din(impacto)} — mais que todo o lucro de E&O",
              sub=f"se Transportes tivesse a margem dos concorrentes ({analise.f_pct(t['mg_m'])}) sobre o prêmio da fase")

    _sub("Papel de cada LOB")
    _tab(
        dd.sort_values("papel"),
        ["lob", "papel", "acao", "share", "mg_a", "mg_m", "gap", "lucro"],
        {"share": analise.f_pct, "mg_a": analise.f_pct, "mg_m": analise.f_pct,
         "gap": lambda v: f"{v*100:+.1f} pp".replace(".", ","), "lucro": analise.f_din},
        {"lob": "LOB", "papel": "Papel", "acao": "Ação", "share": "Participação",
         "mg_a": "Margem Akad", "mg_m": "Margem concorrentes", "gap": "Diferença",
         "lucro": "Lucro na fase"},
    )
    st.caption(
        "O papel de cada LOB é opinião apoiada nos números; precisa ser validado com dados internos de "
        "preço, comissão e resseguro. Gatilho de revisão: se a sinistralidade de E&O voltar acima de 45%, "
        "rever a retenção de risco."
    )
    st.caption(resp[11]["curta"])


def _respostas(resp: list[dict]) -> None:
    st.markdown("#### Respostas do case")
    st.caption(
        "Os números e análises são recalculados com os filtros atuais. O contexto de marca (Q10) e a recomendação da "
        "Q12 são julgamento de negócio, não resultado automático. Para a leitura completa, deixe o filtro em 2020–2025."
    )
    texto = [f"## {item['n']} · {item['pergunta']}\n\n{item['resposta']}\n" for item in resp]
    st.download_button(
        "Baixar respostas em Markdown",
        "\n".join(texto),
        file_name="respostas_akad.md",
        mime="text/markdown",
    )
    for item in resp:
        with st.container(border=True):
            st.markdown(
                f'<span class="resp-badge">Q{html_lib.escape(item["n"])}</span>'
                f'<strong>{html_lib.escape(item["pergunta"])}</strong>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="resp-curta"><strong>Resposta direta:</strong> {html_lib.escape(item["curta"])}</div>',
                unsafe_allow_html=True,
            )
            corpo = item.get("corpo") or item["resposta"]
            st.markdown(corpo)
    st.caption("O roteiro completo, com mercado 101 e leitura de cada gráfico, é um documento local em `analise/roteiro_apresentacao.html`.")


# --------------------------------------------------------------------------
# Aba Dados: a base linha a linha, com busca e download
# --------------------------------------------------------------------------

COLS_DADOS = [
    "lob", "ramo_codigo", "ano", "codigo_susep", "seguradora",
    "premio_ganho", "sinistro_ocorrido", "despesa_resseguro",
    "receita_resseguro", "despesa_comercial",
    "sinistralidade", "lucro", "margem",
]


def _dados(base: pd.DataFrame) -> None:
    st.markdown("#### Base linha a linha")
    st.caption(
        "Uma linha por seguradora, ramo e ano — a mesma tabela do `base.csv`. "
        "Filtre, busque por código SUSEP ou nome e baixe o recorte."
    )

    anos = sorted(int(a) for a in base["ano"].unique())
    lobs_disp = [l for l in analise.LOB_ORDEM if l in set(base["lob"])]
    c1, c2 = st.columns([1.3, 1])
    lobs = c1.multiselect("LOBs", lobs_disp, default=lobs_disp, key="dados_lobs")
    faixa = c2.slider("Anos", min(anos), max(anos), (min(anos), max(anos)), key="dados_anos")

    c3, c4 = st.columns([1, 1.6])
    ramos_disp = sorted(base.loc[base["lob"].isin(lobs), "ramo_codigo"].unique()) if lobs else []
    ramos = c3.multiselect("Ramos", ramos_disp, default=[], key="dados_ramos")
    busca = c4.text_input(
        "Buscar por código SUSEP ou nome", value="", key="dados_busca",
        placeholder="ex.: 02798 ou AKAD",
    ).strip()

    d = base[base["lob"].isin(lobs) & base["ano"].between(faixa[0], faixa[1])]
    if ramos:
        d = d[d["ramo_codigo"].isin(ramos)]
    if busca:
        q = busca.upper()
        d = d[
            d["codigo_susep"].astype(str).str.contains(q, na=False)
            | d["seguradora"].astype(str).str.upper().str.contains(q, na=False)
        ]

    if d.empty:
        st.warning("Nenhuma linha com esses filtros.")
        return

    m = analise.metricas(d)
    _ledger(
        [
            ("Linhas", f"{len(d):,}".replace(",", "."), "seguradora × ramo × ano"),
            ("Prêmio ganho", analise.f_bi(m["premio"]), "soma do recorte"),
            ("Sinistralidade", analise.f_pct(m["sinistralidade"]), "sinistro ÷ prêmio"),
            ("Margem", analise.f_pct(m["margem"]), "resultado técnico ÷ prêmio"),
        ]
    )

    visao = d[COLS_DADOS].sort_values(
        ["lob", "ano", "premio_ganho"], ascending=[True, True, False]
    )
    st.dataframe(
        visao,
        hide_index=True,
        width="stretch",
        height=460,
        column_config={
            "lob": st.column_config.TextColumn("LOB", width="small"),
            "ramo_codigo": st.column_config.TextColumn("Ramo", width="small"),
            "ano": st.column_config.NumberColumn("Ano", width="small", format="%d"),
            "codigo_susep": st.column_config.TextColumn("Código", width="small"),
            "seguradora": st.column_config.TextColumn("Seguradora", width="large"),
            "premio_ganho": st.column_config.NumberColumn("Prêmio", format="%.0f"),
            "sinistro_ocorrido": st.column_config.NumberColumn("Sinistro", format="%.0f"),
            "despesa_resseguro": st.column_config.NumberColumn("Desp. resseg.", format="%.0f"),
            "receita_resseguro": st.column_config.NumberColumn("Rec. resseg.", format="%.0f"),
            "despesa_comercial": st.column_config.NumberColumn("Desp. comercial", format="%.0f"),
            "sinistralidade": st.column_config.NumberColumn("Sinistr.", format="%.1f%%"),
            "lucro": st.column_config.NumberColumn("Resultado", format="%.0f"),
            "margem": st.column_config.NumberColumn("Margem", format="%.1f%%"),
        },
    )
    st.caption(
        "Sinistralidade e margem aparecem vazias quando o prêmio é zero — "
        "a razão não existe nesse caso. Valores negativos são estornos/ajustes, não erro."
    )

    st.download_button(
        "Baixar recorte em CSV",
        visao.to_csv(index=False).encode("utf-8-sig"),
        file_name="base_recorte.csv",
        mime="text/csv",
    )


def render_dados() -> None:
    base = _base_cache()
    if base.empty:
        st.error("Nenhum snapshot anual publicado. Use a aba Atualizar base.")
        return
    _dados(base)


# --------------------------------------------------------------------------
# Entrada
# --------------------------------------------------------------------------

def render() -> None:
    base = _base_cache()
    if base.empty:
        st.error("Nenhum snapshot anual publicado. Rode o pipeline ou use a aba Atualizar base.")
        return
    st.caption("Painel do snapshot anual (2020–2025). Recortes parciais ficam na aba Atualizar base e no Status.")

    anos = sorted(int(a) for a in base["ano"].unique())
    c1, c2, c3 = st.columns([2.2, 2, 0.8])
    lobs = c1.multiselect("LOBs", analise.LOB_ORDEM, default=analise.LOB_ORDEM, key="painel_lobs")
    faixa = c2.slider("Anos", min(anos), max(anos), (min(anos), max(anos)), key="painel_anos")
    if c3.button("Recarregar", key="painel_reload"):
        st.cache_data.clear()
        st.rerun()

    if not lobs:
        st.warning("Selecione pelo menos uma LOB.")
        return

    base_f = analise.filtrar(base, lobs, faixa[0], faixa[1])
    if base_f.empty:
        st.warning("Nenhuma linha com os filtros atuais.")
        return
    if faixa[0] == faixa[1]:
        st.caption("Com um único ano, as perguntas de crescimento ficam sem sentido; escolha um intervalo maior.")

    lob = analise.por_lob(base_f)
    lob_ano = analise.por_lob_ano(base_f)
    resp = analise.respostas(base_f)

    tab_visao, tab_mercado, tab_rent, tab_sin, tab_conc, tab_akad, tab_rec, tab_resp = st.tabs(
        ["Visão geral", "Mercado", "Rentabilidade", "Sinistralidade", "Concorrência",
         "Akad", "Recomendação", "Respostas"]
    )
    with tab_visao:
        _visao(lob, lob_ano, base_f, resp)
    with tab_mercado:
        _mercado(lob, base_f, resp)
    with tab_rent:
        _rentabilidade(lob, base_f, resp)
    with tab_sin:
        _sinistralidade(lob, lob_ano, base_f, resp)
    with tab_conc:
        _concorrencia(base_f, resp)
    with tab_akad:
        _akad(base_f, resp)
    with tab_rec:
        _recomendacao(base_f, resp)
    with tab_resp:
        _respostas(resp)
