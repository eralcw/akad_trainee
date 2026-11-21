"""Tratamento: raw (HTML/.xls do SES) -> base longa em pandas.

Regras de metodo (iguais as do case):
  sinistralidade = sinistro_ocorrido / premio_ganho   (razao de somas, nunca media de razoes)
  lucro  = premio_ganho + receita_resseguro
           - sinistro_ocorrido - despesa_resseguro - despesa_comercial
  margem = lucro / premio_ganho

O parser le a tabela do SES como TEXTO (lxml) e converte o formato pt-BR por
conta propria. Nao usa pandas.read_html de proposito: ele interpreta
'0,46' como 46 e '1.234' como 1,234.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from lxml import html as lxml_html

from .config import Config, Consulta

# titulo da coluna no SES (sem sobrescrito) -> nome na base
COLUNAS_SES = {
    "Código SUSEP": "codigo_susep",
    "Empresa": "seguradora",
    "Prêmio Ganho": "premio_ganho",
    "Sinistro Ocorrido": "sinistro_ocorrido",
    "Despesa com Resseguro": "despesa_resseguro",
    "Receita com Resseguro": "receita_resseguro",
    "Despesa Comercial": "despesa_comercial",
    "Sinistralidade": "sinistralidade_susep",
}
COLUNAS_VALOR = [
    "premio_ganho", "sinistro_ocorrido", "despesa_resseguro",
    "receita_resseguro", "despesa_comercial",
]
COLUNAS_BASE = [
    "lob", "ramo_codigo", "ano", "codigo_susep", "seguradora",
    *COLUNAS_VALOR, "sinistralidade_susep",
    "sinistralidade", "lucro", "margem",
    "raw_arquivo", "raw_sha256",
]
COLUNAS_BASE_PERIODO = [
    *COLUNAS_BASE,
    "periodo_ini", "periodo_fim", "meses", "parcial",
]


# --------------------------------------------------------------------------
# Utilitarios
# --------------------------------------------------------------------------

def sha256_bytes(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def decodificar(conteudo: bytes) -> str:
    """O SES devolve UTF-8 ou Windows-1252 dependendo da tela."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return conteudo.decode(enc)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("utf-8", errors="replace")


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def _limpar_titulo(texto: str) -> str:
    texto = re.sub(r"\s+", " ", texto.replace("\xa0", " ")).strip()
    return re.sub(r"\s*[¹²³]+\s*$", "", texto).strip()


def para_numero(valor) -> float | None:
    """'9.705.565.371' -> 9705565371.0 ; '0,46' -> 0.46 ; '' -> None."""
    if valor is None:
        return None
    texto = str(valor).replace("\xa0", "").replace(" ", "").strip()
    if not texto or texto in {"-", "—"}:
        return None
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Leitura de um arquivo do SES
# --------------------------------------------------------------------------

@dataclass
class TabelaSES:
    corpo: pd.DataFrame                      # uma linha por seguradora (numeros em float)
    totais: dict[str, float | None]          # linha "Totais" oficial do SES
    rodape: tuple[list[str], str, str] | None  # (ramos, periodo_ini, periodo_fim)


def metadados_rodape(texto_html: str):
    """Rodape do SES: 'Ramos selecionados 0351 Periodo de 202001 Periodo ate 202012'."""
    texto = re.sub(r"<[^>]+>", " ", texto_html)
    # o .xls exportado vem com acentos escapados ("Per&iacute;odo")
    texto = html_lib.unescape(texto).replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    m = re.search(
        r"Ramos selecionados\s+([\d,\s]+?)\s+Per[ií]odo de\s+(\d{6})\s+Per[ií]odo at[eé]\s+(\d{6})",
        texto,
    )
    if not m:
        return None
    ramos = [r.strip() for r in m.group(1).split(",") if r.strip()]
    return ramos, m.group(2), m.group(3)


def ler_tabela(texto_html: str) -> TabelaSES:
    """Extrai a tabela de resultado do SES. Levanta ValueError se nao achar."""
    arvore = lxml_html.fromstring(texto_html)

    for tabela in arvore.iter("table"):
        linhas = tabela.xpath(".//tr[not(.//table)]")  # ignora tabelas externas de layout
        cabecalho_idx = None
        cabecalho: list[str] = []
        for i, tr in enumerate(linhas):
            textos = [_limpar_titulo(c.text_content()) for c in tr.xpath("./th|./td")]
            if "Empresa" in textos and "Prêmio Ganho" in textos:
                cabecalho_idx, cabecalho = i, textos
                break
        if cabecalho_idx is None:
            continue

        faltando = [c for c in COLUNAS_SES if c not in cabecalho]
        if faltando:
            raise ValueError(f"colunas ausentes no SES: {faltando}")

        indice = {nome: cabecalho.index(nome) for nome in COLUNAS_SES}
        registros, totais = [], {}
        for tr in linhas[cabecalho_idx + 1:]:
            celulas = [c.text_content().replace("\xa0", " ").strip() for c in tr.xpath("./th|./td")]
            if len(celulas) != len(cabecalho):
                continue
            nome_empresa = celulas[indice["Empresa"]]
            if nome_empresa == "Totais":
                totais = {
                    COLUNAS_SES[n]: para_numero(celulas[i])
                    for n, i in indice.items()
                    if COLUNAS_SES[n] in COLUNAS_VALOR
                }
                continue
            if not nome_empresa:
                continue
            reg = {COLUNAS_SES[n]: celulas[i] for n, i in indice.items()}
            registros.append(reg)

        corpo = pd.DataFrame(registros, columns=list(COLUNAS_SES.values()))
        for col in [*COLUNAS_VALOR, "sinistralidade_susep"]:
            corpo[col] = corpo[col].map(para_numero)
        corpo["codigo_susep"] = corpo["codigo_susep"].str.strip().str.zfill(5)
        return TabelaSES(corpo=corpo, totais=totais, rodape=metadados_rodape(texto_html))

    raise ValueError("tabela de resultado do SES nao encontrada")


def adicionar_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """Sinistralidade, lucro e margem linha a linha (denominador <= 0 -> NaN)."""
    df = df.copy()
    base_ok = df["premio_ganho"] > 0
    df["sinistralidade"] = (df["sinistro_ocorrido"] / df["premio_ganho"]).where(base_ok)
    df["lucro"] = (
        df["premio_ganho"] + df["receita_resseguro"]
        - df["sinistro_ocorrido"] - df["despesa_resseguro"] - df["despesa_comercial"]
    )
    df["margem"] = (df["lucro"] / df["premio_ganho"]).where(base_ok)
    return df


def agregar(df: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Agrega SOMANDO os valores e so depois dividindo (nunca media de percentuais)."""
    soma = df.groupby(por, as_index=False)[COLUNAS_VALOR].sum()
    return adicionar_metricas(soma)


# --------------------------------------------------------------------------
# Construcao da base a partir do manifesto
# --------------------------------------------------------------------------

@dataclass
class Diagnostico:
    chave: str
    arquivo: str | None
    fonte: str | None = None
    erro: str | None = None
    hash_ok: bool = True
    n_seguradoras: int = 0
    totais: dict[str, dict] = field(default_factory=dict)
    rodape_ok: bool | None = None  # None = rodape ausente no arquivo (ex.: .xls)

    def a_dict(self) -> dict:
        return self.__dict__.copy()


def ler_manifesto(raw_dir: Path) -> list[dict]:
    caminho = raw_dir / "manifest.jsonl"
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def ultimas_entradas(manifesto: list[dict]) -> dict[str, dict]:
    """Ultima coleta bem-sucedida de cada consulta.

    Usa a chave gravada no manifesto; entradas antigas, sem `chave`, caem no
    formato historico ramo_ano.
    """
    ultimas: dict[str, dict] = {}
    for e in manifesto:
        if e.get("tipo") == "consulta" and e.get("status") == "ok":
            chave = e.get("chave") or f"{e['ramo']}_{e['ano']}"
            ultimas[chave] = e
    return ultimas


def _conferir_totais(corpo: pd.DataFrame, totais: dict, tolerancia: float) -> dict[str, dict]:
    n = max(len(corpo), 1)
    resultado = {}
    for col in COLUNAS_VALOR:
        oficial = totais.get(col)
        if oficial is None:
            continue
        soma = float(corpo[col].fillna(0).sum())
        dif = abs(soma - oficial)
        # cada linha foi arredondada para o real: aceita ate n reais de arrasto
        ok = dif <= max(tolerancia * abs(oficial), n)
        resultado[col] = {"soma": soma, "oficial": oficial, "dif": dif, "ok": ok}
    return resultado


def construir_base(cfg: Config) -> tuple[pd.DataFrame, list[Diagnostico]]:
    """Le o raw/ (sem rede!) e devolve (base, diagnosticos por consulta)."""
    ultimas = ultimas_entradas(ler_manifesto(cfg.raw))
    tol = cfg.contrato["tolerancia_totais"]

    pedacos: list[pd.DataFrame] = []
    diagnosticos: list[Diagnostico] = []

    for c in cfg.consultas:
        entrada = ultimas.get(c.chave)
        if entrada is None:
            diagnosticos.append(Diagnostico(c.chave, None, erro="consulta nao coletada"))
            continue

        caminho = cfg.raw / entrada["arquivo"]
        diag = Diagnostico(c.chave, entrada["arquivo"], fonte=entrada.get("fonte"))
        diagnosticos.append(diag)

        if not caminho.exists():
            diag.erro = "arquivo raw ausente"
            continue
        if sha256_arquivo(caminho) != entrada["sha256"]:
            diag.hash_ok = False
            diag.erro = "SHA-256 diverge do manifesto (raw alterado)"
            continue

        if entrada.get("fonte") == "vazio":
            rodape = metadados_rodape(decodificar(caminho.read_bytes()))
            diag.rodape_ok = (
                rodape is not None
                and rodape[0] == [c.ramo]
                and (rodape[1], rodape[2]) == c.periodo
            )
            if not diag.rodape_ok:
                diag.erro = "consulta vazia sem rodape coerente com o pedido"
            continue

        try:
            tabela = ler_tabela(decodificar(caminho.read_bytes()))
        except ValueError as e:
            diag.erro = str(e)
            continue

        diag.n_seguradoras = len(tabela.corpo)
        diag.totais = _conferir_totais(tabela.corpo, tabela.totais, tol)
        if tabela.rodape is not None:
            ramos, ini, fim = tabela.rodape
            diag.rodape_ok = ramos == [c.ramo] and (ini, fim) == c.periodo

        if tabela.corpo.empty:
            continue
        corpo = tabela.corpo.assign(
            lob=c.lob, ramo_codigo=c.ramo, ano=c.ano,
            raw_arquivo=entrada["arquivo"], raw_sha256=entrada["sha256"][:12],
        )
        pedacos.append(adicionar_metricas(corpo))

    if pedacos:
        base = pd.concat(pedacos, ignore_index=True)[COLUNAS_BASE]
        base = base.sort_values(["lob", "ano", "premio_ganho"], ascending=[True, True, False])
        base = base.reset_index(drop=True)
    else:
        base = pd.DataFrame(columns=COLUNAS_BASE)
    return base, diagnosticos


def construir_periodo(
    cfg: Config,
    consultas: list[Consulta],
) -> tuple[pd.DataFrame, list[Diagnostico]]:
    """Le o raw de periodos parciais e devolve (base parcial, diagnosticos).

    Nao toca no snapshot anual: os arquivos ficam em data/raw/periodos e a
    base carrega periodo_ini, periodo_fim, meses e parcial.
    """
    ultimas = ultimas_entradas(ler_manifesto(cfg.raw_periodos))
    tol = cfg.contrato["tolerancia_totais"]

    pedacos: list[pd.DataFrame] = []
    diagnosticos: list[Diagnostico] = []

    for c in consultas:
        entrada = ultimas.get(c.chave)
        if entrada is None:
            diagnosticos.append(Diagnostico(c.chave, None, erro="consulta nao coletada"))
            continue

        caminho = cfg.raw_periodos / entrada["arquivo"]
        diag = Diagnostico(c.chave, entrada["arquivo"], fonte=entrada.get("fonte"))
        diagnosticos.append(diag)

        if not caminho.exists():
            diag.erro = "arquivo raw ausente"
            continue
        if sha256_arquivo(caminho) != entrada["sha256"]:
            diag.hash_ok = False
            diag.erro = "SHA-256 diverge do manifesto (raw alterado)"
            continue

        if entrada.get("fonte") == "vazio":
            rodape = metadados_rodape(decodificar(caminho.read_bytes()))
            diag.rodape_ok = (
                rodape is not None
                and rodape[0] == [c.ramo]
                and (rodape[1], rodape[2]) == c.periodo
            )
            if not diag.rodape_ok:
                diag.erro = "consulta vazia sem rodape coerente com o pedido"
            continue

        try:
            tabela = ler_tabela(decodificar(caminho.read_bytes()))
        except ValueError as e:
            diag.erro = str(e)
            continue

        diag.n_seguradoras = len(tabela.corpo)
        diag.totais = _conferir_totais(tabela.corpo, tabela.totais, tol)
        if tabela.rodape is not None:
            ramos, ini, fim = tabela.rodape
            diag.rodape_ok = ramos == [c.ramo] and (ini, fim) == c.periodo

        if tabela.corpo.empty:
            continue
        corpo = tabela.corpo.assign(
            lob=c.lob,
            ramo_codigo=c.ramo,
            ano=c.ano,
            periodo_ini=c.periodo[0],
            periodo_fim=c.periodo[1],
            meses=c.meses,
            parcial=not c.completo,
            raw_arquivo=entrada["arquivo"],
            raw_sha256=entrada["sha256"][:12],
        )
        pedacos.append(adicionar_metricas(corpo))

    if pedacos:
        base = pd.concat(pedacos, ignore_index=True)[COLUNAS_BASE_PERIODO]
        base = base.sort_values(
            ["lob", "ano", "premio_ganho"], ascending=[True, True, False]
        ).reset_index(drop=True)
    else:
        base = pd.DataFrame(columns=COLUNAS_BASE_PERIODO)
    return base, diagnosticos
