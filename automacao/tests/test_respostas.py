"""Respostas Q1–Q12: geração a partir do snapshot publicado, com filtros variados."""

from __future__ import annotations

import re

import pytest

from dashboard import analise as A
from dashboard import respostas as R


@pytest.fixture(scope="module")
def base():
    b = A.carregar_base()
    if b.empty:
        pytest.skip("sem snapshot anual publicado")
    return b


def _sem_lixo(itens):
    assert [i["n"] for i in itens] == [f"{n:02d}" for n in range(1, 13)]
    ruim = re.compile(r"\b(nan|None|inf)\b|\(None|None–")
    for i in itens:
        assert i["curta"].strip() and i["resposta"].strip()
        assert not ruim.search(i["resposta"]), (i["n"], ruim.search(i["resposta"]).group(0))
        assert not ruim.search(i["curta"]), (i["n"], ruim.search(i["curta"]).group(0))


def test_periodo_completo(base):
    itens = A.respostas(base)
    _sem_lixo(itens)
    lob = A.por_lob(base).set_index("lob")
    assert lob.index[0] in itens[0]["curta"]
    assert "bilhões" in itens[0]["curta"]
    assert A.f_pct(lob["sinistralidade"].max()) in itens[2]["curta"]
    assert lob["lucro"].idxmax() in itens[4]["curta"]
    assert "bilhões" in itens[4]["curta"]


def test_q2_nao_repete_lob_quando_lider_e_o_mesmo(base):
    atv = A.ativas_por_ano(base, "premio")
    mesmo_lider = atv[2020].idxmax() == atv[2025].idxmax()
    curta = A.respostas(base)[1]["curta"]
    assert ("nos dois anos" in curta) == mesmo_lider
    if mesmo_lider:
        assert curta.count(atv[2020].idxmax()) == 1


def test_q11_considera_margem_e_sinistralidade(base):
    q11 = A.respostas(base)[10]["resposta"]
    assert "Sinistr. Akad" in q11 and "Pares" in q11 and "Relevantes" in q11
    assert "De onde vem a diferença de margem" in q11


def test_decomposicao_fecha_com_a_margem(base):
    g = base[base["lob"] == "E&O"]
    c = A.componentes(g)
    assert 1 - c["sin"] - c["resseg"] - c["com"] == pytest.approx(c["margem"])


@pytest.mark.parametrize(
    "lobs,ini,fim",
    [
        (["RCG"], 2020, 2025),
        (A.LOB_ORDEM, 2025, 2025),
        (A.LOB_ORDEM, 2020, 2021),
        (["Transportes", "Garantia"], 2022, 2025),
        (["E&O"], 2021, 2024),
    ],
)
def test_filtros_nao_quebram(base, lobs, ini, fim):
    sub = A.filtrar(base, lobs, ini, fim)
    _sem_lixo(A.respostas(sub))


def test_q4_legenda_acompanha_o_corte(base):
    assert "1%" in R.q4_curta(base, 0.01)
    assert "3%" in R.q4_curta(base, 0.03)


def test_nome_curto():
    assert A.nome_curto("TOKIO MARINE SEGURADORA S.A.") == "Tokio Marine"
    assert A.nome_curto("BTG PACTUAL SEGUROS S.A.") == "BTG Pactual"
    assert A.nome_curto("PORTO SEGURO COMPANHIA DE SEGUROS GERAIS") == "Porto"


def test_perguntas_literais_do_pdf(base):
    for q in R.gerar(base):
        assert q["pergunta"] == R.PERGUNTAS[q["n"]]


def test_sem_exclamacao(base):
    for q in R.gerar(base):
        assert "!" not in q["resposta"] and "!" not in q["curta"]


def test_curta_concisa(base):
    for q in R.gerar(base):
        assert len(q["curta"].split()) <= 40, (q["n"], len(q["curta"].split()))


def test_filtro_uma_lob_nao_quebra(base):
    for lob in base["lob"].unique():
        assert len(R.gerar(base[base["lob"] == lob])) == 12


def test_filtro_um_ano_nao_quebra(base):
    ano = int(base["ano"].max())
    assert len(R.gerar(base[base["ano"] == ano])) == 12


def test_sem_texto_de_maquina(base):
    proibidos = ("estrela", "raio-X", "raio x", "indispensável", "nunca usamos", "para antecipar")
    for q in R.gerar(base):
        baixo = q["resposta"].lower()
        for p in proibidos:
            assert p not in baixo, (q["n"], p)


def test_sem_topicos_nem_abreviacoes_fora_das_tabelas(base):
    abreviacoes = re.compile(r"\b(bi|mi|pp)\b")
    for q in R.gerar(base):
        for linha in q["resposta"].splitlines():
            texto = linha.strip()
            if not texto or texto.startswith("|") or texto.startswith("_"):
                continue
            assert not texto.startswith("- "), (q["n"], texto[:60])
            assert not abreviacoes.search(texto), (q["n"], abreviacoes.search(texto).group(0), texto[:60])


def test_primeira_frase_tem_sujeito_e_verbo(base):
    for q in R.gerar(base):
        primeira = q["curta"].strip()
        assert primeira[:1].isupper(), (q["n"], primeira[:40])
        assert any(v in primeira.lower() for v in (" é ", " tem ", " foram ", " somaram ", " lidera ", " ficou ", " passou ", " cresceu ", " deveria ")), (q["n"], primeira[:60])
