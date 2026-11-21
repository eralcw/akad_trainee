#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o manual HTML de apresentacao do case (documento pessoal, fora do git).

Uso:
    python analise/gerar_roteiro_html.py

Saida:
    analise/roteiro_apresentacao.html  (ignorado pelo git)
"""

from __future__ import annotations

import base64
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "automacao"))
sys.path.insert(0, str(ROOT / "analise"))

from dashboard import analise as A  # noqa: E402
import eda  # noqa: E402
from roteiro_conteudo import (  # noqa: E402
    sec_didatico, sec_exemplo, sec_leituras, sec_tour, sec_transcricao,
)

OUT = ROOT / "analise" / "roteiro_apresentacao.html"
LOGO = ROOT / "automacao" / "dashboard" / "assets" / "akad_logo.png"
esc = eda.esc


# --------------------------------------------------------------------------
# Dados
# --------------------------------------------------------------------------

def carregar():
    base = A.carregar_base()
    if base.empty:
        raise SystemExit("Nenhum snapshot anual encontrado. Rode o pipeline primeiro.")
    lob = A.por_lob(base)
    lob_ano = A.por_lob_ano(base)
    cresc = A.crescimento(base)
    ativas = A.ativas_por_ano(base)
    ativas_pres = A.ativas_por_ano(base, "presenca")
    conc = A.concentracao(base)
    trend = A.tendencias(base)
    q4 = A.q4(base)
    akad = A.akad_tabela(base)
    comp = A.comparacao_akad(base)
    resp = {r["n"]: r for r in A.respostas(base)}
    anos = sorted(int(a) for a in base["ano"].unique())
    a0, a1 = anos[0], anos[-1]
    fase = base[base["ano"] >= 2022]
    fase_m = {l: A.metricas(fase[fase["lob"] == l]) for l in A.LOB_ORDEM if not fase[fase["lob"] == l].empty}
    fase_a = {
        l: A.metricas(fase[(fase["lob"] == l) & (fase["codigo_susep"] == A.AKAD)])
        for l in A.LOB_ORDEM
        if not fase[(fase["lob"] == l) & (fase["codigo_susep"] == A.AKAD)].empty
    }
    return base, lob, lob_ano, cresc, ativas, ativas_pres, conc, trend, q4, akad, comp, resp, anos, a0, a1, fase, fase_m, fase_a


def share_akad(base: pd.DataFrame, lob: str, ano: int) -> float:
    g = base[(base["lob"] == lob) & (base["ano"] == ano)]
    total = float(g["premio_ganho"].sum())
    ak = float(g.loc[g["codigo_susep"] == A.AKAD, "premio_ganho"].sum())
    return ak / total if total > 0 else 0.0


# --------------------------------------------------------------------------
# Gráficos SVG
# --------------------------------------------------------------------------

def scatter_svg(pontos, width=860, height=390):
    """x = margem do mercado; y = margem Akad - mercado; tamanho = prêmio."""
    left, right, top, bottom = 64, 24, 28, 48
    pw, ph = width - left - right, height - top - bottom
    xs = [p["x"] for p in pontos]
    ys = [p["y"] for p in pontos]
    x0, x1 = min(xs + [0.0]), max(xs + [0.0])
    y0, y1 = min(ys + [0.0]), max(ys + [0.0])
    padx = (x1 - x0) * 0.15 or 0.01
    pady = (y1 - y0) * 0.20 or 0.02
    x0, x1 = x0 - padx, x1 + padx
    y0, y1 = y0 - pady, y1 + pady

    def X(v):
        return left + pw * (v - x0) / (x1 - x0)

    def Y(v):
        return top + ph * (1 - (v - y0) / (y1 - y0))

    s = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for k in range(5):
        xv = x0 + (x1 - x0) * k / 4
        yv = y0 + (y1 - y0) * k / 4
        s.append(f'<line x1="{X(xv):.1f}" y1="{top}" x2="{X(xv):.1f}" y2="{top+ph}" stroke="{eda.RULE}" stroke-width="1"/>')
        s.append(f'<line x1="{left}" y1="{Y(yv):.1f}" x2="{left+pw}" y2="{Y(yv):.1f}" stroke="{eda.RULE}" stroke-width="1"/>')
        s.append(f'<text x="{X(xv):.1f}" y="{height-22}" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="{eda.MUTED}">{xv:.0%}</text>')
        s.append(f'<text x="{left-8}" y="{Y(yv)+4:.1f}" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="10" fill="{eda.MUTED}">{yv*100:+.0f} pp</text>')
    s.append(f'<line x1="{left}" y1="{Y(0):.1f}" x2="{left+pw}" y2="{Y(0):.1f}" stroke="{eda.INK}" stroke-width="1.2"/>')
    maxs = max(p["size"] for p in pontos) or 1
    for p in pontos:
        r = 9 + 18 * math.sqrt(max(p["size"], 0) / maxs)
        s.append(f'<circle cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="{r:.1f}" fill="{p["color"]}" fill-opacity="0.88" stroke="#FFFFFF" stroke-width="2"><title>{esc(p["label"])}: margem mercado {p["x"]:.1%}, vantagem {p["y"]*100:+.1f} pp</title></circle>')
        s.append(f'<text x="{X(p["x"]):.1f}" y="{Y(p["y"])-r-6:.1f}" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.INK}">{esc(p["label"])}</text>')
    s.append(f'<text x="{left+8}" y="{top+18}" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.MUTED}">seletivo</text>')
    s.append(f'<text x="{left+pw-8}" y="{top+18}" text-anchor="end" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.MUTED}">priorizar</text>')
    s.append(f'<text x="{left+8}" y="{top+ph-8}" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.MUTED}">evitar</text>')
    s.append(f'<text x="{left+pw-8}" y="{top+ph-8}" text-anchor="end" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.MUTED}">corrigir / parceria</text>')
    s.append(f'<text x="{left+pw/2}" y="{height-4}" text-anchor="middle" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{eda.MUTED}">atratividade do mercado (margem 2022–2025)</text>')
    s.append("</svg>")
    return "".join(s)


def qa(n: str, pergunta: str, resposta: str, grafico: str, explicar: list[str], cuidado: str, extra: str = "") -> str:
    itens = "".join(f"<li>{e}</li>" for e in explicar)
    return f"""
    <div class="qa" id="q{n}">
      <div class="qnum">Pergunta {n}</div>
      <h3>{pergunta}</h3>
      <p class="answer">{resposta}</p>
      {grafico}
      {extra}
      <div class="duas">
        <div><h4>Como explicar</h4><ul>{itens}</ul></div>
        <div><h4>Cuidado</h4><p>{cuidado}</p></div>
      </div>
    </div>"""


# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------

CSS = """
:root{
  --ink:#143057; --muted:#5B6485; --rule:#E4E6F4; --bg:#FFFFFF;
  --akad:#E9256A; --lilac:#6B72D8; --pink:#F7A3BF; --navy:#143057;
  --surface:#F4F5FD; --soft:#FFF7FA;
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:15px;line-height:1.6}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr);max-width:1320px;margin:0 auto}
nav.toc{position:sticky;top:0;height:100vh;overflow:auto;padding:28px 20px;border-right:1px solid var(--rule);background:#F8F9FE}
nav.toc .logo{height:34px;margin-bottom:18px}
nav.toc .toc-title{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);margin-bottom:10px}
nav.toc a{display:block;color:var(--ink);text-decoration:none;font-size:12px;padding:6px 8px;border-left:2px solid transparent;margin-bottom:2px}
nav.toc a:hover{color:var(--akad);border-left-color:var(--akad);background:#FFF}
nav.toc a.sub{padding-left:20px;color:var(--muted);font-size:11px}
main{padding:48px 54px 96px;max-width:1010px;min-width:0;overflow-x:hidden}
.kicker{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--lilac);margin-bottom:10px}
h1{font-size:42px;line-height:1.08;letter-spacing:-.03em;font-weight:600;margin:0 0 14px;max-width:820px}
.standfirst{font-size:18px;line-height:1.55;color:#3A4A6B;max-width:760px;margin:0 0 22px}
.meta{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:10px 0;margin-bottom:10px}
section{border-top:1px solid var(--rule);margin-top:54px;padding-top:28px;scroll-margin-top:16px}
.secnum{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--akad);margin-bottom:6px}
h2{font-size:28px;line-height:1.2;letter-spacing:-.02em;font-weight:600;margin:0 0 12px;max-width:780px}
h3{font-size:19px;font-weight:600;margin:30px 0 8px;color:var(--navy)}
h4{font-size:14px;font-weight:600;margin:16px 0 6px;color:var(--navy)}
p{max-width:78ch;margin:0 0 12px;color:#33466B}
ul{max-width:78ch;padding-left:20px;margin:0 0 12px}
li{margin-bottom:6px;color:#33466B}
code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:#F1F2FC;padding:1px 4px}
table{width:100%;border-collapse:collapse;margin:12px 0 16px;font-size:12.5px}
.tablewrap{overflow-x:auto;max-width:100%}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--rule);vertical-align:top}
thead th{font-weight:500;color:var(--muted);font-size:10.5px;border-bottom:1px solid var(--ink)}
td.num,th.num{text-align:right;font-family:'IBM Plex Mono',monospace;font-size:11.5px;white-space:nowrap}
tbody tr:hover{background:var(--surface)}
.chart{margin:14px 0 6px;overflow-x:auto;border:1px solid var(--rule);background:#FFF;padding:10px 12px}
.caption{font-size:11px;color:var(--muted);font-family:'IBM Plex Mono',monospace;margin:0 0 14px}
.nota{background:var(--surface);border-left:3px solid var(--lilac);padding:12px 14px;margin:14px 0;max-width:82ch}
.nota p{margin:0;font-size:14px}
.alerta{background:#FFF1F6;border-left:3px solid var(--akad);padding:12px 14px;margin:14px 0;max-width:82ch}
.alerta p{margin:0;font-size:14px}
.duas{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:10px}
.qa{border:1px solid var(--rule);padding:18px 18px 8px;margin:18px 0 24px;background:#FFF}
.qnum{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--akad);margin-bottom:2px}
.qa h3{margin-top:0}
.leitura{border-top:1px solid var(--rule);padding-top:18px;margin-top:24px}
.leitura h3{margin-top:0}
.leitura p{max-width:78ch}
.answer{font-size:15px;color:var(--ink);background:var(--soft);border-left:3px solid var(--akad);padding:10px 12px;max-width:none}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.col{border-top:2px solid var(--lilac);background:var(--surface);padding:12px 14px}
.col b{display:block;font-size:14px;color:var(--navy);margin-bottom:4px}
.col p{font-size:12.5px;margin:0 0 6px;max-width:none}
.col .formula{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--akad);display:block;margin-top:4px}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}
.flow span{font-family:'IBM Plex Mono',monospace;font-size:11px;background:#F1F2FC;border:1px solid var(--rule);padding:7px 9px}
.flow b{color:var(--akad);font-size:14px}
.fim{margin-top:54px;border-top:1px solid var(--rule);padding-top:14px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted)}
@media(max-width:900px){
  .layout{grid-template-columns:1fr}
  nav.toc{position:static;height:auto;max-height:230px;overflow:auto;border-right:0;border-bottom:1px solid var(--rule);padding:14px 16px}
  nav.toc a{padding:4px 6px;font-size:11px}
  nav.toc a.sub{display:none}
  main{padding:28px 20px 64px}
  h1{font-size:30px}
  .duas,.cols{grid-template-columns:1fr}
  td.num,th.num{white-space:normal}
  table{font-size:11px}
  th,td{padding:6px}
}
@media print{
  nav.toc{display:none}
  .layout{display:block}
  main{padding:0;max-width:none}
  section{page-break-inside:avoid}
  .qa{page-break-inside:avoid}
  .chart{page-break-inside:avoid}
  body{font-size:11pt}
}
"""


# --------------------------------------------------------------------------
# Seções
# --------------------------------------------------------------------------

def sec_historia(fase_m, fase_a, base, a0, a1):
    linhas = []
    for l in A.LOB_ORDEM:
        s0 = share_akad(base, l, 2022)
        s1 = share_akad(base, l, a1)
        am = fase_a.get(l, {})
        mm = fase_m.get(l, {})
        linhas.append(
            [
                esc(l),
                A.f_pct(s0),
                A.f_pct(s1),
                A.f_pct(am.get("margem")),
                A.f_pct(mm.get("margem")),
                A.f_pct(am.get("sinistralidade")),
                A.f_pct(mm.get("sinistralidade")),
            ]
        )
    tab = eda.tabela(
        ["LOB", "Share 2022", f"Share {a1}", "Margem Akad", "Margem mercado", "Sin. Akad", "Sin. mercado"],
        linhas,
        num={1, 2, 3, 4, 5, 6},
    )
    return f"""
    <section id="historia">
      <div class="secnum">00 · ponto de partida</div>
      <h2>A Akad tem uma história em duas fases — e isso muda a leitura</h2>
      <p>A operação começou em <strong>2012 com a Argo no Brasil</strong>. Até 2021, a empresa cresceu e aprendeu muito. Em <strong>2022</strong>, ela renasceu como <strong>Akad Seguros</strong>, uma seguradora moderna e sempre pronta para inovar. A marca Akad, portanto, existe de 2022 em diante.</p>
      <p>A série do case vai de 2020 a 2025 e mistura os dois momentos. Para tamanho de mercado e tendência, os seis anos são úteis; para julgar a Akad atual, a leitura principal é <strong>2022–2025</strong>. O código SUSEP da entidade continua o mesmo (02798), então o dado não se parte por nome; o que muda é a marca e a estratégia.</p>
      <div class="alerta"><p><strong>Frase para a apresentação:</strong> “A série de 2020–2025 tem dois capítulos. Até 2021, a operação era Argo. Em 2022, a Akad nasce como marca e estratégia. Por isso, para avaliar a Akad atual, eu olho 2022–2025; 2020–2021 serve de base histórica.”</p></div>
      <p>Na fase Akad, os números que sustentam a recomendação são:</p>
      {tab}
      <p class="caption">Fonte: snapshot anual SES/SUSEP. Margem e sinistralidade calculadas por razão de somas na fase 2022–2025.</p>
    </section>"""


def sec_mercado():
    return """
    <section id="mercado">
      <div class="secnum">01 · mercado 101</div>
      <h2>O mínimo de seguros para explicar o case sem se perder</h2>
      <p>O SES é o Sistema de Estatísticas da SUSEP. Ele publica, por seguradora, ramo e período, prêmios, sinistros e despesas. A consulta é um formulário antigo, uma combinação de ramo e período por vez. O case pede 14 códigos de ramo em 6 anos: 84 consultas.</p>
      <h3>LOB e ramo</h3>
      <p>LOB é uma linha de negócio, um grupo de ramos parecidos. Ramo é o código técnico da SUSEP. O case agrupa 14 códigos em 5 LOBs: RCG (0351), E&amp;O (0378), Empresarial (0118), Transportes (nove códigos) e Garantia (0775 e 0776). O 0645 não tem movimento: na prática, Transportes são oito ramos.</p>
      <h3>As seis colunas pedidas pelo case</h3>
      <div class="cols">
        <div class="col"><b>Prêmio Ganho</b><p>Parcela do prêmio emitido correspondente ao risco já decorrido. É a receita reconhecida no período, não o caixa recebido.</p><span class="formula">receita de risco decorrido</span></div>
        <div class="col"><b>Sinistro Ocorrido</b><p>Sinistro do período, incluindo a variação de reservas. Pode ser negativo quando a seguradora reverte reservas de anos anteriores.</p><span class="formula">sinistro + variação de reservas</span></div>
        <div class="col"><b>Sinistralidade</b><p>Quanto do prêmio foi consumido por sinistro. A regra é somar primeiro e dividir uma vez; nunca média de razões anuais.</p><span class="formula">soma(sinistro) ÷ soma(prêmio ganho)</span></div>
        <div class="col"><b>Despesa com Resseguro</b><p>Prêmio pago ao ressegurador para transferir parte do risco assumido.</p><span class="formula">custo de cessão de risco</span></div>
        <div class="col"><b>Receita com Resseguro</b><p>Valores que a seguradora recupera do ressegurador pelos riscos cedidos.</p><span class="formula">recuperação de resseguro</span></div>
        <div class="col"><b>Despesa Comercial</b><p>Custo de aquisição, principalmente comissão de corretagem. É o canal de venda aparecendo no número.</p><span class="formula">comissão + aquisição</span></div>
      </div>
      <h3>Resultado técnico e margem</h3>
      <p><strong>Resultado técnico</strong> = prêmio ganho + receita com resseguro − sinistro ocorrido − despesa com resseguro − despesa comercial. Não é lucro contábil: fora da conta ficam despesa administrativa, imposto e resultado financeiro. <strong>Margem</strong> = resultado técnico ÷ prêmio ganho.</p>
      <h3>Seguradora ativa</h3>
      <p>É a que tem prêmio ganho maior que zero no ano. O SES lista empresas registradas mesmo sem operação. Contar todas as linhas mede registro, não atividade. No RCG, são 54 ativas em 78 cadastradas no período.</p>
      <h3>Concentração</h3>
      <p>Top 5 é a soma do share das cinco maiores. “Até 80%” é quantas seguradoras explicam 80% do prêmio. HHI é a soma dos quadrados dos shares; quanto maior, mais concentrado. Nenhuma LOB do case é altamente concentrada, mas Transportes e Empresarial são as mais concentradas do grupo.</p>
      <div class="nota"><p><strong>Valores nominais.</strong> Não há correção pela inflação. O crescimento de prêmio inclui inflação e crescimento real; o case pede o número nominal da SUSEP.</p></div>
      <h3>Por que recalcular a sinistralidade</h3>
      <p>A coluna Sinistralidade da SUSEP vem arredondada e não é aditiva entre ramos ou anos. A análise usa a coluna apenas como conferência e recalcula a razão a partir dos valores.</p>
    </section>"""


def sec_ramos():
    linhas = [
        ["RCG", "0351", "Riscos de engenharia/construção: obras, montagem e responsabilidade do projeto.", "É a LOB mais instável do case; pico de 92,4% em 2023."],
        ["E&amp;O", "0378", "Responsabilidade civil profissional: erros e omissões de profissionais e empresas.", "Akad é líder, com 18,4% de share em 2025."],
        ["Empresarial", "0118", "Patrimonial empresarial: danos ao patrimônio, lucros cessantes e riscos operacionais.", "Mercado grande, mas Akad tem menos de 1% de share."],
        ["Transportes", "0621, 0622, 0632, 0644, 0645, 0652, 0654, 0655, 0656", "Cargas e responsabilidade do transportador, nacional e internacional, além de riscos diversos.", "0645 sem movimento; na prática, oito ramos. Akad é 3ª, mas margem baixa."],
        ["Garantia", "0775, 0776", "Seguro garantia: obrigações contratuais, licitações, performance e obrigações públicas.", "Mercado rentável, mas Akad é subescala."],
    ]
    tab = eda.tabela(["LOB", "Códigos", "O que cobre, em linguagem de negócio", "Leitura no case"], linhas)
    return f"""
    <section id="ramos">
      <div class="secnum">02 · ramos</div>
      <h2>O que cada LOB do case representa</h2>
      <p>Os códigos são técnicos; a leitura de negócio é o que importa na apresentação. A descrição abaixo é uma tradução para conversa, não a nomenclatura oficial da SUSEP.</p>
      {tab}
      <p class="caption">O 0645 não tem tabela em 2020–2024 e, em 2025, aparece com seis linhas zeradas. O contrato tolera consultas vazias; a análise trata Transportes como oito ramos com movimento.</p>
    </section>"""


def sec_automacao():
    return """
    <section id="automacao">
      <div class="secnum">03 · automação</div>
      <h2>Como a coleta foi construída</h2>
      <p>A automação foi separada em quatro camadas: coleta, tratamento, contrato e publicação. A regra central é que a rede só existe na coleta; o tratamento lê arquivos imutáveis e pode rodar offline. Isso torna a base reproduzível e auditável.</p>
      <div class="flow">
        <span>SES (formulário)</span><b>→</b><span>Playwright / Chromium</span><b>→</b><span>data/raw + SHA-256 + manifest</span><b>→</b><span>transform</span><b>→</b><span>contrato</span><b>→</b><span>snapshot</span><b>→</b><span>Streamlit</span>
      </div>
      <h3>1. Coleta (`ses/extract.py`)</h3>
      <p>O Playwright abre o SES, escolhe “Seguros: Prêmios e Sinistros”, preenche Empresas = Todas, um ramo, período AAAAMM, agrupamento por Empresa e clica em Processar. A captura principal é o botão “Exporta para Ms Excel”, que baixa um `.xls` (por dentro, HTML). Se o download falhar, o fallback é o HTML da tela. O robô usa User-Agent de Chrome real porque o firewall do SES recusa o UA padrão do Playwright; se detecta bloqueio, para em vez de insistir. Cada consulta tem até três tentativas, com pausa e backoff.</p>
      <p>Cada arquivo é gravado com nome contendo ramo, ano e timestamp, escrito em `.tmp` e renomeado de forma atômica. O manifesto registra SHA-256, bytes, parâmetros e horário. Consultas legitimamente vazias são registradas como `vazio`, não como erro.</p>
      <h3>2. Tratamento (`ses/transform.py`)</h3>
      <p>O `.xls` do SES tem 20 colunas, rodapé de parâmetros, linha Totais e códigos com espaço à direita. O parser usa lxml e lê a tabela como texto; não usa `pandas.read_html`, que interpreta “0,46” como 46 e “1.234” como 1,234. Ele identifica o cabeçalho por Empresa + Prêmio Ganho, converte o formato brasileiro, preserva zeros à esquerda, confere o rodapé e separa a linha Totais para reconciliação.</p>
      <p>Das 20 colunas, o case manda usar seis. As demais são descartadas. A base final é longa: uma linha por seguradora, ramo e ano, com prêmio ganho, sinistro ocorrido, despesa/receita de resseguro, despesa comercial, sinistralidade recalculada, resultado técnico e margem.</p>
      <h3>3. Contrato (`ses/validate.py`)</h3>
      <p>O snapshot só é publicado se passar em todos os checks: 84/84 consultas lidas; consultas vazias dentro do limite; soma das seguradoras igual à linha Totais do SES nas cinco colunas; rodapé de ramo/período coerente; sem duplicata; prêmio positivo por LOB/ano; colunas obrigatórias não zeradas; Akad presente; SHA-256 do raw igual ao manifesto. Erro bloqueia; aviso informa.</p>
      <p>No snapshot usado: 84/84 lidas, 79 reconciliações, 5 consultas vazias (0645), 4.007 linhas, 0 duplicatas e maior diferença de R$ 5 em uma consulta de R$ 2,65 bi. É a diferença entre “baixei uns dados” e “validei os dados”.</p>
      <h3>4. Publicação (`ses/publish.py`)</h3>
      <p>O snapshot é escrito em staging (Parquet, CSV e meta.json), renomeado de uma vez e só então o ponteiro `latest.json` é trocado de forma atômica. O dashboard lê sempre pelo ponteiro. Se a base for idêntica à vigente, nada é publicado. Há rollback e diff de retificações contra o snapshot anterior.</p>
      <h3>5. Período parcial (trimestre/mês)</h3>
      <p>O comando <code>pipeline.py periodo --periodo-ini 202510 --periodo-fim 202512 --ramos 0351</code> coleta um intervalo, grava com chave de período e publica em <code>data/atualizacoes</code>. Ele não toca no snapshot anual: um trimestre nunca substitui o ano fechado. A base parcial carrega `periodo_ini`, `periodo_fim`, `meses` e `parcial=True`. No app, a aba Atualizar dispara o GitHub Actions; a coleta roda lá, não no navegador do Streamlit.</p>
      <h3>6. GitHub Actions</h3>
      <p>O workflow <code>.github/workflows/update.yml</code> instala Python e Chromium, roda os testes, coleta em headless, processa, valida e comita <code>data/raw</code>, <code>data/atualizacoes</code>, <code>data/snapshots</code> e <code>data/runs</code>. Ele aceita disparo manual com ramos, anos, período, coletar sim/não e forçar. O Streamlit só envia o pedido via API do GitHub; o token fica nos secrets.</p>
      <div class="nota"><p><strong>Como explicar em 30 segundos:</strong> “O robô abre o SES, baixa o .xls de cada ramo/ano, grava o arquivo imutável com hash, transforma em base longa, confere contra a linha Totais da própria SUSEP e publica um snapshot. O dashboard lê o snapshot; a coleta roda no GitHub Actions.”</p></div>
    </section>"""


def sec_dashboard():
    return """
    <section id="dashboard">
      <div class="secnum">05 · dashboard</div>
      <h2>Como o app está organizado</h2>
      <p>O app tem quatro abas principais: <strong>Painel</strong>, <strong>Atualizar base</strong>, <strong>Status</strong> e <strong>Método</strong>. O Painel tem sete sub-abas: Visão geral, Mercado, Rentabilidade, Sinistralidade, Concorrência, Akad e Respostas.</p>
      <p>No topo do Painel, dois filtros globais: LOBs e intervalo de anos. Tudo é recalculado com o filtro. Se você escolher um único ano, as perguntas de crescimento ficam sem sentido; o app avisa.</p>
      <p>A camada de dados lê o snapshot anual por <code>publish.carregar_base</code> e calcula as métricas por razão de somas. O painel não mistura os recortes parciais: eles ficam em <code>data/atualizacoes</code> e aparecem na aba Status.</p>
      <div class="nota"><p><strong>O que mostrar:</strong> a aba Painel é a análise; a aba Atualizar é a operação; a aba Status é a prova de cobertura e validação; a aba Método é a explicação do cálculo. Na apresentação, comece pelo Painel, mostre a automação rapidamente e volte para a recomendação.</p></div>
    </section>"""


def sec_roteiro():
    return """
    <section id="roteiro">
      <div class="secnum">11 · tempo</div>
      <h2>Roteiro de 20 minutos</h2>
      <p><strong>0:00–1:30 — Método e automação.</strong> “Coletei 84 consultas no SES, 14 ramos em 6 anos, e validei cada uma contra a linha Totais da SUSEP. A base tem 4.007 linhas. A coleta roda no GitHub Actions; o app lê o snapshot validado.”</p>
      <p><strong>1:30–5:00 — Mercado.</strong> Q1: Transportes é a maior. Q7: E&amp;O cresce mais em %, Transportes em R$. Q2: Empresarial lidera em ativas com prêmio &gt; 0. Mensagem: o mercado cresce em todas as linhas; a diferença é a qualidade do crescimento.</p>
      <p><strong>5:00–8:00 — Rentabilidade.</strong> Q5: Garantia lidera o resultado técnico. Q6: E&amp;O lidera a margem. Mensagem: tamanho não é margem; Transportes tem escala e a menor margem.</p>
      <p><strong>8:00–11:30 — Risco.</strong> Q3: RCG e Transportes perto de 53%; Garantia abaixo de 20%. Q9: Empresarial melhora; RCG tem o pico de 2023; Transportes é estável em patamar alto. Q4: com corte de 1%, os outliers por LOB. Mensagem: a LOB mais saudável em nível é Garantia; a mais imprevisível é RCG.</p>
      <p><strong>11:30–14:00 — Concorrência.</strong> Q8: top 5 45–54%; 11–14 seguradoras explicam 80%; as relevantes têm margem próxima do mercado, com exceções. Mensagem: relevante é quem tem share material, não quem aparece na tabela.</p>
      <p><strong>14:00–17:00 — Akad.</strong> Conte a história: 2012 Argo; até 2021; 2022 Akad. Q10: E&amp;O 1º com 18,4%; Transportes 3º com 10,2%; RCG 14º com 2,2%. Q11: E&amp;O e RCG acima do mercado em margem; Transportes escala, mas margem baixa. Mensagem: a Akad atual é uma seguradora de 2022; a leitura de posição olha 2022–2025.</p>
      <p><strong>17:00–19:00 — Recomendação.</strong> Q12: E&amp;O é o núcleo; Transportes é escala a corrigir; RCG é aposta seletiva; Garantia/Empresarial são opcionais. E&amp;O combina liderança, margem e sinistralidade controlada; Transportes precisa de reprecificação, sinistros, resseguro e mix; RCG pede nicho e controle de acumulação.</p>
      <p><strong>19:00–20:00 — Limitações e próximos passos.</strong> Valores nominais; sem despesa administrativa/imposto/resultado financeiro; 0645 sem dados; 2020–21 é Argo. Próximo passo: aprofundar a causa da queda de margem em Transportes e testar cenários de crescimento em E&amp;O/RCG.</p>
    </section>"""


def sec_faq():
    return """
    <section id="faq">
      <div class="secnum">12 · perguntas prováveis</div>
      <h2>Respostas curtas para a banca</h2>
      <h3>“Por que resultado técnico e não lucro?”</h3>
      <p>Porque não inclui despesa administrativa, imposto nem resultado financeiro. Chamar de lucro convida a pergunta “o que ficou de fora”; resultado técnico é o nome honesto.</p>
      <h3>“Por que ativa é prêmio &gt; 0?”</h3>
      <p>Porque o SES lista seguradoras registradas mesmo sem operação. No RCG, 54 de 78 têm prêmio positivo. Contar linha mede registro, não atividade.</p>
      <h3>“Por que o 0645 não aparece?”</h3>
      <p>Não tem tabela em 2020–2024 e, em 2025, aparece com seis linhas zeradas. Na prática, Transportes são oito ramos.</p>
      <h3>“Por que sinistralidade negativa?”</h3>
      <p>Reversão de reserva. Exemplo: Companhia de Seguros Aliança da Bahia, no RCG, com sinistro negativo em 2024; no agregado de seis anos, a razão fica em -202,8 vezes o prêmio. Não é erro; agregar antes de dividir dilui.</p>
      <h3>“Por que RCG tem 92,4% em 2023?”</h3>
      <p>Pico de sinistros no ano. Pode ser um ou poucos casos grandes; a série mostra o efeito, não a causa. É o principal argumento para tratar RCG como volátil.</p>
      <h3>“Por que a margem de Transportes caiu?”</h3>
      <p>Em 2025 a sinistralidade da Akad em Transportes ficou em 68,3% e a margem em 0,2%. A base não mostra a causa; as hipóteses são mix, sinistros grandes, reprecificação e resseguro.</p>
      <h3>“O que mudou em 2022?”</h3>
      <p>A marca e a estratégia. 2020–2021 é Argo; 2022+ é Akad. A série de seis anos tem uma quebra estrutural; para a Akad atual, olhe 2022–2025.</p>
      <h3>“Por que valores nominais?”</h3>
      <p>É o que a SUSEP publica. Não deflacionei; o crescimento inclui inflação. Se quiser, o próximo passo é deflacionar pelo IPCA.</p>
      <h3>“Como você validou?”</h3>
      <p>Cada consulta foi comparada com a linha Totais do SES; a maior diferença no snapshot foi R$ 5 em R$ 2,65 bi. Também conferi SHA-256 do raw, rodapé de ramo/período, duplicatas e prêmio positivo por LOB/ano.</p>
      <h3>“O que é a automação?”</h3>
      <p>Playwright abre o SES, preenche ramo/período, exporta o .xls, grava o raw imutável com SHA-256, transforma em base longa, valida o contrato e publica o snapshot. Roda no GitHub Actions; o app só lê e dispara.</p>
    </section>"""


def sec_glossario():
    return """
    <section id="glossario">
      <div class="secnum">13 · glossário</div>
      <h2>Glossário curto</h2>
      <table><thead><tr><th>Termo</th><th>Definição</th></tr></thead><tbody>
      <tr><td>Prêmio ganho</td><td>Receita de risco decorrido.</td></tr>
      <tr><td>Sinistro ocorrido</td><td>Sinistro do período, com reservas.</td></tr>
      <tr><td>Sinistralidade</td><td>Sinistro ÷ prêmio ganho.</td></tr>
      <tr><td>Resultado técnico</td><td>Prêmio + receita de resseguro − sinistro − despesa de resseguro − despesa comercial.</td></tr>
      <tr><td>Margem</td><td>Resultado técnico ÷ prêmio.</td></tr>
      <tr><td>Ativa</td><td>Prêmio ganho &gt; 0.</td></tr>
      <tr><td>Relevante</td><td>Top 80% do prêmio acumulado.</td></tr>
      <tr><td>HHI</td><td>Soma dos quadrados dos shares.</td></tr>
      <tr><td>LOB</td><td>Grupo de ramos semelhantes.</td></tr>
      <tr><td>Ramo</td><td>Código técnico da SUSEP.</td></tr>
      </tbody></table>
    </section>"""


def sec_checklist():
    return """
    <section id="checklist">
      <div class="secnum">14 · antes de apresentar</div>
      <h2>Checklist</h2>
      <ul>
        <li>Rodar o app com o período completo (2020–2025) e conferir o logo e as cores.</li>
        <li>Testar os filtros de LOB e ano; se filtrar um ano só, as perguntas de crescimento ficam sem sentido.</li>
        <li>Abrir a aba Respostas e baixar o Markdown.</li>
        <li>Ter o EDA aberto para quem pedir o tratamento dos dados.</li>
        <li>Saber de cor cinco números: R$ 83,1 bi de prêmio; 43,2% de sinistralidade; R$ 17,2 bi de resultado técnico; 20,7% de margem; E&amp;O 18,4% de share e 41,2% de margem na fase Akad.</li>
        <li>Dizer a frase da marca: “2020–2021 é Argo; 2022 em diante é Akad.”</li>
      </ul>
    </section>"""


# --------------------------------------------------------------------------
# Montagem
# --------------------------------------------------------------------------

def main() -> int:
    (base, lob, lob_ano, cresc, ativas, ativas_pres, conc, trend, q4, akad,
     comp, resp, anos, a0, a1, fase, fase_m, fase_a) = carregar()

    # --- gráficos ---
    q1 = eda.hbar_svg(
        [(r.lob, float(r.premio), A.LOB_COR[r.lob]) for _, r in lob.sort_values("premio").iterrows()],
        fmt=A.f_bi, label_w=150,
    )
    cats = [l for l in A.LOB_ORDEM if l in ativas.index]
    q2 = eda.grouped_svg(
        cats,
        [
            (str(a0), [int(ativas.loc[l, a0]) for l in cats], A.LOB_COR["Empresarial"]),
            (str(a1), [int(ativas.loc[l, a1]) for l in cats], A.LOB_COR["E&O"]),
        ],
        fmt=lambda v: f"{int(v)}", y_fmt=lambda v: f"{int(v)}",
    )
    q3 = eda.hbar_svg(
        [(r.lob, float(r.sinistralidade), A.LOB_COR[r.lob]) for _, r in lob.sort_values("sinistralidade").iterrows()],
        fmt=A.f_pct, label_w=150,
    )
    q5 = eda.hbar_svg(
        [(r.lob, float(r.lucro), A.LOB_COR[r.lob]) for _, r in lob.sort_values("lucro").iterrows()],
        fmt=A.f_bi, label_w=150,
    )
    q6 = eda.hbar_svg(
        [(r.lob, float(r.margem), A.LOB_COR[r.lob]) for _, r in lob.sort_values("margem").iterrows()],
        fmt=A.f_pct, label_w=150,
    )
    q7 = eda.line_svg(
        [(r.name, [float(r.primeiro), float(r.ultimo)], A.LOB_COR[r.name]) for _, r in cresc.iterrows()],
        [str(a0), str(a1)], y_fmt=lambda v: f"{v/1e9:.1f} bi", y0=0,
    )
    q8 = eda.hbar_svg(
        [(r.lob, float(r.top5), A.LOB_COR[r.lob]) for _, r in conc.sort_values("top5").iterrows()],
        fmt=A.f_pct, label_w=150,
    )
    q9 = eda.line_svg(
        [
            (l, [float(v) for v in lob_ano[lob_ano["lob"] == l].sort_values("ano")["sinistralidade"]], A.LOB_COR[l])
            for l in A.LOB_ORDEM
        ],
        [str(a) for a in anos], y_fmt=lambda v: f"{v:.0%}", y0=0,
    )
    q10 = eda.line_svg(
        [
            (l, [share_akad(base, l, a) for a in anos], A.LOB_COR[l])
            for l in A.LOB_ORDEM
        ],
        [str(a) for a in anos], y_fmt=lambda v: f"{v:.0%}", y0=0,
    )
    q11 = eda.grouped_svg(
        [l for l in A.LOB_ORDEM if l in set(comp["lob"])],
        [
            ("Akad", [float(comp.loc[comp["lob"] == l, "akad_mg"].iloc[0]) for l in A.LOB_ORDEM if l in set(comp["lob"])], A.LOB_COR["E&O"]),
            ("Mercado", [float(comp.loc[comp["lob"] == l, "mercado_mg"].iloc[0]) for l in A.LOB_ORDEM if l in set(comp["lob"])], A.LOB_COR["Empresarial"]),
        ],
        fmt=A.f_pct, y_fmt=lambda v: f"{v:.0%}",
    )
    pontos = []
    for l in A.LOB_ORDEM:
        am, mm = fase_a.get(l), fase_m.get(l)
        if not am or not mm:
            continue
        pontos.append({
            "label": l,
            "x": mm["margem"],
            "y": am["margem"] - mm["margem"],
            "size": mm["premio"],
            "color": A.LOB_COR[l],
        })
    q12 = scatter_svg(pontos)

    # --- tabelas ---
    tab_q2 = eda.tabela(
        ["LOB", f"Linhas {a0}", f"Ativas {a0}", f"Linhas {a1}", f"Ativas {a1}"],
        [[
            esc(l), A.f_num(ativas_pres.loc[l, a0]), A.f_num(ativas.loc[l, a0]),
            A.f_num(ativas_pres.loc[l, a1]), A.f_num(ativas.loc[l, a1]),
        ] for l in cats],
        num={1, 2, 3, 4},
    )
    tab_q4 = eda.tabela(
        ["LOB", "Seguradora", "Prêmio", "Share", "Sinistralidade", "Margem"],
        [[
            esc(r["lob"]), esc(r["seguradora"]), A.f_mi(r["premio"]),
            A.f_pct(r["share"]), A.f_pct(r["sinistralidade"]), A.f_pct(r["margem"]),
        ] for _, r in q4.iterrows()],
        num={2, 3, 4, 5},
    )
    tab_q7 = eda.tabela(
        ["LOB", f"Prêmio {a0}", f"Prêmio {a1}", "Variação absoluta", "Variação %"],
        [[esc(r.name), A.f_bi(r.primeiro), A.f_bi(r.ultimo), A.f_bi(r["abs"]), A.f_pct(r["pct"])] for _, r in cresc.iterrows()],
        num={1, 2, 3, 4},
    )
    tab_q8 = eda.tabela(
        ["LOB", "Seguradora", "Share", "Sinistralidade", "Margem", "Δ sin.", "Δ margem"],
        [
            [
                esc(l),
                esc(r["seguradora"]),
                A.f_pct(r["share"]),
                A.f_pct(r["sinistralidade"]),
                A.f_pct(r["margem"]),
                A.f_pct(r["sinistralidade"] - A.metricas(base[base["lob"] == l])["sinistralidade"]),
                A.f_pct(r["margem"] - A.metricas(base[base["lob"] == l])["margem"]),
            ]
            for l in A.LOB_ORDEM
            for _, r in A.por_seguradora(base[(base["lob"] == l) & (base["premio_ganho"] > 0)])
            .sort_values("premio", ascending=False)
            .head(3)
            .iterrows()
        ],
        num={2, 3, 4, 5, 6},
    )
    tab_q10 = eda.tabela(
        ["LOB", "Prêmio 2020", "Prêmio 2025", "Share 2020", "Share 2025", "Rank 2020", "Rank 2025"],
        [[
            esc(r.lob), A.f_bi(r.premio0), A.f_bi(r.premio1),
            A.f_pct(r.share0), A.f_pct(r.share1),
            f"{int(r.rank0)}º" if pd.notna(r.rank0) else "–",
            f"{int(r.rank1)}º" if pd.notna(r.rank1) else "–",
        ] for _, r in akad.iterrows()],
        num={1, 2, 3, 4},
    )
    tab_q11 = eda.tabela(
        ["LOB", "Mercado sin.", "Mercado margem", "Akad sin.", "Akad margem", "Pares", "Margem pares", "Relevantes", "Margem relevantes"],
        [[
            esc(r.lob), A.f_pct(r.mercado_sin), A.f_pct(r.mercado_mg),
            A.f_pct(r.akad_sin), A.f_pct(r.akad_mg),
            str(int(r.peers_n)), A.f_pct(r.peers_mg),
            str(int(r.relev_n)), A.f_pct(r.relev_mg),
        ] for _, r in comp.iterrows()],
        num={1, 2, 3, 4, 5, 6, 7, 8},
    )

    logo_html = ""
    if LOGO.exists():
        b64 = base64.b64encode(LOGO.read_bytes()).decode("ascii")
        logo_html = f'<img class="logo" src="data:image/png;base64,{b64}" alt="Akad Seguros">'

    # --- perguntas ---
    perguntas = [
        qa("01", "Qual a LOB com maior prêmio no período inteiro (2020 a 2025)?", resp["01"]["resposta"],
           f'<div class="chart">{q1}</div><p class="caption">Prêmio ganho acumulado 2020–2025, R$ bi.</p>',
           ["Leia a barra, não a ordem alfabética.", "Transportes tem 35% do prêmio das cinco LOBs; E&O tem 4,5%.", "É prêmio nominal."],
           "Não confunda prêmio com resultado: a maior LOB não é a mais rentável."),
        qa("02", "Qual a LOB com mais seguradoras ativas em 2020? E em 2025?", resp["02"]["resposta"],
           f'<div class="chart">{q2}</div><p class="caption">Seguradoras com prêmio ganho > 0, 2020 vs 2025.</p>{tab_q2}',
           ["Ativa = prêmio > 0.", "Empresarial vai de 47 para 51; RCG de 45 para 47; Transportes fica em 25.", "A contagem por presença de linha seria outra."],
           "Se usar presença de linha, RCG aparece com 70 em 2020. Isso mede registro, não operação."),
        qa("03", "Qual a LOB com maior sinistralidade no período inteiro?", resp["03"]["resposta"],
           f'<div class="chart">{q3}</div><p class="caption">Sinistralidade agregada 2020–2025.</p>',
           ["RCG 52,7% e Transportes 52,6% estão praticamente empatados.", "Garantia 19,6% opera em outro patamar.", "Use a razão de somas."],
           "A diferença entre RCG e Transportes é de 0,1 pp; não trate como vitória folgada."),
        qa("04", "Qual a seguradora com maior sinistralidade no período em cada LOB?", resp["04"]["resposta"],
           f'{tab_q4}<p class="caption">Top 3 por LOB com share mínimo de 1% do prêmio da LOB.</p>',
           ["Use o corte de materialidade.", "Os extremos são Starr 71,9% (Transportes), HDI 74,3% (Empresarial), BTG 138,4% (Garantia), Generali 267,3% (RCG) e Allianz 66,0% (E&O).", "Sinistralidade negativa é reversão de reserva."],
           "Sem corte, empresas minúsculas aparecem com 1.000% e dominam o ranking."),
        qa("05", "Quanto foi o resultado técnico de cada LOB?", resp["05"]["resposta"],
           f'<div class="chart">{q5}</div><p class="caption">Resultado técnico acumulado 2020–2025, R$ bi.</p>',
           ["Garantia lidera com R$ 5,34 bi, mesmo sendo a terceira em prêmio.", "Transportes tem o maior prêmio e a menor margem.", "A fórmula não inclui despesa administrativa, imposto nem resultado financeiro."],
           "Não chame de lucro contábil; a banca vai perguntar o que ficou de fora."),
        qa("06", "Quanto foi a margem de cada LOB?", resp["06"]["resposta"],
           f'<div class="chart">{q6}</div><p class="caption">Margem = resultado técnico ÷ prêmio ganho.</p>',
           ["E&O 29,4%; Garantia 26,7%; RCG 22,8%; Empresarial 20,3%; Transportes 15,2%.", "Tamanho não é margem.", "A margem é o elo entre crescimento e rentabilidade."],
           "Margem alta com prêmio pequeno não resolve escala; leia junto com a Q1."),
        qa("07", "Qual LOB teve o maior crescimento em prêmio, em porcentagem e em valor absoluto?", resp["07"]["resposta"],
           f'<div class="chart">{q7}</div><p class="caption">Prêmio 2020 → 2025 por LOB, R$ bi.</p>{tab_q7}',
           ["E&O cresce 108,7% em %, mas adiciona R$ 0,46 bi.", "Transportes cresce 74,4% e adiciona R$ 2,48 bi.", "Sempre apresente % e absoluto juntos."],
           "Porcentagem alta sobre base pequena pode ser irrelevante em tamanho."),
        qa("08", "Quais são as seguradoras realmente relevantes de cada LOB? Como margem e sinistralidade se comparam ao mercado?", resp["08"]["resposta"],
           f'<div class="chart">{q8}</div><p class="caption">Top 5 share por LOB.</p>{tab_q8}',
           ["Relevante = top 80% do prêmio acumulado.", "Top 5 concentra 45–54%; 11–14 seguradoras explicam 80%.", "As relevantes têm margem próxima do mercado, com exceções."],
           "Não liste as 70 seguradoras; foque nas que explicam 80%."),
        qa("09", "Como é a tendência de sinistros e sinistralidade de cada LOB? Qual é a mais saudável/atrativa?", resp["09"]["resposta"],
           f'<div class="chart">{q9}</div><p class="caption">Sinistralidade anual por LOB.</p>',
           ["Garantia é a mais confortável em nível.", "Empresarial é a que mais melhora.", "RCG é a mais volátil; Transportes é a mais estável, mas em patamar alto."],
           "Nível e tendência são coisas diferentes; não escolha a mais saudável só pela média."),
        qa("10", "Em quais LOBs a Akad é relevante? Como se comportou a posição dela? O que pode explicar as mudanças?", resp["10"]["resposta"],
           f'<div class="chart">{q10}</div><p class="caption">Share da Akad por LOB e ano.</p>{tab_q10}',
           ["E&O 18,4% e 1º; Transportes 10,2% e 3º; RCG 2,2% e 14º.", "2020–2021 é Argo; 2022+ é Akad.", "Na fase Akad, E&O 15,2%→18,4%, Transportes 7,3%→10,2%, RCG 0,8%→2,2%."],
           "Não atribua todo o crescimento a desempenho orgânico: o rebranding de 2022 é uma quebra estrutural."),
        qa("11", "Considerando margem e sinistralidade, em quais LOBs a Akad é melhor que o mercado? E em relação aos pares e relevantes?", resp["11"]["resposta"],
           f'<div class="chart">{q11}</div><p class="caption">Margem Akad vs mercado, período completo.</p>{tab_q11}',
           ["E&O e RCG têm margem acima do mercado.", "Transportes tem escala, mas margem abaixo.", "Garantia e Empresarial são subescala."],
           "Olhe também os pares de porte e as relevantes; a vantagem de E&O não é só tamanho."),
        qa("12", "Em qual LOB a Akad deveria focar nos próximos anos? Qual deve ser a estratégia?", resp["12"]["resposta"],
           f'<div class="chart">{q12}</div><p class="caption">Matriz: atratividade do mercado × vantagem da Akad, fase 2022–2025. Tamanho = prêmio.</p>',
           ["E&O é o núcleo: liderança, margem e sinistralidade controlada.", "Transportes é escala a corrigir: reprecificação, sinistros, resseguro e mix.", "RCG é aposta seletiva; Garantia e Empresarial são opcionais."],
           "É uma recomendação, não um resultado automático. Diga as premissas e o que ficou fora do dado."),
    ]

    nav = """
    <nav class="toc">
      %s
      <div class="toc-title">CONTEÚDO</div>
      <a href="#historia">00 · história da Akad</a>
      <a href="#mercado">01 · mercado 101</a>
      <a href="#ramos">02 · ramos</a>
      <a href="#automacao">03 · automação</a>
      <a href="#didatico">04 · automação sem jargão</a>
      <a href="#dashboard">05 · dashboard</a>
      <a href="#perguntas">06 · as 12 perguntas</a>
      <a href="#leituras">07 · leitura dos gráficos</a>
      <a href="#exemplo">08 · exemplo real</a>
      <a href="#tour">09 · tour do app</a>
      <a href="#transcricao">10 · transcrição 20 min</a>
      <a class="sub" href="#q01">Q1 · prêmio</a>
      <a class="sub" href="#q02">Q2 · ativas</a>
      <a class="sub" href="#q03">Q3 · sinistralidade</a>
      <a class="sub" href="#q04">Q4 · por seguradora</a>
      <a class="sub" href="#q05">Q5 · resultado</a>
      <a class="sub" href="#q06">Q6 · margem</a>
      <a class="sub" href="#q07">Q7 · crescimento</a>
      <a class="sub" href="#q08">Q8 · relevantes</a>
      <a class="sub" href="#q09">Q9 · tendência</a>
      <a class="sub" href="#q10">Q10 · Akad</a>
      <a class="sub" href="#q11">Q11 · vs mercado</a>
      <a class="sub" href="#q12">Q12 · foco</a>
      <a href="#roteiro">11 · roteiro 20 min</a>
      <a href="#faq">12 · perguntas prováveis</a>
      <a href="#glossario">13 · glossário</a>
      <a href="#checklist">14 · checklist</a>
    </nav>""" % logo_html

    perguntas_html = "\n".join(perguntas)
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manual de apresentação · Case Akad 2027</title>
<style>{CSS}</style></head><body>
<div class="layout">
{nav}
<main>
  <div class="kicker">Akad Seguros · Case Trainee 2027 · documento pessoal</div>
  <h1>Manual de apresentação: da coleta à recomendação</h1>
  <p class="standfirst">Tudo o que você precisa para explicar a automação, o dashboard, o mercado de seguros e as 12 perguntas — com os gráficos e as frases de leitura.</p>
  <div class="meta">SNAPSHOT 2020–2025 · 4.007 linhas · 84 consultas · fonte SES/SUSEP · gerado em {pd.Timestamp.now():%Y-%m-%d %H:%M}</div>

  {sec_historia(fase_m, fase_a, base, a0, a1)}
  {sec_mercado()}
  {sec_ramos()}
  {sec_automacao()}
  {sec_didatico()}
  {sec_dashboard()}

  <section id="perguntas">
    <div class="secnum">06 · as 12 perguntas</div>
    <h2>Resposta, gráfico, como explicar e cuidado</h2>
    <p>Cada bloco abaixo tem a resposta curta, o gráfico correspondente e a leitura para a apresentação. As respostas são recalculadas com a base anual; os recortes parciais ficam separados.</p>
    {perguntas_html}
  </section>

  {sec_leituras()}
  {sec_exemplo(base)}
  {sec_tour()}
  {sec_transcricao()}

  {sec_roteiro()}
  {sec_faq()}
  {sec_glossario()}
  {sec_checklist()}

  <div class="fim">Documento gerado por analise/gerar_roteiro_html.py · uso pessoal · não comitado (gitignore) · Akad Seguros 2027</div>
</main>
</div>
</body></html>"""

    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    OUT.write_text(html, encoding="utf-8")
    print(f"Gerado: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
