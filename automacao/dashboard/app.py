"""Aplicacao Streamlit: operacao da base SES/SUSEP."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from . import atualizar, dados, github_api, painel
from .estilo import CSS

REPO_URL = "https://github.com/eralcw/akad_trainee"
LOGO = Path(__file__).resolve().parent / "assets" / "akad_logo.png"


def _segredo():
    try:
        return st.secrets["github"]
    except Exception:
        return None


def _data(valor) -> str:
    if not valor:
        return "—"
    return str(valor).replace("T", " ").replace("Z", "")


def _header() -> None:
    st.markdown(
        """
        <div class="masthead">
          <div class="kicker">Akad Seguros · base SES/SUSEP · 2020–2025</div>
          <h1>Operação da base</h1>
          <p class="standfirst">
            Leia o mercado, a rentabilidade e a posição da Akad nas cinco LOBs. Quando precisar,
            atualize o snapshot anual ou acompanhe um recorte parcial. A coleta roda no GitHub
            Actions; aqui você escolhe o recorte, dispara o workflow e vê o resultado publicado.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sidebar(s: dict) -> None:
    repo = github_api.repo_de_secrets(_segredo()) if _segredo() is not None else None
    with st.sidebar:
        st.markdown("### Snapshot anual")
        st.markdown(f"`{s['snapshot'] or 'nenhum'}`")
        st.caption(f"Criado em {_data(s['criado_em'])}")
        st.markdown(
            f"Cobertura raw **{s['cobertura_raw']}**  \n"
            f"Cobertura snapshot **{s['cobertura_snapshot']}**  \n"
            f"Totais SES **{s['totais']}**  \n"
            f"Linhas **{s['linhas'] if s['linhas'] is not None else '—'}**"
        )
        st.caption(f"Última coleta no raw: {_data(s['ultima_coleta'])}")
        st.markdown("### Recortes parciais")
        st.markdown(f"**{s['parciais']}** publicado(s) em `data/atualizacoes`")
        st.divider()
        if repo is not None:
            st.link_button("Abrir GitHub Actions", github_api.url_actions(repo), use_container_width=True)
            st.caption("GitHub conectado.")
        else:
            st.caption("GitHub sem token configurado; a aba de atualização fica em leitura.")
        st.link_button("Ver código no GitHub", REPO_URL, use_container_width=True)
        st.divider()
        st.caption(
            "O app não grava arquivos. O workflow baixa do SES, valida, comita o raw "
            "e publica o snapshot. O app relê o que foi comitado."
        )


def _status_tab(s: dict) -> None:
    st.subheader("Status da base")
    ledger = (
        '<div class="ledger">'
        f'<div><span class="lab">Snapshot anual</span><span class="val">{s["snapshot"] or "—"}</span>'
        f'<span class="nota">{_data(s["criado_em"])}</span></div>'
        f'<div><span class="lab">Cobertura raw</span><span class="val">{s["cobertura_raw"]}</span>'
        '<span class="nota">consultas do config</span></div>'
        f'<div><span class="lab">Totais conferidos</span><span class="val">{s["totais"]}</span>'
        '<span class="nota">contra a linha Totais do SES</span></div>'
        f'<div><span class="lab">Linhas na base</span><span class="val">{s["linhas"] if s["linhas"] is not None else "—"}</span>'
        f'<span class="nota">{s["parciais"]} recorte(s) parcial(is)</span></div>'
        "</div>"
    )
    st.markdown(ledger, unsafe_allow_html=True)

    st.markdown("#### Atualizações parciais")
    parciais = dados.atualizacoes(12)
    if not parciais:
        st.info("Nenhum recorte parcial publicado ainda. Use a aba Atualizar base com trimestre ou intervalo de meses.")
    else:
        df = pd.DataFrame(parciais)
        df["aprovado"] = df["aprovado"].map({True: "sim", False: "não", None: "—"})
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "atualizacao": st.column_config.TextColumn("Atualização"),
                "criado_em": st.column_config.TextColumn("Criado em"),
                "periodo": st.column_config.TextColumn("Período"),
                "meses": st.column_config.NumberColumn("Meses", format="%d"),
                "ramos": st.column_config.NumberColumn("Ramos", format="%d"),
                "linhas": st.column_config.NumberColumn("Linhas", format="%d"),
                "cobertura": st.column_config.TextColumn("Cobertura"),
                "aprovado": st.column_config.TextColumn("Contrato"),
            },
        )

    if s["avisos"]:
        with st.expander(f"Avisos do último contrato ({len(s['avisos'])})"):
            for a in s["avisos"]:
                st.markdown(f"- {a}")

    st.caption(
        "O recorte parcial fica separado do snapshot anual de propósito: um trimestre "
        "não pode substituir o ano fechado."
    )


def _metodo_tab() -> None:
    st.subheader("Como a atualização funciona")
    st.markdown(
        """
        **Ano fechado.** O workflow pede janeiro a dezembro ao SES para os ramos escolhidos.
        O resultado passa pelo contrato e, se aprovar, vira um novo snapshot em
        `data/snapshots`. É a base que alimenta a análise de 2020–2025.

        **Trimestre ou intervalo de meses.** O workflow pede só o período escolhido,
        grava em `data/raw/periodos` e publica em `data/atualizacoes` com `parcial = true`.
        Isso permite acompanhar o trimestre sem sobrescrever o ano fechado. A base anual
        só muda quando os 12 meses são coletados.

        **Seguradora ativa.** É a que tem prêmio ganho maior que zero no ano. Quem aparece
        no SES apenas por registro cadastral não entra em contagem nem em ranking.

        **Sinistralidade.** Sempre soma dos sinistros dividida pela soma dos prêmios,
        nunca média de razões. A coluna Sinistralidade da SUSEP é usada só como conferência;
        a análise recalcula.

        **Resultado técnico.** Prêmio ganho + receita com resseguro − sinistro ocorrido
        − despesa com resseguro − despesa comercial. Não é lucro contábil: não inclui
        despesa administrativa, imposto nem resultado financeiro.

        **Conferência.** Em cada consulta, a soma das seguradoras é comparada com a linha
        Totais que a própria SUSEP publica no fim da tabela. Se não bater, o contrato reprova
        e nada é publicado.
        """
    )
    st.markdown("#### O caminho do botão")
    st.markdown(
        """
        1. O app envia um `workflow_dispatch` para o GitHub com ramos, anos e período.
        2. O GitHub Actions instala Python e Chromium, abre o SES e coleta.
        3. O pipeline valida os totais, comita `data/raw`, `data/atualizacoes`,
           `data/snapshots` e `data/runs`.
        4. O Streamlit relê o que foi comitado e mostra o status.
        """
    )
    st.link_button("Abrir o workflow no GitHub", f"{REPO_URL}/blob/main/.github/workflows/update.yml")
    st.link_button("Abrir o EDA", f"{REPO_URL}/blob/main/analise/eda.html")
    st.link_button("Abrir o roteiro de apresentação", f"{REPO_URL}/blob/main/analise/roteiro_apresentacao.md")


def main() -> None:
    st.set_page_config(
        page_title="Akad · Base SES/SUSEP",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    if LOGO.exists():
        try:
            st.logo(str(LOGO), size="large", link=REPO_URL)
        except Exception:
            with st.sidebar:
                st.image(str(LOGO), use_container_width=True)
    s = dados.status_geral()
    _header()
    _sidebar(s)
    tab_painel, tab_atualizar, tab_status, tab_metodo = st.tabs(
        ["Painel", "Atualizar base", "Status", "Método"]
    )
    with tab_painel:
        painel.render()
    with tab_atualizar:
        atualizar.render()
    with tab_status:
        _status_tab(s)
    with tab_metodo:
        _metodo_tab()
