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
CFG = {"displayModeBar": False}


# --------------------------------------------------------------------------
# Helpers visuais
# --------------------------------------------------------------------------

def _layout(fig, height: int = 330, ytitle: str | None = None, xtitle: str | None = None, legend: bool = True):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=13, color=INK),
        margin=dict(l=8, r=8, t=34, b=8),
        height=height,
        showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font_family="IBM Plex Mono"),
    )
    fig.update_xaxes(showgrid=False, linecolor=RULE, tickfont=dict(size=12))
    fig.update_yaxes(gridcolor="rgba(18,32,29,0.08)", zeroline=False, tickfont=dict(size=12))
    if ytitle:
        fig.update_yaxes(title=dict(text=ytitle, font=dict(size=12, color=MUTED)))
    if xtitle:
        fig.update_xaxes(title=dict(text=xtitle, font=dict(size=12, color=MUTED)))
    return fig


def _plot(fig, height: int = 330, ytitle: str | None = None, xtitle: str | None = None, legend: bool = True):
    st.plotly_chart(_layout(fig, height, ytitle, xtitle, legend), use_container_width=True, config=CFG)


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
        use_container_width=True,
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
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=5))
    fig.update_xaxes(dtick=1)
    _plot(fig, 340, ytitle="R$ bilhões", legend=True)

    pivot = lob_ano.pivot(index="lob", columns="ano", values="sinistralidade")
    pivot = pivot.reindex([l for l in analise.LOB_ORDEM if l in pivot.index])
    texto = [[analise.f_pct(v) for v in row] for row in pivot.values]
    heat = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=pivot.index,
            colorscale=[[0, "#F4F5FD"], [0.5, PINK], [1, PINE]],
            text=texto,
            texttemplate="%{text}",
            showscale=False,
            hovertemplate="%{y} · %{x}<br>sinistralidade %{text}<extra></extra>",
        )
    )
    st.markdown("#### Sinistralidade por LOB e ano")
    _plot(heat, 280, legend=False)

    st.markdown("#### Leitura rápida")
    for item in resp[:3] + [resp[6], resp[8]]:
        st.markdown(f"**{item['n']}.** {item['pergunta']}  \n{item['curta']}")


def _mercado(lob: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    st.markdown("#### Q1 · prêmio ganho por LOB")
    d = lob.sort_values("premio").copy()
    d["premio_bi"] = d["premio"] / 1e9
    fig = px.bar(
        d, x="premio_bi", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["premio_bi"].map(lambda v: f"{v:.1f} bi"),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    _plot(fig, 300, xtitle="R$ bilhões", legend=False)
    st.caption(resp[0]["curta"])

    anos_f = sorted(int(a) for a in base_f["ano"].unique())
    periodo_f = f"{anos_f[0]}–{anos_f[-1]}" if len(anos_f) > 1 else str(anos_f[0])
    st.markdown(f"#### Q7 · crescimento do prêmio {periodo_f}")
    cresc = analise.crescimento(base_f)
    if cresc.empty:
        st.info("Selecione pelo menos dois anos para calcular crescimento.")
    else:
        fig = go.Figure()
        for lname, r in cresc.iterrows():
            cor = analise.LOB_COR.get(lname, PINE)
            fig.add_trace(
                go.Scatter(
                    x=[r["primeiro"] / 1e9, r["ultimo"] / 1e9],
                    y=[lname, lname],
                    mode="lines",
                    line=dict(color=cor, width=3),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[r["primeiro"] / 1e9],
                    y=[lname],
                    mode="markers",
                    marker=dict(color=cor, size=9, line=dict(color="#FFFFFF", width=1)),
                    showlegend=False,
                    hovertemplate=f"{lname} {int(r['ano_ini'])}: R$ %{{x:.2f}} bi<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[r["ultimo"] / 1e9],
                    y=[lname],
                    mode="markers+text",
                    marker=dict(color=cor, size=12, line=dict(color="#FFFFFF", width=1)),
                    text=[analise.f_pct(r["pct"])],
                    textposition="middle right",
                    showlegend=False,
                    hovertemplate=f"{lname} {int(r['ano_fim'])}: R$ %{{x:.2f}} bi<extra></extra>",
                )
            )
        _plot(fig, 320, xtitle="prêmio ganho, R$ bilhões", legend=False)
        _tab(
            cresc.reset_index(),
            ["lob", "primeiro", "ultimo", "abs", "pct"],
            {"primeiro": analise.f_bi, "ultimo": analise.f_bi, "abs": analise.f_bi, "pct": analise.f_pct},
            {"lob": "LOB", "primeiro": str(anos_f[0]), "ultimo": str(anos_f[-1]), "abs": "Variação absoluta", "pct": "Variação %"},
        )
        st.caption(resp[6]["curta"])

    st.markdown("#### Q2 · seguradoras ativas")
    ativas = analise.ativas_por_ano(base_f)
    ativas_pres = analise.ativas_por_ano(base_f, "presenca")
    anos = sorted(ativas.columns)
    if len(anos) >= 2:
        a0, a1 = anos[0], anos[-1]
        linhas = []
        for lname in analise.LOB_ORDEM:
            if lname not in ativas.index:
                continue
            linhas.append({"lob": lname, "ano": str(a0), "ativas": int(ativas.loc[lname, a0])})
            linhas.append({"lob": lname, "ano": str(a1), "ativas": int(ativas.loc[lname, a1])})
        df = pd.DataFrame(linhas)
        fig = px.bar(
            df, x="lob", y="ativas", color="ano", barmode="group",
            color_discrete_sequence=[LILAC, PINE],
        )
        _plot(fig, 320, ytitle="seguradoras com prêmio > 0", legend=True)
        _tab(
            pd.DataFrame(
                [
                    {
                        "lob": l,
                        "presenca0": int(ativas_pres.loc[l, a0]),
                        "ativas0": int(ativas.loc[l, a0]),
                        "presenca1": int(ativas_pres.loc[l, a1]),
                        "ativas1": int(ativas.loc[l, a1]),
                    }
                    for l in analise.LOB_ORDEM
                    if l in ativas.index
                ]
            ),
            ["lob", "presenca0", "ativas0", "presenca1", "ativas1"],
            {},
            {"lob": "LOB", "presenca0": f"Linhas {a0}", "ativas0": f"Ativas {a0}", "presenca1": f"Linhas {a1}", "ativas1": f"Ativas {a1}"},
        )
        st.caption(resp[1]["curta"])


def _rentabilidade(lob: pd.DataFrame, resp: list[dict]) -> None:
    st.markdown("#### Q5 · resultado técnico por LOB")
    d = lob.sort_values("lucro").copy()
    d["lucro_bi"] = d["lucro"] / 1e9
    fig = px.bar(
        d, x="lucro_bi", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["lucro_bi"].map(lambda v: f"{v:.2f} bi"),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    _plot(fig, 300, xtitle="R$ bilhões", legend=False)
    st.caption(resp[4]["curta"])

    st.markdown("#### Q6 · margem por LOB")
    d = lob.sort_values("margem").copy()
    fig = px.bar(
        d, x="margem", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["margem"].map(analise.f_pct),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(tickformat=".0%")
    _plot(fig, 300, xtitle="margem", legend=False)
    st.caption(resp[5]["curta"])

    _tab(
        lob,
        ["lob", "premio", "lucro", "margem", "sinistralidade"],
        {"premio": analise.f_bi, "lucro": analise.f_bi, "margem": analise.f_pct, "sinistralidade": analise.f_pct},
        {"lob": "LOB", "premio": "Prêmio ganho", "lucro": "Resultado técnico", "margem": "Margem", "sinistralidade": "Sinistralidade"},
    )
    st.caption(
        "Resultado técnico = prêmio ganho + receita com resseguro − sinistro ocorrido "
        "− despesa com resseguro − despesa comercial."
    )


def _sinistralidade(lob: pd.DataFrame, lob_ano: pd.DataFrame, base_f: pd.DataFrame, resp: list[dict]) -> None:
    st.markdown("#### Q3 · sinistralidade agregada")
    d = lob.sort_values("sinistralidade", ascending=False).copy()
    fig = px.bar(
        d, x="sinistralidade", y="lob", orientation="h", color="lob",
        color_discrete_map=analise.LOB_COR, text=d["sinistralidade"].map(analise.f_pct),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_xaxes(tickformat=".0%")
    _plot(fig, 300, xtitle="sinistralidade", legend=False)
    st.caption(resp[2]["curta"])

    st.markdown("#### Q9 · tendência anual")
    fig = px.line(
        lob_ano, x="ano", y="sinistralidade", color="lob", markers=True,
        color_discrete_map=analise.LOB_COR,
    )
    fig.update_traces(line=dict(width=2), marker=dict(size=5))
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(dtick=1)
    _plot(fig, 340, ytitle="sinistralidade", legend=True)
    st.caption(resp[8]["curta"])

    trend = analise.tendencias(base_f)
    trend = trend.merge(lob[["lob", "premio"]], on="lob", how="left")
    fig = px.scatter(
        trend, x="vol", y="sin_media", size="premio", color="lob", text="lob",
        color_discrete_map=analise.LOB_COR, size_max=45,
    )
    fig.update_traces(textposition="top center")
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    _plot(fig, 330, xtitle="volatilidade (desvio da sinistralidade)", ytitle="média", legend=False)
    _tab(
        trend,
        ["lob", "sin_media", "vol", "slope", "cresc_sinistro", "margem_media"],
        {
            "sin_media": analise.f_pct, "vol": analise.f_pct,
            "slope": lambda v: f"{v*100:+.1f} pp/ano".replace(".", ",") if pd.notna(v) else "–",
            "cresc_sinistro": analise.f_pct, "margem_media": analise.f_pct,
        },
        {"lob": "LOB", "sin_media": "Média", "vol": "Volatilidade", "slope": "Tendência", "cresc_sinistro": "Crescimento do sinistro", "margem_media": "Margem média"},
    )

    st.markdown("#### Q4 · maior sinistralidade por LOB")
    thr = st.slider("Share mínimo para entrar no ranking", 0.0, 5.0, 1.0, 0.1) / 100
    q4 = analise.q4(base_f, min_share=thr)
    if q4.empty:
        st.info("Sem seguradoras acima do corte.")
    else:
        _tab(
            q4,
            ["lob", "seguradora", "premio", "share", "sinistralidade", "margem"],
            {"premio": analise.f_mi, "share": analise.f_pct, "sinistralidade": analise.f_pct, "margem": analise.f_pct},
            {"lob": "LOB", "seguradora": "Seguradora", "premio": "Prêmio", "share": "Share", "sinistralidade": "Sinistralidade", "margem": "Margem"},
        )
        st.caption(respostas_mod.q4_curta(base_f, thr))
    st.caption("Sinistralidade negativa não é erro: é reversão de reserva. O corte de materialidade evita que empresas minúsculas dominem o ranking.")


def _concorrencia(base_f: pd.DataFrame, resp: list[dict]) -> None:
    st.markdown("#### Q8 · seguradoras relevantes e comparação com o mercado")
    lob_sel = st.selectbox("LOB", analise.LOB_ORDEM, index=0, key="concorrencia_lob")
    mesa, n, mercado = analise.relevantes(base_f, lob_sel)
    if mesa.empty:
        st.info("Sem seguradoras com prêmio positivo nesta LOB.")
        return

    st.caption(
        f"{n} seguradoras explicam 80% do prêmio de {lob_sel}. "
        f"Mercado: margem {analise.f_pct(mercado['margem'])} e sinistralidade {analise.f_pct(mercado['sinistralidade'])}."
    )
    _tab(
        mesa,
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
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=seg["rank"], y=seg["cum"], mode="lines+markers", line=dict(color=LILAC, width=2), marker=dict(size=4), name="acumulado"))
    fig.add_hline(y=0.8, line_dash="dash", line_color=MUTED, annotation_text="80%")
    fig.update_yaxes(tickformat=".0%")
    _plot(fig, 280, xtitle="seguradoras ordenadas por prêmio", ytitle="share acumulado", legend=False)

    fig = px.scatter(
        seg, x="sinistralidade", y="margem", size="premio", text="seguradora",
        color="share", color_continuous_scale=["#F4F5FD", LILAC], size_max=45,
    )
    fig.update_traces(textposition="top center", textfont=dict(size=10))
    fig.add_vline(x=mercado["sinistralidade"], line_dash="dash", line_color=MUTED)
    fig.add_hline(y=mercado["margem"], line_dash="dash", line_color=MUTED)
    ak = seg[seg["codigo_susep"] == analise.AKAD]
    if not ak.empty:
        fig.add_trace(
            go.Scatter(
                x=ak["sinistralidade"], y=ak["margem"], mode="markers+text",
                marker=dict(symbol="star", size=16, color=analise.COR_AKAD),
                text=["Akad"], textposition="bottom center", name="Akad",
            )
        )
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    _plot(fig, 360, xtitle="sinistralidade", ytitle="margem", legend=False)
    st.caption(resp[7]["curta"])


def _akad(base_f: pd.DataFrame, resp: list[dict]) -> None:
    st.markdown("#### Q10 · posição da Akad")
    st.caption(
        "2020–2021: operação Argo (a compra pela GP é de 2021). 2022 em diante: Akad Seguros (marca de junho de 2022). "
        "A série de seis anos mistura as duas fases; a leitura de posição da Akad deve priorizar 2022–2025."
    )
    anos = sorted(base_f["ano"].unique())
    ano_a, ano_b = int(anos[0]), int(anos[-1])
    akad = analise.akad_tabela(base_f)
    _tab(
        akad,
        ["lob", "premio0", "premio1", "share0", "share1", "rank0", "rank1", "cresc"],
        {
            "premio0": analise.f_bi, "premio1": analise.f_bi,
            "share0": analise.f_pct, "share1": analise.f_pct,
            "rank0": lambda v: f"{int(v)}º" if pd.notna(v) else "–",
            "rank1": lambda v: f"{int(v)}º" if pd.notna(v) else "–",
            "cresc": analise.f_pct,
        },
        {"lob": "LOB", "premio0": f"Prêmio {ano_a}", "premio1": f"Prêmio {ano_b}", "share0": f"Share {ano_a}", "share1": f"Share {ano_b}", "rank0": f"Posição {ano_a}", "rank1": f"Posição {ano_b}", "cresc": "Crescimento"},
    )

    anos = sorted(base_f["ano"].unique())
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
        fig = px.line(df, x="ano", y="share", color="lob", markers=True, color_discrete_map=analise.LOB_COR)
        fig.update_traces(line=dict(width=2), marker=dict(size=5))
        fig.update_yaxes(tickformat=".0%")
        fig.update_xaxes(dtick=1)
        _plot(fig, 320, ytitle="share da Akad", legend=True)
    st.caption(resp[9]["curta"])

    st.markdown("#### Q11 · Akad contra mercado, pares e relevantes")
    comp = analise.comparacao_akad(base_f)
    comp["delta_mg"] = comp["akad_mg"] - comp["mercado_mg"]
    _tab(
        comp,
        [
            "lob", "akad_mg", "mercado_mg", "peers_mg", "relev_mg",
            "akad_sin", "mercado_sin", "peers_sin", "relev_sin", "peers_n", "relev_n",
        ],
        {
            "akad_mg": analise.f_pct, "mercado_mg": analise.f_pct,
            "peers_mg": analise.f_pct, "relev_mg": analise.f_pct,
            "akad_sin": analise.f_pct, "mercado_sin": analise.f_pct,
            "peers_sin": analise.f_pct, "relev_sin": analise.f_pct,
        },
        {
            "lob": "LOB", "akad_mg": "Margem Akad", "mercado_mg": "Margem mercado",
            "peers_mg": "Margem pares", "relev_mg": "Margem relevantes",
            "akad_sin": "Sinistr. Akad", "mercado_sin": "Sinistr. mercado",
            "peers_sin": "Sinistr. pares", "relev_sin": "Sinistr. relevantes",
            "peers_n": "Nº pares", "relev_n": "Nº relevantes",
        },
    )
    comp = comp.sort_values("delta_mg").copy()
    comp["sinal"] = comp["delta_mg"].map(lambda v: "melhor que o mercado" if v > 0 else "pior que o mercado")
    fig = px.bar(
        comp, x="delta_mg", y="lob", orientation="h", color="sinal",
        color_discrete_map={"melhor que o mercado": PINE, "pior que o mercado": NEGATIVO},
        text=comp["delta_mg"].map(lambda v: f"{v*100:+.1f} pp".replace(".", ",")),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.add_vline(x=0, line_color=MUTED)
    fig.update_xaxes(tickformat=".0%")
    _plot(fig, 300, xtitle="margem da Akad − margem do mercado", legend=False)
    st.caption("O gráfico mostra a margem; a tabela acima traz pares e relevantes também em sinistralidade.")
    st.caption(resp[10]["curta"])

    # de onde vem a diferença de margem (fase Akad, quando existe)
    ref = base_f[base_f["ano"] >= 2022]
    ref = ref if not ref.empty else base_f
    anos_ref = sorted(int(a) for a in ref["ano"].unique())
    rot_ref = f"{anos_ref[0]}–{anos_ref[-1]}" if len(anos_ref) > 1 else str(anos_ref[0])
    linhas = []
    for lname in analise.LOB_ORDEM:
        g = ref[ref["lob"] == lname]
        a = g[g["codigo_susep"] == analise.AKAD]
        if g.empty or a.empty:
            continue
        ca, cm = analise.componentes(a), analise.componentes(g)
        for chave, nome in (("sin", "Sinistralidade"), ("resseg", "Resseguro líquido"), ("com", "Despesa comercial")):
            linhas.append({"lob": lname, "componente": nome, "pp": -(ca[chave] - cm[chave]) * 100})
    if linhas:
        st.markdown(f"##### De onde vem a diferença de margem ({rot_ref})")
        dd = pd.DataFrame(linhas)
        fig = px.bar(
            dd, x="pp", y="lob", color="componente", orientation="h", barmode="relative",
            color_discrete_map={"Sinistralidade": PINE, "Resseguro líquido": LILAC, "Despesa comercial": PINK},
            category_orders={"lob": list(reversed([l for l in analise.LOB_ORDEM if l in set(dd["lob"])]))},
        )
        fig.add_vline(x=0, line_color=MUTED)
        _plot(fig, 320, xtitle="contribuição para (margem Akad − margem mercado), em pontos percentuais; positivo ajuda a Akad", legend=True)
        st.caption(
            "Resseguro líquido = despesa − receita com resseguro. Contribuição positiva em resseguro significa "
            "que a Akad cede menos risco que o mercado: mais margem nos anos bons, mas mais capital e volatilidade retidos."
        )


def _respostas(resp: list[dict]) -> None:
    st.markdown("#### Respostas do case")
    st.caption(
        "Os números são recalculados com os filtros atuais. O contexto de marca (Q10) e a recomendação da "
        "Q12 são julgamento, não resultado automático. Para a leitura completa, deixe o filtro em 2020–2025."
    )
    texto = []
    for item in resp:
        st.markdown(f"### {item['n']} · {item['pergunta']}")
        st.markdown(item["resposta"])
        texto.append(f"## {item['n']} · {item['pergunta']}\n\n{item['resposta']}\n")
        st.divider()
    st.download_button(
        "Baixar respostas em Markdown",
        "\n".join(texto),
        file_name="respostas_akad.md",
        mime="text/markdown",
    )
    st.caption("O roteiro completo, com mercado 101 e leitura de cada gráfico, é um documento local e não versionado.")


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

    tab_visao, tab_mercado, tab_rent, tab_sin, tab_conc, tab_akad, tab_resp = st.tabs(
        ["Visão geral", "Mercado", "Rentabilidade", "Sinistralidade", "Concorrência", "Akad", "Respostas"]
    )
    with tab_visao:
        _visao(lob, lob_ano, base_f, resp)
    with tab_mercado:
        _mercado(lob, base_f, resp)
    with tab_rent:
        _rentabilidade(lob, resp)
    with tab_sin:
        _sinistralidade(lob, lob_ano, base_f, resp)
    with tab_conc:
        _concorrencia(base_f, resp)
    with tab_akad:
        _akad(base_f, resp)
    with tab_resp:
        _respostas(resp)
