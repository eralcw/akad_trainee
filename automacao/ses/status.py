"""Painel de saude da operacao: cobertura, frescor e disponibilidade da fonte."""

from __future__ import annotations

import urllib.request
from datetime import datetime

from . import publish
from .config import Config
from .transform import ler_manifesto, ultimas_entradas


def fonte_disponivel(cfg: Config, timeout: float = 15) -> bool:
    try:
        req = urllib.request.Request(cfg.url, headers={"User-Agent": "Mozilla/5.0 (case academico)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def coletar_status(cfg: Config, checar_fonte: bool = False, max_idade_dias: int = 100) -> dict:
    manifesto = ler_manifesto(cfg.raw)
    ultimas = ultimas_entradas(manifesto)
    esperadas = [c.chave for c in cfg.consultas]
    no_raw = [k for k in esperadas if k in ultimas]

    vigente = publish.atual(cfg)
    meta = publish.carregar_meta(cfg) if vigente else {}
    criado = meta.get("criado_em")
    idade = (datetime.now() - datetime.fromisoformat(criado)).days if criado else None

    relatorio = meta.get("relatorio", {})
    cob = relatorio.get("cobertura", {})
    ultima_coleta = max((e["quando"] for e in ultimas.values()), default=None)

    status = {
        "snapshot_vigente": vigente,
        "snapshots_disponiveis": len(publish.listar(cfg)),
        "dados_atualizados_em": criado,
        "idade_dias": idade,
        "dados_ok": bool(vigente) and relatorio.get("aprovado", False),
        "dados_frescos": idade is not None and idade <= max_idade_dias,
        "cobertura_raw": f"{len(no_raw)}/{len(esperadas)}",
        "cobertura_snapshot": f"{cob.get('lidas', 0)}/{cob.get('esperadas', len(esperadas))}",
        "totais_conferidos": f"{cob.get('totais_conferidos', 0)}/{cob.get('esperadas', len(esperadas))}",
        "ultima_coleta_raw": ultima_coleta,
        "avisos": relatorio.get("avisos", []),
        "fonte_ses_disponivel": fonte_disponivel(cfg) if checar_fonte else None,
    }
    return status
