"""Contrato de dados: so publica snapshot se a base passar em todos os checks.

Erros bloqueiam a publicacao; avisos apenas aparecem no relatorio e no painel.
"""

from __future__ import annotations

import pandas as pd

from .config import Config
from .transform import COLUNAS_VALOR, Diagnostico


def validar(cfg: Config, base: pd.DataFrame, diagnosticos: list[Diagnostico]) -> dict:
    erros: list[str] = []
    avisos: list[str] = []
    contrato = cfg.contrato
    esperadas = len(cfg.consultas)

    # 1) Cobertura: todas as consultas lidas sem erro
    com_erro = [d for d in diagnosticos if d.erro]
    for d in com_erro:
        erros.append(f"{d.chave}: {d.erro}")
    lidas = [d for d in diagnosticos if not d.erro]

    # 2) Consultas vazias (ramo sem mercado no ano) dentro do limite
    vazias = [d.chave for d in lidas if d.n_seguradoras == 0]
    if len(vazias) > contrato["max_consultas_vazias"]:
        erros.append(
            f"{len(vazias)} consultas vazias (limite {contrato['max_consultas_vazias']}): {vazias}"
        )
    elif vazias:
        avisos.append(f"consultas sem seguradoras (ramo sem mercado no ano?): {vazias}")

    # 3) Reconciliacao com a linha "Totais" do proprio SES
    for d in lidas:
        for col, r in d.totais.items():
            if not r["ok"]:
                erros.append(
                    f"{d.chave}: {col} nao bate com 'Totais' do SES "
                    f"(soma={r['soma']:,.0f} oficial={r['oficial']:,.0f})"
                )
    n_totais_ok = sum(1 for d in lidas if d.totais and all(r["ok"] for r in d.totais.values()))

    # 4) Rodape do SES coerente com o que foi pedido (quando o arquivo traz o rodape)
    for d in lidas:
        if d.rodape_ok is False:
            erros.append(f"{d.chave}: ramo/periodo do rodape do SES diferem da consulta pedida")

    if not base.empty:
        # 5) Sem duplicatas
        dups = base.duplicated(["ramo_codigo", "ano", "codigo_susep"], keep=False)
        if dups.any():
            erros.append(f"{int(dups.sum())} linhas duplicadas (ramo, ano, seguradora)")

        # 6) Premio ganho positivo em cada LOB x ano
        por_lob_ano = base.groupby(["lob", "ano"])["premio_ganho"].sum()
        for lob in cfg.lobs:
            for ano in cfg.anos:
                if por_lob_ano.get((lob, ano), 0) <= 0:
                    erros.append(f"{lob} {ano}: premio ganho total <= 0")

        # 7) Colunas obrigatorias nao podem estar zeradas em uma LOB inteira
        for lob, grupo in base.groupby("lob"):
            for col in contrato["colunas_obrigatorias"]:
                if (grupo[col].fillna(0) == 0).all():
                    erros.append(f"{lob}: coluna {col} totalmente zerada")

        # 8) Sinais: o metodo assume valores positivos
        for col in COLUNAS_VALOR:
            n_neg = int((base[col] < 0).sum())
            if n_neg:
                avisos.append(f"{n_neg} linhas com {col} negativo (estornos/ajustes) - conferir sinal")

        # 9) A empresa-alvo precisa aparecer
        if cfg.akad_codigo not in set(base["codigo_susep"]):
            erros.append(f"empresa-alvo {cfg.akad_codigo} (Akad) ausente da base")
    else:
        erros.append("base vazia")

    return {
        "aprovado": not erros,
        "erros": erros,
        "avisos": avisos,
        "cobertura": {
            "esperadas": esperadas,
            "lidas": len(lidas),
            "vazias": len(vazias),
            "totais_conferidos": n_totais_ok,
        },
        "linhas": int(len(base)),
    }


def validar_periodo(
    cfg: Config,
    base: pd.DataFrame,
    diagnosticos: list[Diagnostico],
    consultas,
) -> dict:
    """Contrato do recorte parcial.

    Nao exige as 84 consultas nem a Akad: o recorte e intencional. Exige
    cobertura do que foi pedido, totais do SES, rodape, sem duplicata e
    sinaliza periodo sem premio positivo.
    """
    erros: list[str] = []
    avisos: list[str] = []

    com_erro = [d for d in diagnosticos if d.erro]
    for d in com_erro:
        erros.append(f"{d.chave}: {d.erro}")
    lidas = [d for d in diagnosticos if not d.erro]
    vazias = [d.chave for d in lidas if d.n_seguradoras == 0]
    if vazias:
        avisos.append(f"consultas sem seguradoras no periodo: {vazias}")

    for d in lidas:
        for col, r in d.totais.items():
            if not r["ok"]:
                erros.append(
                    f"{d.chave}: {col} nao bate com 'Totais' do SES "
                    f"(soma={r['soma']:,.0f} oficial={r['oficial']:,.0f})"
                )
        if d.rodape_ok is False:
            erros.append(f"{d.chave}: ramo/periodo do rodape do SES diferem do pedido")

    n_totais_ok = sum(1 for d in lidas if d.totais and all(r["ok"] for r in d.totais.values()))

    if not base.empty:
        dups = base.duplicated(["ramo_codigo", "periodo_ini", "periodo_fim", "codigo_susep"], keep=False)
        if dups.any():
            erros.append(f"{int(dups.sum())} linhas duplicadas (ramo, periodo, seguradora)")
        if int((base["premio_ganho"] > 0).sum()) == 0:
            avisos.append("periodo sem premio ganho positivo (ramo sem movimento?)")
        for col in COLUNAS_VALOR:
            n_neg = int((base[col] < 0).sum())
            if n_neg:
                avisos.append(f"{n_neg} linhas com {col} negativo (estornos/ajustes)")
    else:
        avisos.append("base parcial vazia: nenhuma seguradora no periodo")

    return {
        "aprovado": not erros,
        "erros": erros,
        "avisos": avisos,
        "cobertura": {
            "esperadas": len(consultas),
            "lidas": len(lidas),
            "vazias": len(vazias),
            "totais_conferidos": n_totais_ok,
        },
        "linhas": int(len(base)),
        "parcial": True,
    }
