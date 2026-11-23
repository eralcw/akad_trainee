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
            legend: bool = True, topo: int = 44):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=13, color=INK),
        margin=dict(l=8, r=8, t=topo, b=8),
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


def _plot(fig, height: int = 330, ytitle: str | None = None, xtitle: str | None = None,
          legend: bool = True, topo: int = 44):
    st.plotly_chart(_layout(fig, height, ytitle, xtitle, legend, topo), use_container_width=True, config=CFG)


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
    _folga_x(fig, d["premio_bi"])
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
    _folga_x(fig, d["lucro_bi"])
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
    _folga_x(fig, d["margem"])
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
    _folga_x(fig, d["sinistralidade"])
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
    fig.update_traces(textposition="top center", textfont=dict(size=11.5))
    xmax = float(trend["vol"].max() or 0)
    ymax = float(trend["sin_media"].max() or 0)
    xmin = float(trend["vol"].min() or 0)
    fig.update_xaxes(
        tickformat=".0%",
        range=[max(0, xmin - xmax * 0.18), xmax * 1.14],
    )
    fig.update_yaxes(
        tickformat=".0%",
        range=[max(0, float(trend["sin_media"].min() or 0) * 0.6), ymax * 1.22],
    )
    _plot(
        fig, 390,
        xtitle="volatilidade da sinistralidade (desvio-padrão)",
        ytitle="sinistralidade média anual",
        legend=False, topo=56,
    )
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
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=seg["rank"], y=seg["cum"], mode="lines+markers", line=dict(color=LILAC, width=2), marker=dict(size=4), name="acumulado"))
    fig.add_hline(y=0.8, line_dash="dash", line_color=MUTED, annotation_text="80%")
    fig.update_yaxes(tickformat=".0%")
    _plot(fig, 280, xtitle="seguradoras ordenadas por prêmio", ytitle="share acumulado", legend=False)

    # --- mapa de posicionamento: só as relevantes, com escala controlada ---
    st.markdown("##### Posicionamento: risco × rentabilidade")
    mostrar_todas = st.checkbox(
        "Incluir as demais seguradoras da LOB (pontos pequenos, sem rótulo)", value=False
    )
    base_mapa = seg if mostrar_todas else mesa.copy()
    base_mapa = base_mapa.sort_values("premio", ascending=False).head(24).copy()

    x_lo, x_hi = -0.25, 1.25
    y_lo, y_hi = -0.70, 0.90
    base_mapa["x"] = base_mapa["sinistralidade"].clip(x_lo, x_hi)
    base_mapa["y"] = base_mapa["margem"].clip(y_lo, y_hi)
    base_mapa["fora"] = (
        base_mapa["sinistralidade"].ne(base_mapa["x"])
        | base_mapa["margem"].ne(base_mapa["y"])
    )
    rotulados = set(base_mapa.nlargest(6, "premio")["codigo_susep"]) | {analise.AKAD}
    base_mapa["rotulo"] = [
        analise.nome_curto(n) if c in rotulados else ""
        for c, n in zip(base_mapa["codigo_susep"], base_mapa["seguradora"])
    ]

    fig = px.scatter(
        base_mapa,
        x="x",
        y="y",
        size="premio",
        color="share",
        text="rotulo",
        hover_name="seguradora",
        color_continuous_scale=["#F4F5FD", LILAC],
        size_max=38,
        custom_data=[
            "premio", "share", "sinistralidade", "margem", "fora",
        ],
    )
    fig.update_traces(
        textposition="top center",
        textfont=dict(size=10.5, color=INK),
        marker=dict(line=dict(width=1, color="#FFFFFF")),
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "prêmio R$ %{customdata[0]:,.0f}<br>"
            "share %{customdata[1]:.1%}<br>"
            "sinistralidade %{customdata[2]:.1%}<br>"
            "margem %{customdata[3]:.1%}"
            "<extra></extra>"
        ),
    )

    # quadrantes nomeados
    xm, ym = mercado["sinistralidade"], mercado["margem"]
    fig.add_vline(x=xm, line_dash="dash", line_color=MUTED, line_width=1)
    fig.add_hline(y=ym, line_dash="dash", line_color=MUTED, line_width=1)
    for x, y, txt, cor in [
        (x_lo + 0.03, y_hi - 0.06, "risco baixo · margem alta", "#2E7D5B"),
        (x_hi - 0.03, y_hi - 0.06, "risco alto · margem alta", "#B4723A"),
        (x_lo + 0.03, y_lo + 0.04, "risco baixo · margem baixa", "#9AA0B5"),
        (x_hi - 0.03, y_lo + 0.04, "risco alto · margem baixa", "#C8451F"),
    ]:
        fig.add_annotation(
            x=x, y=y, text=txt, showarrow=False,
            font=dict(size=10, color=cor), opacity=0.85,
            xanchor="left" if x < 0 else "right",
            yanchor="top" if y > 0 else "bottom",
        )

    # Akad em destaque
    if destaques:
        marcados = base_mapa[base_mapa["codigo_susep"].isin(destaques)]
        if not marcados.empty:
            fig.add_trace(
                go.Scatter(
                    x=marcados["x"], y=marcados["y"], mode="markers",
                    marker=dict(symbol="circle-open", size=26, color="#143057",
                                line=dict(width=2.5)),
                    name="busca", hoverinfo="skip", showlegend=False,
                )
            )

    ak = base_mapa[base_mapa["codigo_susep"] == analise.AKAD]
    if not ak.empty:
        fig.add_trace(
            go.Scatter(
                x=ak["x"], y=ak["y"], mode="markers",
                marker=dict(symbol="star", size=20, color=analise.COR_AKAD,
                            line=dict(width=1.5, color="#FFFFFF")),
                name="Akad", hoverinfo="skip", showlegend=False,
            )
        )

    fig.update_xaxes(tickformat=".0%", range=[x_lo - 0.03, x_hi + 0.03])
    fig.update_yaxes(tickformat=".0%", range=[y_lo - 0.03, y_hi + 0.03])
    _plot(fig, 400, xtitle="sinistralidade", ytitle="margem", legend=False)
    st.caption(
        "Cada ponto é uma seguradora: tamanho = prêmio, cor = share. "
        "As linhas tracejadas marcam a média do mercado da LOB; o quadrante superior esquerdo "
        "é o melhor (menos sinistro, mais margem). Só entram as relevantes (top 80%) e os rótulos "
        "ficam nas seis maiores e na Akad; passe o mouse para ver todas."
    )
    if base_mapa["fora"].any():
        fora = base_mapa[base_mapa["fora"]][["seguradora", "sinistralidade", "margem"]]
        nomes = "; ".join(
            f"{analise.nome_curto(r.seguradora)} ({analise.f_pct(r.sinistralidade)} / {analise.f_pct(r.margem)})"
            for r in fora.head(6).itertuples()
        )
        resto = "" if len(fora) <= 6 else f"; e mais {len(fora) - 6}"
        st.caption(f"Fora da escala, presos na borda (sinistralidade / margem): {nomes}{resto}.")
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
    _folga_x(fig, comp["delta_mg"])
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
        use_container_width=True,
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
