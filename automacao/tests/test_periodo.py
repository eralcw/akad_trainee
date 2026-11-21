"""Testes do recorte parcial (trimestre/mes) - sem rede."""

from __future__ import annotations

import pytest

from ses.config import Config, Consulta


def test_chave_anual_nao_muda():
    c = Consulta("RCG", "0351", 2025)
    assert c.periodo == ("202501", "202512")
    assert c.chave == "0351_2025"
    assert c.completo is True
    assert c.meses == 12


def test_chave_parcial_inclui_meses():
    c = Consulta("RCG", "0351", 2025, 1, 3)
    assert c.periodo == ("202501", "202503")
    assert c.chave == "0351_2025_01_03"
    assert c.completo is False
    assert c.meses == 3


def test_mes_invalido_reprova():
    with pytest.raises(ValueError):
        Consulta("RCG", "0351", 2025, 0, 3)
    with pytest.raises(ValueError):
        Consulta("RCG", "0351", 2025, 4, 3)


def test_consultas_periodo_por_lob():
    cfg = Config()
    consultas = cfg.consultas_periodo(2025, 1, 3, lobs=["RCG"])
    assert len(consultas) == 1
    assert consultas[0].ramo == "0351"
    assert consultas[0].periodo == ("202501", "202503")


def test_consultas_periodo_por_ramo():
    cfg = Config()
    consultas = cfg.consultas_periodo(2025, 4, 6, ramos=["0775", "0776"])
    assert {c.ramo for c in consultas} == {"0775", "0776"}
    assert all(c.lob == "Garantia" for c in consultas)


def test_ramo_desconhecido_reprova():
    cfg = Config()
    with pytest.raises(ValueError):
        cfg.consultas_periodo(2025, 1, 3, ramos=["9999"])
