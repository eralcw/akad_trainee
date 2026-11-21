"""Testes offline: nenhum acesso a rede. Usam HTML sintetico no formato do SES."""

from __future__ import annotations

import json

import pytest
import yaml

from ses import publish
from ses.config import Config, Consulta
from ses.extract import _vazio, gravar_raw, pendentes
from ses.transform import agregar, construir_base, decodificar, ler_tabela, para_numero
from ses.validate import validar

CABECALHO = (
    "Código SUSEP|Empresa|Prêmio Direto ¹|Prêmio Ganho ¹|Despesa com Resseguro ³|"
    "Sinistro Ocorrido ³|Receita com Resseguro ³|Despesa Comercial|Sinistralidade ¹|RVNE ³"
).split("|")


def br(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def html_ses(linhas, ramo="0351", ini="202001", fim="202012", totais=None):
    """linhas: (codigo, nome, premio_ganho, sinistro, desp_res, rec_res, desp_com)."""
    def tr(celulas):
        return "<tr>" + "".join(f"<td>{c}</td>" for c in celulas) + "</tr>"

    corpo = [
        tr([cod, nome, br(pg), br(pg), br(dr), br(so), br(rr), br(dc),
            f"{so / pg:.2f}".replace(".", ","), "0,00"])
        for cod, nome, pg, so, dr, rr, dc in linhas
    ]
    soma = lambda i: sum(l[i] for l in linhas)
    t = totais or {2: soma(2), 3: soma(3), 4: soma(4), 5: soma(5), 6: soma(6)}
    total = tr(["&nbsp;", "Totais", br(t[2]), br(t[2]), br(t[4]), br(t[3]), br(t[5]), br(t[6]), "", ""])
    return (
        "<html><body><table><tr><td><table>"
        + "<tr>" + "".join(f"<th>{c}</th>" for c in CABECALHO) + "</tr>"
        + "".join(corpo) + total
        + f"</table></td></tr></table><table><tr><td>Ramos selecionados </td><td>{ramo}</td>"
        f"<td>Período de</td><td>{ini}</td><td>Período até</td><td>{fim}</td></tr></table>"
        "</body></html>"
    )


def html_vazio(ramo="0351", ini="202001", fim="202012"):
    """Pagina do SES sem tabela de resultado (ramo sem dados no periodo)."""
    return (
        "<html><body><table><tr><td>Sem dados para os parametros informados</td></tr></table>"
        f"<table><tr><td>Ramos selecionados </td><td>{ramo}</td>"
        f"<td>Período de</td><td>{ini}</td><td>Período até</td><td>{fim}</td></tr></table>"
        "</body></html>"
    )


LINHAS = [
    ("02798", "AKAD SEGUROS S.A.", 100_000_000, 45_000_000, 9_000_000, 13_000_000, 22_000_000),
    ("06190", "TOKIO MARINE SEGURADORA S.A.", 800_000_000, 320_000_000, 100_000_000, 60_000_000, 150_000_000),
]


@pytest.fixture
def cfg(tmp_path):
    dados = {
        "fonte": {"url": "http://exemplo", "consulta": "x", "agrupamento": "Empresa"},
        "periodo": {"ano_inicio": 2024, "ano_fim": 2025},
        "lobs": {"RCG": ["0351"], "Garantia": ["0775", "0776"]},
        "akad": {"codigo_susep": "02798", "nome": "AKAD"},
        "atualizacao": {"reextrair_anos": [], "pausa_entre_consultas_s": 0, "tentativas": 1},
        "contrato": {
            "tolerancia_totais": 0.0005,
            "colunas_obrigatorias": ["premio_ganho", "sinistro_ocorrido"],
            "max_consultas_vazias": 0,
        },
        "pastas": {
            "raw": str(tmp_path / "raw"),
            "snapshots": str(tmp_path / "snap"),
            "runs": str(tmp_path / "runs"),
        },
    }
    caminho = tmp_path / "config.yaml"
    caminho.write_text(yaml.safe_dump(dados), encoding="utf-8")
    return Config(caminho)


def popular_raw(cfg, escala=1.0, **kw):
    for c in cfg.consultas:
        linhas = [(a, b, int(pg * escala), int(so * escala), dr, rr, dc)
                  for a, b, pg, so, dr, rr, dc in LINHAS]
        ini, fim = c.periodo
        conteudo = html_ses(linhas, ramo=c.ramo, ini=ini, fim=fim, **kw).encode("utf-8")
        gravar_raw(cfg, c, conteudo, "export_xls", "Empresa")


def test_para_numero_pt_br():
    assert para_numero("9.705.565.371") == 9705565371.0
    assert para_numero("0,46") == 0.46
    assert para_numero("1.234") == 1234.0   # nao pode virar 1,234
    assert para_numero("") is None


def test_ler_tabela_e_totais():
    t = ler_tabela(decodificar(html_ses(LINHAS).encode("utf-8")))
    assert len(t.corpo) == 2
    assert t.corpo.loc[0, "codigo_susep"] == "02798"
    assert t.corpo.loc[0, "sinistralidade_susep"] == 0.45
    assert t.totais["premio_ganho"] == 900_000_000
    assert t.rodape == (["0351"], "202001", "202012")


def test_rodape_desescapa_entidades_do_xls():
    bruto = html_ses(LINHAS).replace("Período", "Per&iacute;odo")
    assert ler_tabela(bruto).rodape == (["0351"], "202001", "202012")


def test_detecta_consulta_vazia():
    c = Consulta("RCG", "0351", 2024)
    assert _vazio(html_vazio("0351", "202401", "202412").encode(), c)
    assert not _vazio(html_vazio("0999", "202401", "202412").encode(), c)
    assert not _vazio(html_ses(LINHAS, "0351", "202401", "202412").encode(), c)


def test_consulta_vazia_nao_reprova(cfg):
    popular_raw(cfg)
    c = next(c for c in cfg.consultas if c.ramo == "0776" and c.ano == 2024)
    gravar_raw(cfg, c, html_vazio(c.ramo, *c.periodo).encode("utf-8"), "vazio", "Empresa")
    cfg.dados["contrato"]["max_consultas_vazias"] = 1
    base, diag = construir_base(cfg)
    rel = validar(cfg, base, diag)
    assert rel["aprovado"], rel["erros"]
    assert rel["cobertura"]["vazias"] == 1


def test_decodifica_cp1252():
    texto = html_ses(LINHAS).encode("cp1252")
    assert ler_tabela(decodificar(texto)).corpo["seguradora"].iloc[1].startswith("TOKIO")


def test_agregar_soma_antes_de_dividir():
    t = ler_tabela(html_ses(LINHAS))
    base = t.corpo.assign(lob="RCG", ramo_codigo="0351", ano=2024)
    ag = agregar(base, ["lob"])
    esperado = (45_000_000 + 320_000_000) / (100_000_000 + 800_000_000)
    assert ag.loc[0, "sinistralidade"] == pytest.approx(esperado)
    lucro = 900e6 + 73e6 - 365e6 - 109e6 - 172e6
    assert ag.loc[0, "lucro"] == pytest.approx(lucro)
    assert ag.loc[0, "margem"] == pytest.approx(lucro / 900e6)


def test_pendentes_pula_o_que_ja_existe(cfg):
    coletar, pular = pendentes(cfg)
    assert len(coletar) == 6 and not pular
    popular_raw(cfg)
    coletar, pular = pendentes(cfg)
    assert not coletar and len(pular) == 6
    assert len(pendentes(cfg, forcar=True)[0]) == 6
    assert len(pendentes(cfg, anos=[2025], forcar=True)[0]) == 3


def test_pipeline_offline_publica_e_nao_republica(cfg):
    popular_raw(cfg)
    base, diag = construir_base(cfg)
    rel = validar(cfg, base, diag)
    assert rel["aprovado"], rel["erros"]
    assert rel["cobertura"] == {"esperadas": 6, "lidas": 6, "vazias": 0, "totais_conferidos": 6}

    r1 = publish.publicar(cfg, base, rel)
    assert r1["publicado"] and publish.atual(cfg) == r1["snapshot"]
    assert len(publish.carregar_base(cfg)) == 12

    base2, diag2 = construir_base(cfg)
    r2 = publish.publicar(cfg, base2, validar(cfg, base2, diag2))
    assert not r2["publicado"]          # base identica: nao cria snapshot


def test_retificacao_gera_diff_e_rollback(cfg):
    popular_raw(cfg)
    base, diag = construir_base(cfg)
    s1 = publish.publicar(cfg, base, validar(cfg, base, diag))["snapshot"]

    # SUSEP retifica: premio do RCG/2025 sobe 10% (coleta nova, raw antigo preservado)
    for c in cfg.consultas:
        if c.ramo == "0351" and c.ano == 2025:
            linhas = [(a, b, int(pg * 1.1), so, dr, rr, dc) for a, b, pg, so, dr, rr, dc in LINHAS]
            gravar_raw(cfg, c, html_ses(linhas, "0351", *c.periodo).encode("utf-8"), "export_xls", "Empresa")

    base2, diag2 = construir_base(cfg)
    rel2 = validar(cfg, base2, diag2)
    assert rel2["aprovado"], rel2["erros"]
    r = publish.publicar(cfg, base2, rel2)
    assert r["publicado"]
    assert r["diff"]["linhas_alteradas"] == 2
    assert r["diff"]["delta_premio_ganho_por_lob"]["RCG"] == pytest.approx(90_000_000)

    assert publish.rollback(cfg) == s1
    assert publish.atual(cfg) == s1


def test_contrato_reprova_total_que_nao_bate(cfg):
    popular_raw(cfg, totais={2: 1, 3: 1, 4: 1, 5: 1, 6: 1})
    base, diag = construir_base(cfg)
    rel = validar(cfg, base, diag)
    assert not rel["aprovado"]
    assert any("Totais" in e for e in rel["erros"])
    with pytest.raises(RuntimeError):
        publish.publicar(cfg, base, rel)
    assert publish.atual(cfg) is None   # nada foi promovido


def test_contrato_reprova_cobertura_incompleta(cfg):
    popular_raw(cfg)
    manifesto = cfg.raw / "manifest.jsonl"
    linhas = manifesto.read_text(encoding="utf-8").splitlines()
    manifesto.write_text("\n".join(linhas[:-1]) + "\n", encoding="utf-8")  # perde 1 consulta
    base, diag = construir_base(cfg)
    rel = validar(cfg, base, diag)
    assert not rel["aprovado"]
    assert any("nao coletada" in e for e in rel["erros"])


def test_hash_detecta_raw_adulterado(cfg):
    popular_raw(cfg)
    primeiro = json.loads((cfg.raw / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[0])
    arq = cfg.raw / primeiro["arquivo"]
    arq.write_bytes(arq.read_bytes().replace(b"100.000.000", b"999.000.000"))
    base, diag = construir_base(cfg)
    rel = validar(cfg, base, diag)
    assert not rel["aprovado"]
    assert any("SHA-256" in e for e in rel["erros"])


def test_rodape_divergente_reprova(cfg):
    for c in cfg.consultas:
        gravar_raw(cfg, c, html_ses(LINHAS, "0999", *c.periodo).encode("utf-8"), "export_xls", "Empresa")
    base, diag = construir_base(cfg)
    assert not validar(cfg, base, diag)["aprovado"]
