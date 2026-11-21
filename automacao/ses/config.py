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
    """Uma consulta ao SES: um ramo em um período (ano fechado ou parcial)."""

    lob: str
    ramo: str
    ano: int
    mes_inicio: int = 1
    mes_fim: int = 12

    def __post_init__(self):
        if not 1 <= self.mes_inicio <= 12 or not 1 <= self.mes_fim <= 12:
            raise ValueError("mes deve estar entre 1 e 12")
        if self.mes_inicio > self.mes_fim:
            raise ValueError("mes_inicio nao pode ser maior que mes_fim")

    @property
    def periodo(self) -> tuple[str, str]:
        return f"{self.ano}{self.mes_inicio:02d}", f"{self.ano}{self.mes_fim:02d}"

    @property
    def completo(self) -> bool:
        return self.mes_inicio == 1 and self.mes_fim == 12

    @property
    def meses(self) -> int:
        return self.mes_fim - self.mes_inicio + 1

    @property
    def chave(self) -> str:
        if self.completo:
            return f"{self.ramo}_{self.ano}"
        return f"{self.ramo}_{self.ano}_{self.mes_inicio:02d}_{self.mes_fim:02d}"


class Config:
    def __init__(self, caminho: Path = CONFIG_PATH):
        with open(caminho, encoding="utf-8") as f:
            self.dados = yaml.safe_load(f)

        pastas = self.dados["pastas"]
        self.raw = REPO_DIR / pastas["raw"]
        self.snapshots = REPO_DIR / pastas["snapshots"]
        self.runs = REPO_DIR / pastas["runs"]
        self.raw_periodos = REPO_DIR / pastas.get("raw_periodos", "data/raw/periodos")
        self.atualizacoes = REPO_DIR / pastas.get("atualizacoes", "data/atualizacoes")

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

    def consultas_periodo(
        self,
        ano: int,
        mes_inicio: int,
        mes_fim: int,
        ramos: list[str] | None = None,
        lobs: list[str] | None = None,
    ) -> list[Consulta]:
        """Consultas de um periodo parcial, restritas por ramo ou LOB."""
        if ramos:
            alvo = [r for r in ramos if r in self.ramo_para_lob]
            desconhecidos = [r for r in ramos if r not in self.ramo_para_lob]
            if desconhecidos:
                raise ValueError(f"ramos desconhecidos: {desconhecidos}")
        elif lobs:
            alvo = []
            for lob in lobs:
                if lob not in self.lobs:
                    raise ValueError(f"LOB desconhecida: {lob}")
                alvo.extend(self.lobs[lob])
        else:
            alvo = self.ramos
        vistos = []
        for r in alvo:
            if r not in vistos:
                vistos.append(r)
        return [
            Consulta(self.ramo_para_lob[r], r, ano, mes_inicio, mes_fim)
            for r in vistos
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
