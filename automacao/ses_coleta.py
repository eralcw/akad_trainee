#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coleta de dados do SES/SUSEP - Case Trainee Akad Seguros 2027
=============================================================

O SES entrega uma combinacao de ramo e periodo por consulta. Este script
automatiza o formulario para montar a serie 2020-2025 dos 13 codigos de ramo
do case e, opcionalmente, baixa a base completa publicada pela SUSEP.

Instalacao (uma vez):
    pip install playwright
    playwright install chromium

Uso:
    python ses_coleta.py descobrir          # 1 consulta de teste + diagnostico
    python ses_coleta.py coletar            # os 13 ramos, retomando de onde parou
    python ses_coleta.py base "<URL>"       # baixa a Base de Dados do SES

O que fica em disco:
    raw/         respostas brutas (HTML, prints) + manifest.jsonl
    processed/   preenchido depois, pelo tratamento
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    sys.exit(
        "Playwright nao instalado.\n"
        "  pip install playwright\n"
        "  playwright install chromium"
    )

# --------------------------------------------------------------------------
# Parametros do case
# --------------------------------------------------------------------------

URL_PRINCIPAL = "https://www2.susep.gov.br/menuestatistica/ses/principal.aspx"

# Nome da consulta no dropdown "Operacoes". Comparado sem acento (ver normalizar),
# entao escrever "Premios" aqui encontra "Premios" com ou sem circunflexo.
CONSULTA = "Seguros: Premios e Sinistros"

ANO_INICIO = 2020
ANO_FIM = 2025

# O SES devolve o periodo inteiro somado numa linha por empresa: nao existe
# quebra por ano na resposta. Por isso a coleta e ano a ano,
# 13 ramos x 6 anos = 78 consultas.
PERIODOS = [(str(a), f"{a}01", f"{a}12") for a in range(ANO_INICIO, ANO_FIM + 1)]

LOBS = {
    "RCG": ["0351"],
    "E&O": ["0378"],
    "Empresarial": ["0118"],
    "Transportes": ["0654", "0655", "0644", "0621", "0632", "0622", "0652", "0656", "0645"],
    "Garantia": ["0775", "0776"],
}

BASE_DIR = Path(__file__).resolve().parent
RAW = BASE_DIR / "raw"
RAW.mkdir(exist_ok=True)
MANIFEST = RAW / "manifest.jsonl"


# --------------------------------------------------------------------------
# Utilitarios
# --------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Minusculo, sem acento, sem espaco sobrando - para comparar rotulos."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def registrar(evento: dict) -> None:
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def nome_arquivo(codigo_ramo: str, ano: str) -> str:
    return f"empresa_ramo{codigo_ramo}_{ano}.html"


def opcoes_do_select(select_handle):
    """Lista [{v, t}] de um <select>, ou None se nao for um select legivel."""
    try:
        return select_handle.evaluate(
            "el => Array.from(el.options).map(o => ({v: o.value, t: o.text.trim()}))"
        )
    except Exception:
        return None


def clicar(page, texto: str) -> bool:
    """Clica no botao/link cujo texto ou value contenha `texto`."""
    candidatos = [
        page.locator(f"input[type=submit][value*='{texto}' i], input[type=button][value*='{texto}' i]"),
        page.get_by_role("button", name=re.compile(re.escape(texto), re.I)),
        page.locator("a").filter(has_text=re.compile(re.escape(texto), re.I)),
    ]
    for loc in candidatos:
        try:
            if loc.count() > 0:
                loc.first.click()
                return True
        except Exception:
            continue
    return False


def esperar_tela_consulta(page) -> None:
    """Espera a tela que tem as listas de Empresas e Ramos."""
    page.wait_for_function(
        """() => {
            const selects = [...document.querySelectorAll('select')];
            const temEmpresas = selects.some(s => [...s.options].some(o => o.text.trim() === 'Todas'));
            const temRamos    = selects.some(s => [...s.options].some(o => o.text.trim() === 'Todos'));
            return temEmpresas && temRamos;
        }""",
        timeout=90000,
    )


# --------------------------------------------------------------------------
# Navegacao no SES
# --------------------------------------------------------------------------

def abrir_consulta(page) -> None:
    log("Abrindo o SES...")
    page.goto(URL_PRINCIPAL, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(1500)

    alvo, valor = None, None
    alvo_normalizado = normalizar(CONSULTA)
    for i in range(page.locator("select").count()):
        s = page.locator("select").nth(i)
        opcoes = opcoes_do_select(s)
        if not opcoes:
            continue
        # 1o: igualdade exata - garante a versao nacional, nao a "( UF )"
        encontrada = next(
            (o for o in opcoes if normalizar(o["t"]) == alvo_normalizado), None
        )
        # 2o: se nao houver exata, aceita a que contem o nome
        if encontrada is None:
            encontrada = next(
                (o for o in opcoes if alvo_normalizado in normalizar(o["t"])), None
            )
        if encontrada:
            alvo, valor = s, encontrada["v"]
            break

    if alvo is None:
        raise RuntimeError(
            "Nao encontrei a consulta no dropdown. A lista pode ter mudado de nome."
        )

    alvo.select_option(valor)
    if not clicar(page, "Ir para a consulta"):
        raise RuntimeError("Nao encontrei o botao 'Ir para a consulta'.")

    esperar_tela_consulta(page)
    log("Tela de consulta aberta.")


def preencher(page, ramos, inicio: str, fim: str, agrupamento: str = "Empresa"):
    """Preenche e processa. Devolve a pagina com o resultado."""
    if normalizar(agrupamento).startswith("mes"):
        agrupamento = "Mês"

    sel_emp = sel_ramo = None
    for i in range(page.locator("select").count()):
        s = page.locator("select").nth(i)
        opcoes = opcoes_do_select(s)
        if not opcoes:
            continue
        textos = [o["t"] for o in opcoes]
        if "Todas" in textos:
            sel_emp = s
        elif "Todos" in textos:
            sel_ramo = s

    if sel_emp is None or sel_ramo is None:
        raise RuntimeError("Nao identifiquei as listas de Empresas e Ramos.")

    # Empresas: seleciona "Todas"
    v_emp = sel_emp.evaluate(
        "el => ([...el.options].find(o => o.text.trim() === 'Todas') || {}).value"
    )
    sel_emp.select_option([v_emp])

    # Ramos: seleciona pelos codigos do case
    opcoes = opcoes_do_select(sel_ramo) or []
    valores = []
    for codigo in ramos:
        achados = [o["v"] for o in opcoes if o["t"].startswith(codigo)]
        if not achados:
            log(f"  aviso: codigo {codigo} nao aparece na lista de ramos")
        valores.extend(achados)
    if not valores:
        raise RuntimeError(f"Nenhum ramo selecionado para {ramos}.")
    sel_ramo.select_option(valores)

    # Periodo: os dois campos AAAAMM
    campos = page.locator("input[maxlength='6']")
    if campos.count() < 2:
        campos = page.locator("input[type=text]:visible")
    if campos.count() < 2:
        raise RuntimeError("Nao encontrei os campos de periodo.")
    campos.nth(0).fill(inicio)
    campos.nth(1).fill(fim)

    # Agrupamento
    try:
        page.get_by_text(
            re.compile(rf"Agrupar por\s+{re.escape(agrupamento)}", re.I)
        ).first.click()
    except Exception:
        idx = {"Empresa": 0, "Ramo": 1, "Mês": 2}.get(agrupamento, 0)
        page.locator("input[type=radio]").nth(idx).check()

    antes = list(page.context.pages)
    if not clicar(page, "Processar"):
        raise RuntimeError("Nao encontrei o botao 'Processar'.")

    page.wait_for_timeout(1500)
    novas = [p for p in page.context.pages if p not in antes]
    if novas:
        page = novas[0]
    page.wait_for_load_state("networkidle", timeout=120000)
    page.wait_for_timeout(2000)
    return page


def diagnosticar(page) -> dict:
    return page.evaluate(
        """() => {
            const tabelas = [...document.querySelectorAll('table')].map((t, i) => ({
                i,
                linhas: t.rows.length,
                colunas: t.rows.length ? t.rows[0].cells.length : 0,
                cabecalho: t.rows.length
                    ? [...t.rows[0].cells].map(c => c.innerText.trim().replace(/\\s+/g, ' ')).slice(0, 25)
                    : []
            }));
            const exportacao = [...document.querySelectorAll('a, input[type=submit], input[type=button]')]
                .map(e => (e.innerText || e.value || '').trim())
                .filter(t => /excel|xls|csv|export|download|arquivo/i.test(t));
            return { tabelas, exportacao: [...new Set(exportacao)] };
        }"""
    )


# --------------------------------------------------------------------------
# Modos
# --------------------------------------------------------------------------

def modo_descobrir(args) -> None:
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(ignore_https_errors=True, accept_downloads=True)
        page = ctx.new_page()

        abrir_consulta(page)
        ano, inicio, fim = PERIODOS[0]
        page = preencher(page, LOBS["RCG"], inicio, fim, "Empresa")

        # salva com o nome definitivo: assim o modo `coletar` pula este arquivo
        html = RAW / nome_arquivo("0351", ano)
        html.write_text(page.content(), encoding="utf-8")
        png = RAW / f"descoberta_{carimbo}.png"
        page.screenshot(path=str(png), full_page=True)

        info = diagnosticar(page)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        registrar({
            "modo": "descobrir", "quando": carimbo,
            "html": html.name, "png": png.name, **info,
        })
        log(f"Salvo: {html.name} e {png.name}")
        browser.close()


def modo_coletar(args) -> None:
    alvos = [
        (lob, codigo, ano, inicio, fim)
        for lob, codigos in LOBS.items()
        for codigo in codigos
        for ano, inicio, fim in PERIODOS
    ]
    log(f"{len(alvos)} consultas previstas ({len(PERIODOS)} anos).")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(ignore_https_errors=True, accept_downloads=True)
        page = ctx.new_page()

        for lob, codigo, ano, inicio, fim in alvos:
            destino = RAW / nome_arquivo(codigo, ano)
            if destino.exists():
                log(f"{lob} {codigo} {ano}: ja existe, pulando.")
                continue

            for tentativa in range(1, 4):
                try:
                    log(f"{lob} {codigo} {ano}: tentativa {tentativa}...")
                    abrir_consulta(page)
                    page = preencher(page, [codigo], inicio, fim, args.agrupar)
                    destino.write_text(page.content(), encoding="utf-8")
                    registrar({
                        "modo": "coletar", "lob": lob, "ramo": codigo, "ano": ano,
                        "periodo": f"{inicio}-{fim}",
                        "agrupamento": args.agrupar,
                        "arquivo": destino.name,
                        "quando": datetime.now().isoformat(timespec="seconds"),
                    })
                    log(f"{lob} {codigo} {ano}: ok -> {destino.name}")
                    break
                except Exception as e:
                    log(f"{lob} {codigo} {ano}: falhou ({e})")
                    try:
                        page.screenshot(
                            path=str(RAW / f"erro_{codigo}_{ano}_{tentativa}.png"),
                            full_page=True,
                        )
                    except Exception:
                        pass
                    time.sleep(min(90, 5 * tentativa ** 2))
            else:
                log(f"{lob} {codigo} {ano}: desisti apos 3 tentativas.")

            time.sleep(args.pausa)

        browser.close()


def modo_base(args) -> None:
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    log("Baixando a base do SES...")
    req = urllib.request.Request(
        args.url, headers={"User-Agent": "Mozilla/5.0 (coleta academica)"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        nome = None
        cd = r.headers.get("Content-Disposition", "") or ""
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
        if m:
            nome = m.group(1).strip()
        if not nome:
            tipo = (r.headers.get("Content-Type") or "").lower()
            ext = ".zip" if "zip" in tipo else ".bin"
            nome = f"base_ses_{carimbo}{ext}"

        destino = RAW / nome
        with destino.open("wb") as f:
            shutil.copyfileobj(r, f, length=1024 * 256)

    tamanho = destino.stat().st_size / 1e6
    log(f"Salvo em {destino.name} ({tamanho:.1f} MB)")
    registrar({
        "modo": "base", "url": args.url, "arquivo": destino.name,
        "mb": round(tamanho, 1),
        "quando": datetime.now().isoformat(timespec="seconds"),
    })


# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Coleta SES/SUSEP - case Akad 2027")
    sub = p.add_subparsers(dest="modo", required=True)

    d = sub.add_parser("descobrir", help="uma consulta de teste + diagnostico da tabela")
    d.add_argument("--headless", action="store_true", help="rodar sem janela visivel")
    d.set_defaults(func=modo_descobrir)

    c = sub.add_parser("coletar", help="coleta os 13 codigos de ramo do case")
    c.add_argument("--headless", action="store_true")
    c.add_argument("--pausa", type=float, default=3.0, help="segundos entre consultas")
    c.add_argument("--agrupar", default="Empresa", choices=["Empresa", "Ramo", "Mês", "Mes"])
    c.set_defaults(func=modo_coletar)

    b = sub.add_parser("base", help="baixa a Base de Dados do SES")
    b.add_argument("url")
    b.set_defaults(func=modo_base)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
