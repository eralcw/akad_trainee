"""Extracao do SES/SUSEP com Playwright.

Rota A (principal): clica em "Exporta para Ms Excel" e guarda o .xls oficial
                    (por dentro e HTML) exatamente como a SUSEP entregou.
Rota B (fallback) : se a exportacao falhar, guarda o HTML da pagina renderizada.

Cada arquivo e gravado em data/raw/ de forma imutavel (nome com data/hora) e
registrado em data/raw/manifest.jsonl com SHA-256 e os parametros da consulta.
Nada aqui e necessario para reconstruir a base: ver `pipeline.py processar`.
"""

from __future__ import annotations

import json
import platform
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from .config import Config, Consulta
from .transform import (
    decodificar, ler_manifesto, ler_tabela, metadados_rodape,
    sha256_bytes, ultimas_entradas,
)


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def _normalizar(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem).strip().lower()


def _user_agent(browser) -> str:
    """UA de Chrome real: a WAF do SES devolve HTTP 500 para o UA padrao do Playwright."""
    sistema = {
        "Windows": "Windows NT 10.0; Win64; x64",
        "Darwin": "Macintosh; Intel Mac OS X 10_15_7",
    }.get(platform.system(), "X11; Linux x86_64")
    return (
        f"Mozilla/5.0 ({sistema}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{browser.version} Safari/537.36"
    )


# --------------------------------------------------------------------------
# Raw imutavel + manifesto
# --------------------------------------------------------------------------

def gravar_raw(
    cfg: Config,
    c: Consulta,
    conteudo: bytes,
    fonte: str,
    agrupamento: str,
    pasta: Path | None = None,
) -> dict:
    destino_dir = pasta or cfg.raw
    destino_dir.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    ext = "xls" if fonte == "export_xls" else "html"
    sufixo = "" if c.completo else f"_{c.mes_inicio:02d}{c.mes_fim:02d}"
    nome = f"ses_ramo{c.ramo}_{c.ano}{sufixo}_{agora:%Y%m%dT%H%M%S}.{ext}"
    destino = destino_dir / nome
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    tmp.write_bytes(conteudo)
    tmp.replace(destino)

    entrada = {
        "tipo": "consulta", "status": "ok",
        "chave": c.chave,
        "lob": c.lob, "ramo": c.ramo, "ano": c.ano,
        "periodo": f"{c.periodo[0]}-{c.periodo[1]}",
        "mes_inicio": c.mes_inicio, "mes_fim": c.mes_fim,
        "meses": c.meses, "parcial": not c.completo,
        "agrupamento": agrupamento,
        "fonte": fonte,
        "arquivo": nome,
        "bytes": len(conteudo),
        "sha256": sha256_bytes(conteudo),
        "quando": agora.isoformat(timespec="seconds"),
    }
    registrar(cfg, entrada, pasta=destino_dir)
    return entrada


def registrar(cfg: Config, evento: dict, pasta: Path | None = None) -> None:
    destino_dir = pasta or cfg.raw
    destino_dir.mkdir(parents=True, exist_ok=True)
    with (destino_dir / "manifest.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def pendentes(
    cfg: Config,
    forcar: bool = False,
    anos: list[int] | None = None,
    ramos: list[str] | None = None,
    consultas: list[Consulta] | None = None,
    pasta: Path | None = None,
) -> tuple[list[Consulta], list[Consulta]]:
    """Separa consultas (a coletar, a pular).

    Pula o que ja existe no raw, exceto anos em `atualizacao.reextrair_anos`
    (retificacoes recentes) ou quando `forcar=True`. Para periodo parcial,
    `pasta` aponta para data/raw/periodos e `consultas` traz o recorte.
    """
    destino = pasta or cfg.raw
    ultimas = ultimas_entradas(ler_manifesto(destino))
    reextrair = set(cfg.atualizacao.get("reextrair_anos") or [])
    coletar, pular = [], []
    for c in (consultas or cfg.consultas):
        if anos and c.ano not in anos:
            continue
        if ramos and c.ramo not in ramos:
            continue
        existente = ultimas.get(c.chave)
        ja_tem = existente is not None and (destino / existente["arquivo"]).exists()
        if ja_tem and not forcar and c.ano not in reextrair:
            pular.append(c)
        else:
            coletar.append(c)
    return coletar, pular


# --------------------------------------------------------------------------
# Navegacao no SES (formulario ASP.NET)
# --------------------------------------------------------------------------

def _opcoes(select) -> list[dict] | None:
    try:
        return select.evaluate(
            "el => Array.from(el.options).map(o => ({v: o.value, t: o.text.trim()}))"
        )
    except Exception:
        return None


def _clicar(page, texto: str) -> bool:
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


class BloqueioSES(RuntimeError):
    """O portal recusou o acesso (HTTP >= 400 ou pagina de bloqueio do firewall).

    Nao adianta insistir: a coleta para e o pipeline segue com o raw/ existente.
    """


def abrir_consulta(page, cfg: Config) -> None:
    resp = page.goto(cfg.url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(1500)
    titulo = _normalizar(page.title() or "")
    if (resp is not None and resp.status >= 400) or "blocked" in titulo:
        raise BloqueioSES(
            f"o SES recusou o acesso (HTTP {resp.status if resp else '?'}, titulo: {page.title()!r})"
        )

    alvo_norm = _normalizar(cfg.nome_consulta)
    alvo = valor = None
    for i in range(page.locator("select").count()):
        s = page.locator("select").nth(i)
        opcoes = _opcoes(s)
        if not opcoes:
            continue
        achada = next((o for o in opcoes if _normalizar(o["t"]) == alvo_norm), None)
        if achada is None:
            achada = next((o for o in opcoes if alvo_norm in _normalizar(o["t"])), None)
        if achada:
            alvo, valor = s, achada["v"]
            break
    if alvo is None:
        raise RuntimeError("consulta nao encontrada no dropdown (o SES pode ter mudado)")

    alvo.select_option(valor)
    if not _clicar(page, "Ir para a consulta"):
        raise RuntimeError("botao 'Ir para a consulta' nao encontrado")

    page.wait_for_function(
        """() => {
            const sels = [...document.querySelectorAll('select')];
            const tem = t => sels.some(s => [...s.options].some(o => o.text.trim() === t));
            return tem('Todas') && tem('Todos');
        }""",
        timeout=90000,
    )


def _esperar(fn, timeout: float = 25.0, intervalo: float = 0.5):
    """Repete `fn` ate devolver algo verdadeiro ou estourar o tempo."""
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            r = fn()
            if r:
                return r
        except Exception:
            pass
        time.sleep(intervalo)
    return None


def _selects(page) -> tuple:
    """Localiza as listas de Empresas ('Todas') e Ramos ('Todos')."""
    sel_emp = sel_ramo = None
    for i in range(page.locator("select").count()):
        s = page.locator("select").nth(i)
        opcoes = _opcoes(s)
        if not opcoes:
            continue
        textos = [o["t"] for o in opcoes]
        if "Todas" in textos:
            sel_emp = s
        elif "Todos" in textos:
            sel_ramo = s
    return sel_emp, sel_ramo


def _campos_periodo(page):
    """Espera os dois campos de periodo ficarem visiveis."""
    def procurar():
        loc = page.locator("input[maxlength='6']:visible")
        if loc.count() >= 2:
            return loc
        loc = page.locator("input[type=text]:visible")
        return loc if loc.count() >= 2 else None

    return _esperar(procurar, timeout=30)


def preencher_e_processar(page, c: Consulta, agrupamento: str):
    """Preenche empresas=Todas, 1 ramo, periodo AAAAMM e clica Processar.

    O SES e uma pagina ASP.NET: ao trocar "Empresas", as listas sao recarregadas
    e os campos de periodo podem reaparecer depois. Por isso cada etapa espera
    o elemento ficar realmente disponivel, em vez de ler na hora.
    """
    sel_emp, sel_ramo = _selects(page)
    if sel_emp is None or sel_ramo is None:
        # a pagina pode estar montando as listas: tenta de novo por alguns segundos
        def _achar():
            e, r = _selects(page)
            return (e, r) if e is not None and r is not None else None

        achado = _esperar(_achar, timeout=20)
        if achado is None:
            raise RuntimeError("listas de Empresas/Ramos nao identificadas")
        sel_emp, sel_ramo = achado

    v_emp = sel_emp.evaluate(
        "el => ([...el.options].find(o => o.text.trim() === 'Todas') || {}).value"
    )
    sel_emp.select_option([v_emp])
    page.wait_for_timeout(900)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    # a troca de Empresas pode redesenhar a pagina: relocaliza as listas,
    # esperando a lista de ramos voltar a ter opcoes
    def _reachar():
        e, r = _selects(page)
        if r is None:
            return None
        return (e, r) if (_opcoes(r) or []) else None

    achado = _esperar(_reachar, timeout=20)
    if achado is not None:
        sel_emp, sel_ramo = achado

    def _valores_ramo():
        opcoes = _opcoes(sel_ramo) or []
        valores = [o["v"] for o in opcoes if o["t"].startswith(c.ramo)]
        return valores or None

    valores = _esperar(_valores_ramo, timeout=30)
    if not valores:
        opcoes = [o["t"] for o in (_opcoes(sel_ramo) or [])][:10]
        raise RuntimeError(
            f"ramo {c.ramo} nao aparece na lista do SES "
            f"(primeiras opcoes: {opcoes})"
        )
    sel_ramo.select_option(valores)
    page.wait_for_timeout(400)

    campos = _campos_periodo(page)
    if campos is None:
        raise RuntimeError(
            "campos de periodo nao encontrados (a pagina pode nao ter carregado por completo)"
        )
    inicio, fim = c.periodo
    campos.nth(0).fill("")
    campos.nth(0).fill(inicio)
    campos.nth(1).fill("")
    campos.nth(1).fill(fim)
    page.wait_for_timeout(200)

    try:
        page.get_by_text(re.compile(rf"Agrupar por\s+{re.escape(agrupamento)}", re.I)).first.click()
    except Exception:
        idx = {"empresa": 0, "ramo": 1, "mes": 2}.get(_normalizar(agrupamento), 0)
        page.locator("input[type=radio]").nth(idx).check()

    antes = list(page.context.pages)
    if not _clicar(page, "Processar"):
        raise RuntimeError("botao 'Processar' nao encontrado")
    page.wait_for_timeout(1500)
    novas = [p for p in page.context.pages if p not in antes]
    if novas:
        page = novas[0]
    page.wait_for_load_state("networkidle", timeout=120000)
    page.wait_for_timeout(1500)
    return page


def _valido(conteudo: bytes) -> bool:
    """O conteudo capturado tem mesmo a tabela do SES?"""
    try:
        ler_tabela(decodificar(conteudo))
        return True
    except Exception:
        return False


def _vazio(conteudo: bytes, c: Consulta) -> bool:
    """Pagina da consulta sem tabela: ramo sem dados no periodo (resultado legitimo)."""
    texto = decodificar(conteudo)
    try:
        ler_tabela(texto)
        return False
    except ValueError:
        pass
    rodape = metadados_rodape(texto)
    return rodape is not None and rodape[0] == [c.ramo] and (rodape[1], rodape[2]) == c.periodo


def capturar(page, c: Consulta) -> tuple[bytes, str]:
    """Rota A (export .xls oficial) com fallback para a Rota B (HTML da tela)."""
    try:
        with page.expect_download(timeout=60000) as info:
            if not _clicar(page, "Exporta para Ms Excel"):
                raise RuntimeError("botao de exportacao nao encontrado")
        caminho = Path(info.value.path())
        conteudo = caminho.read_bytes()
        if _valido(conteudo):
            return conteudo, "export_xls"
        if _vazio(conteudo, c):
            return conteudo, "vazio"
        log("  export baixado mas sem tabela valida; usando HTML da tela")
    except Exception as e:
        log(f"  export falhou ({e}); usando HTML da tela")

    conteudo = page.content().encode("utf-8")
    if _valido(conteudo):
        return conteudo, "dom_html"
    if _vazio(conteudo, c):
        return conteudo, "vazio"
    raise RuntimeError("nem o export nem a tela trouxeram a tabela do SES")


# --------------------------------------------------------------------------
# Orquestracao
# --------------------------------------------------------------------------

def extrair(
    cfg: Config,
    headless: bool = True,
    forcar: bool = False,
    anos: list[int] | None = None,
    ramos: list[str] | None = None,
    limite: int | None = None,
    consultas: list[Consulta] | None = None,
    pasta: Path | None = None,
) -> dict:
    from playwright.sync_api import sync_playwright  # import tardio: --offline nao precisa

    coletar, pular = pendentes(cfg, forcar, anos, ramos, consultas, pasta)
    if limite:
        coletar = coletar[:limite]
    log(f"{len(coletar)} consultas a coletar, {len(pular)} ja existentes no raw/.")

    resumo = {"coletadas": [], "puladas": [c.chave for c in pular], "falhas": [], "erros": {}}
    if not coletar:
        return resumo

    tentativas = cfg.atualizacao["tentativas"]
    pausa = cfg.atualizacao["pausa_entre_consultas_s"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(
            ignore_https_errors=True,
            accept_downloads=True,
            user_agent=_user_agent(browser),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1366, "height": 768},
        )
        page = ctx.new_page()

        for c in coletar:
            ultimo_erro = None
            for t in range(1, tentativas + 1):
                try:
                    log(f"{c.lob} {c.ramo} {c.ano}: tentativa {t}/{tentativas}")
                    abrir_consulta(page, cfg)
                    resultado = preencher_e_processar(page, c, cfg.agrupamento)
                    conteudo, fonte = capturar(resultado, c)
                    entrada = gravar_raw(cfg, c, conteudo, fonte, cfg.agrupamento, pasta=pasta)
                    etiqueta = "ok [vazio]" if fonte == "vazio" else f"ok [{fonte}]"
                    log(f"  {etiqueta} {entrada['arquivo']} sha256={entrada['sha256'][:12]}")
                    resumo["coletadas"].append(c.chave)
                    # mantem a aba principal aberta; fecha popups do resultado
                    for p in list(ctx.pages)[1:]:
                        p.close()
                    page = ctx.pages[0]
                    break
                except BloqueioSES as e:
                    log(f"  BLOQUEIO: {e}")
                    log("  Coleta interrompida (nao insisto). O pipeline segue com o raw/ existente.")
                    resumo["falhas"].append(c.chave)
                    resumo["erros"][c.chave] = str(e)
                    resumo["bloqueio"] = str(e)
                    browser.close()
                    return resumo
                except Exception as e:
                    ultimo_erro = str(e)
                    log(f"  falhou: {e}")
                    time.sleep(min(60, 5 * t * t))
            else:
                registrar(cfg, {
                    "tipo": "consulta", "status": "falha",
                    "chave": c.chave, "ramo": c.ramo, "ano": c.ano,
                    "periodo": f"{c.periodo[0]}-{c.periodo[1]}",
                    "erro": ultimo_erro,
                    "quando": datetime.now().isoformat(timespec="seconds"),
                }, pasta=pasta)
                resumo["falhas"].append(c.chave)
                resumo["erros"][c.chave] = ultimo_erro
            time.sleep(pausa)

        browser.close()
    return resumo
