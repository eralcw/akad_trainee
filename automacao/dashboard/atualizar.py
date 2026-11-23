"""Aba de atualizacao: dispara o workflow do GitHub e mostra o estado."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from . import github_api
from .dados import carregar_cfg

TRIMESTRES = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
MESES = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}
STATUS = {
    "queued": "na fila",
    "in_progress": "em execução",
    "completed": "concluída",
    "requested": "solicitada",
    "waiting": "aguardando",
}
CONCLUSAO = {
    "success": "sucesso",
    "failure": "falha",
    "cancelled": "cancelada",
    "skipped": "ignorada",
}


def _segredo():
    try:
        return st.secrets["github"]
    except Exception:
        return None


def _senha_ok() -> bool:
    """Protege a aba quando `[app] senha_atualizacao` existe nos secrets."""
    try:
        senha = str(st.secrets["app"]["senha_atualizacao"])
    except Exception:
        return True
    if not senha:
        return True
    if st.session_state.get("upd_ok"):
        return True
    with st.form("upd_login"):
        valor = st.text_input("Senha para atualizar a base", type="password")
        if st.form_submit_button("Entrar"):
            if valor == senha:
                st.session_state["upd_ok"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False


def _tabela_execucoes(repo, execucoes: list[dict]) -> None:
    if not execucoes:
        st.info("Nenhuma execução encontrada para este workflow.")
        return
    linhas = []
    for r in execucoes:
        linhas.append(
            {
                "run": r.get("run_number") or r.get("id"),
                "quando": (r.get("created_at") or "").replace("T", " ").replace("Z", ""),
                "status": STATUS.get(r.get("status"), r.get("status") or "—"),
                "resultado": CONCLUSAO.get(r.get("conclusion"), r.get("conclusion") or "—"),
                "link": r.get("html_url"),
            }
        )
    df = pd.DataFrame(linhas)
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "link": st.column_config.LinkColumn("Abrir", display_text="ver no GitHub"),
            "run": st.column_config.TextColumn("Run"),
        },
    )


def render() -> None:
    cfg = carregar_cfg()
    segredo = _segredo()
    repo = github_api.repo_de_secrets(segredo) if segredo is not None else None

    st.subheader("Atualizar a base")
    st.caption(
        "A coleta roda no GitHub Actions. Este painel só escolhe o recorte, "
        "dispara o workflow e acompanha o resultado."
    )

    if not _senha_ok():
        return

    if repo is not None:
        with st.expander("Diagnóstico da conexão com o GitHub"):
            st.caption("Testa token, repositório, workflow e branch — sem disparar nada.")
            if st.button("Testar conexão"):
                for etapa in github_api.diagnostico(repo):
                    texto = f"**{etapa['etapa']}** — {etapa['detalhe']}"
                    if etapa["ok"]:
                        st.success(texto)
                    else:
                        st.error(texto)

    if repo is None:
        st.warning(
            "Token do GitHub não configurado. Preencha `.streamlit/secrets.toml` "
            "ou os Secrets do Streamlit Cloud para habilitar os botões."
        )

    execucoes: list[dict] = []
    if repo is not None:
        try:
            execucoes = github_api.execucoes(repo, 6)
        except RuntimeError as e:
            st.warning(f"Não foi possível ler as execuções: {e}")
    em_curso = github_api.em_andamento(execucoes)
    if em_curso:
        st.info("Há uma execução em andamento. O disparo fica bloqueado até ela terminar.")

    lob = st.selectbox("LOB", ["Todas"] + list(cfg.lobs), index=0)
    opcoes = cfg.ramos if lob == "Todas" else cfg.lobs[lob]
    ramos = st.multiselect("Ramos", opcoes, default=opcoes)
    if not ramos:
        st.error("Selecione pelo menos um ramo.")

    modo = st.radio(
        "Período",
        ["Ano fechado", "Trimestre", "Intervalo de meses"],
        horizontal=True,
    )

    anos_anuais = list(cfg.anos)
    anos_parciais = sorted(set(anos_anuais) | {dt.date.today().year})

    if modo == "Ano fechado":
        ano = st.selectbox("Ano", anos_anuais, index=len(anos_anuais) - 1)
        mes_ini, mes_fim = 1, 12
    else:
        ano = st.selectbox("Ano", anos_parciais, index=len(anos_parciais) - 1)
        if ano not in anos_anuais:
            st.caption("Ano fora do período do case: fica registrado como atualização parcial de monitoramento.")
        if modo == "Trimestre":
            tri = st.selectbox(
                "Trimestre", [1, 2, 3, 4],
                format_func=lambda q: f"Q{q} ({MESES[TRIMESTRES[q][0]]} a {MESES[TRIMESTRES[q][1]]})",
                index=3,
            )
            mes_ini, mes_fim = TRIMESTRES[tri]
        else:
            c1, c2 = st.columns(2)
            mes_ini = c1.selectbox("Mês inicial", list(range(1, 13)), format_func=lambda m: MESES[m], index=0)
            mes_fim = c2.selectbox("Mês final", list(range(1, 13)), format_func=lambda m: MESES[m], index=11)
            if mes_ini > mes_fim:
                st.error("O mês inicial não pode ser maior que o final.")

    forcar = st.checkbox(
        "Baixar de novo mesmo o que já existe (cria um novo arquivo)", value=False
    )
    periodo_txt = f"{ano}{mes_ini:02d}–{ano}{mes_fim:02d}"
    st.markdown(
        f"**{len(ramos)} consulta(s)** · ramos {', '.join(ramos) if ramos else '—'} · {periodo_txt}"
    )

    # quantas dessas consultas ja existem no raw
    novas = existentes = None
    try:
        from ses.extract import pendentes

        if modo == "Ano fechado":
            consultas = cfg.consultas_periodo(ano, 1, 12, ramos=ramos)
            pasta = cfg.raw
        else:
            consultas = cfg.consultas_periodo(ano, mes_ini, mes_fim, ramos=ramos)
            pasta = cfg.raw_periodos
        a_coletar, ja_existem = pendentes(cfg, forcar=forcar, consultas=consultas, pasta=pasta)
        novas, existentes = len(a_coletar), len(ja_existem)
    except Exception as e:  # nao impede o disparo
        st.caption(f"Não foi possível verificar o raw: {e}")

    if novas is not None:
        if forcar:
            st.caption(f"**{novas} consulta(s) serão baixadas de novo** (novo arquivo para cada uma).")
        elif existentes:
            st.warning(
                f"**{existentes} de {novas + existentes} consulta(s) já existem no raw.** "
                "Elas serão puladas, então nenhum `.xls` novo aparecerá — só o registro do run. "
                "Marque **Baixar de novo** para forçar o download."
            )
        else:
            st.caption(f"**{novas} consulta(s) novas** serão baixadas.")

    if modo == "Ano fechado":
        st.caption("Ano fechado atualiza o snapshot anual. Reprocessar o raw refaz as 84 consultas.")
    else:
        st.caption(
            "Recorte parcial: grava em `data/atualizacoes` e não substitui o ano fechado. "
            "A base anual só muda com os 12 meses."
        )

    st.divider()
    confirmar = st.checkbox("Confirmo que quero disparar o workflow", value=False)
    bloqueado = repo is None or em_curso or not confirmar or not ramos or mes_ini > mes_fim
    b1, b2 = st.columns(2)
    coletar = b1.button("Coletar e atualizar", type="primary", disabled=bloqueado)
    reprocessar = b2.button("Só reprocessar raw", disabled=bloqueado)

    if coletar or reprocessar:
        inputs = {
            "ramos": ",".join(ramos),
            "anos": str(ano) if modo == "Ano fechado" else "",
            "periodo_ini": "" if modo == "Ano fechado" else f"{ano}{mes_ini:02d}",
            "periodo_fim": "" if modo == "Ano fechado" else f"{ano}{mes_fim:02d}",
            "coletar": "sim" if coletar else "nao",
            "forcar": "sim" if forcar else "nao",
        }
        try:
            github_api.disparar(repo, inputs)
            st.success(
                "Workflow disparado. Acompanhe em Execuções recentes ou na aba Actions. "
                "Se as consultas já existiam no raw, o run apenas registra o diário (JSON); "
                "para gerar um `.xls` novo, marque \"Baixar de novo\" e dispare outra vez."
            )
            st.session_state["ultimo_disparo"] = {
                "modo": "coleta + atualização" if coletar else "reprocessar raw",
                "periodo": periodo_txt,
                "ramos": ", ".join(ramos),
                "quando": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        except RuntimeError as e:
            st.error(str(e))

    if "ultimo_disparo" in st.session_state:
        u = st.session_state["ultimo_disparo"]
        st.caption(
            f"Último disparo nesta sessão: {u['modo']} · {u['periodo']} · "
            f"ramos {u['ramos']} · {u['quando']}"
        )

    st.divider()
    st.markdown("#### Execuções recentes")
    c1, c2 = st.columns([1, 3])
    if c1.button("Atualizar status"):
        st.rerun()
    if repo is not None:
        c2.link_button("Abrir GitHub Actions", github_api.url_actions(repo))
    _tabela_execucoes(repo, execucoes)
