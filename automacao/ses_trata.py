#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tratamento das respostas do SES - Case Trainee Akad 2027
========================================================

Le todos os HTML salvos em raw/ pelo ses_coleta.py e monta uma tabela unica
em processed/base_ses.csv, no formato longo:

    ramo_codigo, lob, ano, periodo_ini, periodo_fim, codigo_susep, seguradora,
    premio_ganho, sinistro_ocorrido, despesa_resseguro, receita_resseguro,
    despesa_comercial, sinistralidade, sinistralidade_susep, lucro, margem

Regras de metodo:
  - sinistralidade = soma(sinistro ocorrido) / soma(premio ganho)  [razao de somas,
    nunca media de razoes]
  - lucro = premio_ganho + receita_reesseguro - sinistro_ocorrido
            - despesa_reesseguro - despesa_comercial
  - margem = lucro / premio_ganho

Uso:
    python ses_trata.py
"""

from __future__ import annotations

import html as html_lib
import re
from io import StringIO
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
RAW = BASE_DIR / "raw"
PROC = BASE_DIR / "processed"
PROC.mkdir(exist_ok=True)

# codigo do ramo -> LOB do case
CODIGO_PARA_LOB = {
    "0351": "RCG",
    "0378": "E&O",
    "0118": "Empresarial",
    "0644": "Transportes", "0621": "Transportes", "0622": "Transportes",
    "0632": "Transportes", "0645": "Transportes", "0652": "Transportes",
    "0654": "Transportes", "0655": "Transportes", "0656": "Transportes",
    "0775": "Garantia", "0776": "Garantia",
}

# nome canonico da coluna no SES -> nome na nossa tabela
RENOMEAR = {
    "Código SUSEP": "codigo_susep",
    "Empresa": "seguradora",
    "Prêmio Ganho": "premio_ganho",
    "Sinistro Ocorrido": "sinistro_ocorrido",
    "Despesa com Resseguro": "despesa_resseguro",
    "Receita com Resseguro": "receita_resseguro",
    "Despesa Comercial": "despesa_comercial",
    "Sinistralidade": "sinistralidade_susep",
}


def canonico(nome) -> str:
    """Remove o sobrescrito (¹ ² ³) que a SUSEP usa para marcar series."""
    return re.sub(r"\s*[¹²³]\s*$", "", str(nome)).strip()


def para_numero(valor):
    """Converte numero em formato pt-BR ('9.705.565.371', '0,53') para float."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    texto = str(valor).strip().replace(" ", "")
    if not texto:
        return None
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def metadados(bruto: str):
    """Le do rodape da propria pagina quais ramos e periodo foram consultados."""
    texto = html_lib.unescape(re.sub(r"<[^>]+>", " ", bruto))
    texto = re.sub(r"\s+", " ", texto)
    m = re.search(
        r"Ramos selecionados\s+([\d,\s]+?)\s+Período de\s+(\d{6})\s+Período até\s+(\d{6})",
        texto,
    )
    if not m:
        return None
    ramos = [r.strip() for r in m.group(1).split(",") if r.strip()]
    return ramos, m.group(2), m.group(3)


def ler_arquivo(caminho: Path):
    bruto = caminho.read_text(encoding="utf-8", errors="replace")

    meta = metadados(bruto)
    if meta is None:
        return None, "sem rodape com ramos/periodo"
    ramos, inicio, fim = meta

    try:
        tabelas = pd.read_html(StringIO(bruto))
    except ValueError:
        return None, "nenhuma tabela"

    alvo = None
    for tabela in tabelas:
        colunas = [canonico(c) for c in tabela.columns]
        if "Empresa" in colunas and "Prêmio Ganho" in colunas:
            alvo = tabela
            break
    if alvo is None:
        return None, "tabela de resultado nao encontrada"

    alvo = alvo.rename(columns={c: RENOMEAR.get(canonico(c), canonico(c)) for c in alvo.columns})

    faltando = [c for c in RENOMEAR.values() if c not in alvo.columns]
    if faltando:
        return None, f"colunas ausentes: {faltando}"

    corpo = alvo[alvo["seguradora"].astype(str).str.strip() != "Totais"].copy()
    totais = alvo[alvo["seguradora"].astype(str).str.strip() == "Totais"]

    for coluna in [
        "premio_ganho", "sinistro_ocorrido", "despesa_resseguro",
        "receita_resseguro", "despesa_comercial", "sinistralidade_susep",
    ]:
        corpo[coluna] = corpo[coluna].map(para_numero)

    corpo["codigo_susep"] = (
        corpo["codigo_susep"].map(lambda v: str(int(float(v))).zfill(5) if pd.notna(v) else None)
    )

    ano = inicio[:4] if inicio[:4] == fim[:4] else f"{inicio[:4]}-{fim[:4]}"

    corpo = corpo.assign(
        ramo_codigo=",".join(ramos),
        lob="/".join(sorted({CODIGO_PARA_LOB.get(r, "?") for r in ramos})),
        ano=ano,
        periodo_ini=inicio,
        periodo_fim=fim,
    )

    corpo["sinistralidade"] = (
        corpo["sinistro_ocorrido"] / corpo["premio_ganho"]
    ).where(corpo["premio_ganho"] > 0)

    corpo["lucro"] = (
        corpo["premio_ganho"] + corpo["receita_resseguro"]
        - corpo["sinistro_ocorrido"] - corpo["despesa_resseguro"]
        - corpo["despesa_comercial"]
    )
    corpo["margem"] = (corpo["lucro"] / corpo["premio_ganho"]).where(corpo["premio_ganho"] > 0)

    conferencia = None
    if not totais.empty:
        soma = corpo["premio_ganho"].sum()
        oficial = para_numero(totais.iloc[0]["premio_ganho"])
        if oficial:
            conferencia = abs(soma - oficial) / oficial

    return corpo, conferencia


def main() -> None:
    arquivos = sorted(RAW.glob("*.html"))
    if not arquivos:
        print("Nenhum HTML em raw/. Rode o ses_coleta.py primeiro.")
        return

    pedacos, problemas = [], []
    for caminho in arquivos:
        dados, info = ler_arquivo(caminho)
        if dados is None:
            problemas.append((caminho.name, info))
            print(f"  ! {caminho.name}: {info}")
            continue
        pedacos.append(dados)
        aviso = ""
        if isinstance(info, float):
            aviso = f" | total confere ({info:.4%} de diferenca)"
        print(f"  ok {caminho.name}: {len(dados)} seguradoras{aviso}")

    if not pedacos:
        print("Nada aproveitavel.")
        return

    base = pd.concat(pedacos, ignore_index=True)

    ordem = [
        "ramo_codigo", "lob", "ano", "periodo_ini", "periodo_fim",
        "codigo_susep", "seguradora", "premio_ganho", "sinistro_ocorrido",
        "despesa_resseguro", "receita_resseguro", "despesa_comercial",
        "sinistralidade", "sinistralidade_susep", "lucro", "margem",
    ]
    base = base[ordem].sort_values(["lob", "ano", "premio_ganho"], ascending=[True, True, False])

    destino = PROC / "base_ses.csv"
    base.to_csv(destino, index=False, encoding="utf-8-sig")

    print()
    print(f"{len(arquivos) - len(problemas)} arquivos lidos, {len(problemas)} com problema")
    print(f"{len(base)} linhas -> {destino}")
    print()
    print("premio ganho por LOB (soma de tudo que foi lido):")
    resumo = base.groupby("lob")["premio_ganho"].sum().sort_values(ascending=False)
    for lob, valor in resumo.items():
        print(f"  {lob:<15} R$ {valor:>18,.0f}")


if __name__ == "__main__":
    main()
