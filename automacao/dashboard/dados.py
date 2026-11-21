"""Leitura do estado da base para a interface Streamlit (sem rede)."""

from __future__ import annotations

import json
from pathlib import Path

from ses import publish
from ses.config import Config
from ses.transform import ler_manifesto, ultimas_entradas


def carregar_cfg() -> Config:
    return Config()


def status_geral() -> dict:
    cfg = Config()
    vigente = publish.atual(cfg)
    meta = publish.carregar_meta(cfg) if vigente else {}
    rel = meta.get("relatorio", {})
    cob = rel.get("cobertura", {})
    ultimas = ultimas_entradas(ler_manifesto(cfg.raw))
    esperadas = len(cfg.consultas)
    return {
        "snapshot": vigente,
        "criado_em": meta.get("criado_em"),
        "linhas": meta.get("linhas"),
        "aprovado": rel.get("aprovado"),
        "cobertura_raw": f"{len(ultimas)}/{esperadas}",
        "cobertura_snapshot": f"{cob.get('lidas', 0)}/{cob.get('esperadas', esperadas)}",
        "totais": f"{cob.get('totais_conferidos', 0)}/{cob.get('esperadas', esperadas)}",
        "ultima_coleta": max((e.get("quando", "") for e in ultimas.values()), default=None),
        "avisos": rel.get("avisos", []),
        "snapshots": len(publish.listar(cfg)),
        "parciais": len(publish.listar_atualizacoes(cfg)),
    }


def atualizacoes(limite: int = 8) -> list[dict]:
    cfg = Config()
    nomes = publish.listar_atualizacoes(cfg)
    saida: list[dict] = []
    for nome in reversed(nomes[-limite:]):
        pasta = cfg.atualizacoes / nome
        try:
            meta = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        rel = meta.get("relatorio", {})
        cob = rel.get("cobertura", {})
        saida.append(
            {
                "atualizacao": nome,
                "criado_em": (meta.get("criado_em") or "").replace("T", " "),
                "periodo": f"{meta.get('periodo_ini', '?')}–{meta.get('periodo_fim', '?')}",
                "meses": meta.get("meses"),
                "ramos": len(meta.get("ramos", [])),
                "linhas": meta.get("linhas"),
                "cobertura": f"{cob.get('lidas', 0)}/{cob.get('esperadas', 0)}",
                "aprovado": rel.get("aprovado"),
            }
        )
    return saida


def cobertura_por_lob() -> dict:
    cfg = Config()
    ultimas = ultimas_entradas(ler_manifesto(cfg.raw))
    saida: dict[str, list[str]] = {}
    for c in cfg.consultas:
        if c.chave not in ultimas:
            saida.setdefault(c.lob, []).append(c.chave)
    return saida
