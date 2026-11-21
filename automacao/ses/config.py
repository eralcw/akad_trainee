"""Carrega config.yaml e resolve os caminhos do projeto."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

AUTOMACAO_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = AUTOMACAO_DIR.parent
CONFIG_PATH = AUTOMACAO_DIR / "config.yaml"


@dataclass(frozen=True)
class Consulta:
    """Uma consulta ao SES: um ramo em um ano."""

    lob: str
    ramo: str
    ano: int

    @property
    def periodo(self) -> tuple[str, str]:
        return f"{self.ano}01", f"{self.ano}12"

    @property
    def chave(self) -> str:
        return f"{self.ramo}_{self.ano}"


class Config:
    def __init__(self, caminho: Path = CONFIG_PATH):
        with open(caminho, encoding="utf-8") as f:
            self.dados = yaml.safe_load(f)

        pastas = self.dados["pastas"]
        self.raw = REPO_DIR / pastas["raw"]
        self.snapshots = REPO_DIR / pastas["snapshots"]
        self.runs = REPO_DIR / pastas["runs"]

    # -- atalhos --------------------------------------------------------
    @property
    def url(self) -> str:
        return self.dados["fonte"]["url"]

    @property
    def nome_consulta(self) -> str:
        return self.dados["fonte"]["consulta"]

    @property
    def agrupamento(self) -> str:
        return self.dados["fonte"]["agrupamento"]

    @property
    def anos(self) -> list[int]:
        p = self.dados["periodo"]
        return list(range(p["ano_inicio"], p["ano_fim"] + 1))

    @property
    def lobs(self) -> dict[str, list[str]]:
        return self.dados["lobs"]

    @property
    def ramo_para_lob(self) -> dict[str, str]:
        return {r: lob for lob, ramos in self.lobs.items() for r in ramos}

    @property
    def ramos(self) -> list[str]:
        return list(self.ramo_para_lob)

    @property
    def consultas(self) -> list[Consulta]:
        return [
            Consulta(lob, ramo, ano)
            for lob, ramos in self.lobs.items()
            for ramo in ramos
            for ano in self.anos
        ]

    @property
    def akad_codigo(self) -> str:
        return str(self.dados["akad"]["codigo_susep"]).zfill(5)

    @property
    def atualizacao(self) -> dict:
        return self.dados["atualizacao"]

    @property
    def contrato(self) -> dict:
        return self.dados["contrato"]
