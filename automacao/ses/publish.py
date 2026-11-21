"""Publicacao transacional de snapshots (staging -> contrato -> promote) e rollback.

data/snapshots/
    20261120T180000/base.parquet, base.csv, meta.json
    latest.json            <- ponteiro: {"snapshot": "20261120T180000"}

O dashboard le SEMPRE pelo ponteiro. Promover = trocar o ponteiro de forma
atomica (escreve .tmp e renomeia). Rollback = apontar para um snapshot anterior.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import Config
from .transform import COLUNAS_VALOR

PONTEIRO = "latest.json"


def listar(cfg: Config) -> list[str]:
    if not cfg.snapshots.exists():
        return []
    return sorted(p.name for p in cfg.snapshots.iterdir() if (p / "base.parquet").exists())


def atual(cfg: Config) -> str | None:
    ponteiro = cfg.snapshots / PONTEIRO
    if not ponteiro.exists():
        return None
    return json.loads(ponteiro.read_text(encoding="utf-8")).get("snapshot")


def _apontar(cfg: Config, nome: str) -> None:
    cfg.snapshots.mkdir(parents=True, exist_ok=True)
    tmp = cfg.snapshots / (PONTEIRO + ".tmp")
    tmp.write_text(json.dumps({"snapshot": nome}), encoding="utf-8")
    tmp.replace(cfg.snapshots / PONTEIRO)


def carregar_base(cfg: Config, snapshot: str | None = None) -> pd.DataFrame:
    """Ponto de entrada do dashboard: le a base do snapshot vigente."""
    nome = snapshot or atual(cfg)
    if nome is None:
        raise FileNotFoundError("nenhum snapshot publicado; rode `pipeline.py atualizar`")
    return pd.read_parquet(cfg.snapshots / nome / "base.parquet")


def carregar_meta(cfg: Config, snapshot: str | None = None) -> dict:
    nome = snapshot or atual(cfg)
    if nome is None:
        return {}
    return json.loads((cfg.snapshots / nome / "meta.json").read_text(encoding="utf-8"))


def diff_retificacoes(anterior: pd.DataFrame, novo: pd.DataFrame, tol: float = 1.0) -> dict:
    """Compara com o snapshot anterior: quais valores a SUSEP/seguradoras corrigiram."""
    chave = ["ramo_codigo", "ano", "codigo_susep"]
    a = anterior.set_index(chave)[COLUNAS_VALOR]
    n = novo.set_index(chave)[COLUNAS_VALOR]

    comuns = a.index.intersection(n.index)
    delta = (n.loc[comuns] - a.loc[comuns]).abs().gt(tol).any(axis=1)
    alteradas = comuns[delta.to_numpy()]

    por_lob = {}
    if len(alteradas):
        lob_map = novo.drop_duplicates("ramo_codigo").set_index("ramo_codigo")["lob"]
        d = (n.loc[alteradas] - a.loc[alteradas])["premio_ganho"].reset_index()
        d["lob"] = d["ramo_codigo"].map(lob_map)
        por_lob = {k: float(v) for k, v in d.groupby("lob")["premio_ganho"].sum().items()}

    return {
        "linhas_alteradas": int(len(alteradas)),
        "linhas_novas": int(len(n.index.difference(a.index))),
        "linhas_removidas": int(len(a.index.difference(n.index))),
        "delta_premio_ganho_por_lob": por_lob,
    }


def publicar(cfg: Config, base: pd.DataFrame, relatorio: dict, extra_meta: dict | None = None) -> dict:
    """Promove a base como novo snapshot. Chamar SO com relatorio aprovado."""
    if not relatorio["aprovado"]:
        raise RuntimeError("contrato reprovado: snapshot nao pode ser promovido")

    anterior_nome = atual(cfg)
    diff = None
    if anterior_nome:
        diff = diff_retificacoes(carregar_base(cfg, anterior_nome), base)
        # base identica a vigente: nao cria snapshot novo
        if diff["linhas_alteradas"] == diff["linhas_novas"] == diff["linhas_removidas"] == 0:
            return {"publicado": False, "motivo": "base identica ao snapshot vigente",
                    "snapshot": anterior_nome, "diff": diff}

    nome = datetime.now().strftime("%Y%m%dT%H%M%S")
    sufixo = 0
    while (cfg.snapshots / nome).exists():   # dois snapshots no mesmo segundo
        sufixo += 1
        nome = f"{datetime.now():%Y%m%dT%H%M%S}_{sufixo}"
    staging = cfg.snapshots / f".staging_{nome}"
    final = cfg.snapshots / nome
    staging.mkdir(parents=True, exist_ok=True)
    try:
        base.to_parquet(staging / "base.parquet", index=False)
        base.to_csv(staging / "base.csv", index=False, encoding="utf-8-sig")
        meta = {
            "snapshot": nome,
            "criado_em": datetime.now().isoformat(timespec="seconds"),
            "linhas": int(len(base)),
            "relatorio": relatorio,
            "diff_vs_anterior": diff,
            "anterior": anterior_nome,
            **(extra_meta or {}),
        }
        (staging / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        staging.rename(final)      # snapshot completo aparece de uma vez
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _apontar(cfg, nome)            # promote: troca atomica do ponteiro
    return {"publicado": True, "snapshot": nome, "anterior": anterior_nome, "diff": diff}


def rollback(cfg: Config, destino: str | None = None) -> str:
    """Volta o ponteiro para um snapshot anterior (por padrao, o imediatamente anterior)."""
    todos = listar(cfg)
    vigente = atual(cfg)
    if destino is None:
        if vigente not in todos or todos.index(vigente) == 0:
            raise RuntimeError("nao ha snapshot anterior para voltar")
        destino = todos[todos.index(vigente) - 1]
    elif destino not in todos:
        raise RuntimeError(f"snapshot {destino} nao existe; disponiveis: {todos}")
    _apontar(cfg, destino)
    return destino
