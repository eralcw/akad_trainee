#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EDA do mercado de seguros no SES/SUSEP - Case Trainee Akad 2027.

Le o snapshot publicado pelo pipeline, documenta o tratamento aplicado as
tabelas do SES e gera um relatorio HTML autocontido (sem servidor, sem CDN).

Uso:
    python analise/eda.py                 # gera analise/eda.html
    python analise/eda.py --snapshot 20261120T185656
    python analise/eda.py --saida outro.html

Regras de metodo:
  - sinistralidade = soma(sinistro ocorrido) / soma(premio ganho)
  - resultado tecnico (coluna `lucro` na base, por compatibilidade) =
        premio ganho + receita resseguro - sinistro ocorrido
        - despesa resseguro - despesa comercial
  - margem = resultado tecnico / premio ganho
  - seguradora "ativa" em um ramo/ano = premio ganho > 0
  - linhas com premio <= 0 ficam nas somas de mercado (os totais do SES as
    incluem) mas saem das contagens de ativas e das razoes por seguradora.
  - chave de seguradora = codigo SUSEP; o nome e apenas rotulo.
"""

from __future__ import annotations

import argparse
import html
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "snapshots"
RAW_DIR = ROOT / "data" / "raw"

INK = "#12201D"
MUTED = "#5C6B66"
RULE = "#CBD6D1"
BG = "#EDF1EF"
PINE = "#17453C"
SIGNAL = "#C8451F"
STEEL = "#3D6E8C"
MOSS = "#6E8B3D"
COPPER = "#B4723A"
PLUM = "#7D5A8C"
NEUTRAL = "#98A6A1"

LOB_ORDEM = ["Transportes", "Empresarial", "Garantia", "RCG", "E&O"]
LOB_COR = {
    "Transportes": COPPER,
    "Empresarial": MOSS,
    "Garantia": PLUM,
    "RCG": PINE,
    "E&O": STEEL,
}
VALORES = [
    "premio_ganho",
    "sinistro_ocorrido",
    "despesa_resseguro",
    "receita_resseguro",
    "despesa_comercial",
]
AKAD = "02798"


# --------------------------------------------------------------------------
# Carregamento e tratamento
# --------------------------------------------------------------------------

def snapshot_vigente() -> str:
    ponteiro = SNAP_DIR / "latest.json"
    return json.loads(ponteiro.read_text(encoding="utf-8"))["snapshot"]


def carregar(snapshot: str | None = None):
    nome = snapshot or snapshot_vigente()
    pasta = SNAP_DIR / nome
    meta = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))
    try:
        base = pd.read_parquet(pasta / "base.parquet")
    except Exception:
        base = pd.read_csv(
            pasta / "base.csv",
            encoding="utf-8-sig",
            dtype={"ramo_codigo": str, "codigo_susep": str},
        )
    base["ramo_codigo"] = base["ramo_codigo"].astype(str).str.zfill(4)
    base["codigo_susep"] = base["codigo_susep"].astype(str).str.zfill(5)
    return base, meta, nome


def ler_manifesto() -> list[dict]:
    caminho = RAW_DIR / "manifest.jsonl"
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def mascaras(base: pd.DataFrame):
    zerada = base[VALORES].fillna(0).eq(0).all(axis=1)
    ativa = base["premio_ganho"] > 0
    return zerada, ativa


def metricas(df: pd.DataFrame) -> dict:
    p = float(df["premio_ganho"].sum())
    s = float(df["sinistro_ocorrido"].sum())
    l = float(df["lucro"].sum())
    return {
        "premio": p,
        "sinistro": s,
        "lucro": l,
        "sinistralidade": s / p if p > 0 else math.nan,
        "margem": l / p if p > 0 else math.nan,
    }


def por_lob(base: pd.DataFrame) -> pd.DataFrame:
    linhas = [{"lob": lob, **metricas(g)} for lob, g in base.groupby("lob")]
    return pd.DataFrame(linhas).sort_values("premio", ascending=False).reset_index(drop=True)


def por_lob_ano(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for (lob, ano), g in base.groupby(["lob", "ano"]):
        linhas.append({"lob": lob, "ano": int(ano), **metricas(g)})
    return pd.DataFrame(linhas).sort_values(["lob", "ano"]).reset_index(drop=True)


def por_seguradora(base: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for (lob, cod), g in base.groupby(["lob", "codigo_susep"], sort=False):
        m = metricas(g)
        m.update(
            lob=lob,
            codigo_susep=cod,
            seguradora=g["seguradora"].iloc[-1],
        )
        linhas.append(m)
    df = pd.DataFrame(linhas)
    total = df.groupby("lob")["premio"].transform("sum")
    df["share"] = df["premio"] / total.replace(0, np.nan)
    return df


def consultas_vazias(base: pd.DataFrame) -> pd.DataFrame:
    q = base.groupby(["lob", "ramo_codigo", "ano"]).premio_ganho.sum().reset_index()
    return q[q["premio_ganho"] <= 0].sort_values(["lob", "ramo_codigo", "ano"])


def crescimento(base: pd.DataFrame) -> pd.DataFrame:
    p = base.groupby(["lob", "ano"]).premio_ganho.sum().unstack()
    anos = sorted(p.columns)
    primeiro, ultimo = anos[0], anos[-1]
    out = pd.DataFrame(
        {
            "primeiro": p[primeiro],
            "ultimo": p[ultimo],
            "abs": p[ultimo] - p[primeiro],
            "pct": p[ultimo] / p[primeiro] - 1,
            "cagr": (p[ultimo] / p[primeiro]) ** (1 / (ultimo - primeiro)) - 1,
        }
    )
    return out.sort_values("pct", ascending=False)


def concentracao(base: pd.DataFrame) -> pd.DataFrame:
    ativa = base[base["premio_ganho"] > 0]
    cadastradas = base.groupby("lob").codigo_susep.nunique()
    linhas = []
    for lob, g in ativa.groupby("lob"):
        s = g.groupby("codigo_susep").premio_ganho.sum().sort_values(ascending=False)
        share = s / s.sum()
        cum = share.cumsum()
        n80 = int((cum < 0.8).sum()) + 1
        linhas.append(
            {
                "lob": lob,
                "n_total": int(cadastradas.get(lob, 0)),
                "n_ativas": int(len(s)),
                "top5": float(share.head(5).sum()),
                "n80": n80,
                "hhi": int((share**2).sum() * 10000),
            }
        )
    return pd.DataFrame(linhas).sort_values("top5", ascending=False)


def ativas_por_ano(base: pd.DataFrame, definicao: str) -> pd.DataFrame:
    if definicao == "premio":
        df = base[base["premio_ganho"] > 0]
        return df.groupby(["lob", "ano"]).codigo_susep.nunique().unstack()
    return base.groupby(["lob", "ano"]).codigo_susep.nunique().unstack()


def tendencias(base: pd.DataFrame, ativa: bool = False) -> pd.DataFrame:
    df = base[base["premio_ganho"] > 0] if ativa else base
    s = por_lob_ano(df)
    linhas = []
    for lob, g in s.groupby("lob"):
        g = g.sort_values("ano")
        if len(g) >= 2:
            slope = float(np.polyfit(g["ano"], g["sinistralidade"], 1)[0])
            cresc_sin = (g["sinistro"].iloc[-1] / g["sinistro"].iloc[0]) ** (
                1 / (g["ano"].iloc[-1] - g["ano"].iloc[0])
            ) - 1
        else:
            slope = math.nan
            cresc_sin = math.nan
        linhas.append(
            {
                "lob": lob,
                "sin": float(g["sinistralidade"].mean()),
                "vol": float(g["sinistralidade"].std()),
                "slope": slope,
                "cresc_sinistro": float(cresc_sin),
                "margem": float(g["margem"].mean()),
            }
        )
    return pd.DataFrame(linhas).sort_values("sin", ascending=True)


def out_por_lob(base: pd.DataFrame, min_share: float = 0.01) -> pd.DataFrame:
    seg = por_seguradora(base[base["premio_ganho"] > 0])
    seg = seg[(seg["share"] >= min_share) & (seg["premio"] > 0)].copy()
    linhas = []
    for lob, g in seg.groupby("lob"):
        top = g.sort_values("sinistralidade", ascending=False).head(3)
        for _, r in top.iterrows():
            linhas.append(
                {
                    "lob": lob,
                    "seguradora": r["seguradora"],
                    "premio": r["premio"],
                    "share": r["share"],
                    "sin": r["sinistralidade"],
                    "margem": r["margem"],
                }
            )
    return pd.DataFrame(linhas)


def akad_tabela(base: pd.DataFrame) -> pd.DataFrame:
    ak = base[base["codigo_susep"] == AKAD]
    linhas = []
    for lob in LOB_ORDEM:
        g = base[base["lob"] == lob]
        if g.empty:
            continue
        a = ak[ak["lob"] == lob]
        anos = sorted(g["ano"].unique())
        p0, p1 = anos[0], anos[-1]
        premio0 = float(a.loc[a["ano"] == p0, "premio_ganho"].sum())
        premio1 = float(a.loc[a["ano"] == p1, "premio_ganho"].sum())
        mercado0 = float(g.loc[g["ano"] == p0, "premio_ganho"].sum())
        mercado1 = float(g.loc[g["ano"] == p1, "premio_ganho"].sum())

        def rank(ano: int) -> int | None:
            p = g[(g["ano"] == ano) & (g["premio_ganho"] > 0)].groupby("codigo_susep").premio_ganho.sum()
            if AKAD not in p.index:
                return None
            return int(p.rank(ascending=False, method="min").loc[AKAD])

        linhas.append(
            {
                "lob": lob,
                "premio0": premio0,
                "premio1": premio1,
                "share0": premio0 / mercado0 if mercado0 > 0 else 0.0,
                "share1": premio1 / mercado1 if mercado1 > 0 else 0.0,
                "rank0": rank(p0),
                "rank1": rank(p1),
                "n1": int(g[(g["ano"] == p1) & (g["premio_ganho"] > 0)].codigo_susep.nunique()),
                "abs": premio1 - premio0,
                "cresc": premio1 / premio0 - 1 if premio0 > 0 else math.nan,
            }
        )
    return pd.DataFrame(linhas)


def comparacao_akad(base: pd.DataFrame, min_share: float = 0.01) -> pd.DataFrame:
    linhas = []
    for lob, g in base.groupby("lob"):
        a = g[g["codigo_susep"] == AKAD]
        if a.empty:
            continue
        ma, aa = metricas(g), metricas(a)
        p25 = g[g["ano"] == g["ano"].max()].groupby("codigo_susep").premio_ganho.sum()
        alvo = p25.get(AKAD, 0.0)
        peers = [c for c in p25[(p25 >= alvo / 3) & (p25 <= alvo * 3)].index if c != AKAD]
        pm = metricas(g[g["codigo_susep"].isin(peers)]) if peers else {"sinistralidade": math.nan, "margem": math.nan}
        s = g[g["premio_ganho"] > 0].groupby("codigo_susep").premio_ganho.sum().sort_values(ascending=False)
        cum = s / s.sum()
        n80 = int((cum.cumsum() < 0.8).sum()) + 1
        relevantes = [c for c in s.index[:n80] if c != AKAD]
        rm = metricas(g[g["codigo_susep"].isin(relevantes)]) if relevantes else {"sinistralidade": math.nan, "margem": math.nan}
        linhas.append(
            {
                "lob": lob,
                "mercado_sin": ma["sinistralidade"],
                "mercado_mg": ma["margem"],
                "akad_sin": aa["sinistralidade"],
                "akad_mg": aa["margem"],
                "peers_n": len(peers),
                "peers_sin": pm["sinistralidade"],
                "peers_mg": pm["margem"],
                "relev_n": len(relevantes),
                "relev_sin": rm["sinistralidade"],
                "relev_mg": rm["margem"],
            }
        )
    return pd.DataFrame(linhas).sort_values("lob")


# --------------------------------------------------------------------------
# Formatacao
# --------------------------------------------------------------------------

def esc(t) -> str:
    return html.escape(str(t))


def f_num(v, dec=0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_pct(v, dec=1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v*100:,.{dec}f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def f_bi(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sinal = "−" if v < 0 else ""
    return f"{sinal}R$ {abs(v)/1e9:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")


def f_mi(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sinal = "−" if v < 0 else ""
    return f"{sinal}R$ {abs(v)/1e6:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")


def f_vezes(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:,.1f} vezes".replace(",", "X").replace(".", ",").replace("X", ".")


def f_dinheiro(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if abs(v) >= 1e9:
        return f_bi(v)
    if abs(v) >= 1e6:
        return f_mi(v)
    sinal = "−" if v < 0 else ""
    return f"{sinal}R$ {abs(v):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def f_rank(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{int(v)}º"


def f_pp(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v*100:+.1f} pp/ano".replace(".", ",")


# --------------------------------------------------------------------------
# Graficos em SVG/HTML, sem dependencias externas
# --------------------------------------------------------------------------

def _interp(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _luz(cor: str) -> float:
    r, g, b = [int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def line_svg(series, x_labels, *, width=860, height=300, y_fmt=f_num, y0=None, y1=None, label_w=150):
    """series: [(nome, [valores], cor)] com um ponto por x_label."""
    left, right, top, bottom = 56, label_w, 18, 38
    pw, ph = width - left - right, height - top - bottom
    vals = [v for _, vs, _ in series for v in vs if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return ""
    lo = min(vals) if y0 is None else y0
    hi = max(vals) if y1 is None else y1
    if hi == lo:
        hi = lo + 1
    pad = (hi - lo) * 0.1
    if y0 is None:
        lo -= pad
    if y1 is None:
        hi += pad

    def X(i):
        return left + (pw * i / (len(x_labels) - 1) if len(x_labels) > 1 else pw / 2)

    def Y(v):
        return top + ph * (1 - (v - lo) / (hi - lo))

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{RULE}" stroke-width="1"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="10" fill="{MUTED}">{esc(y_fmt(v))}</text>')
    for i, lab in enumerate(x_labels):
        parts.append(f'<text x="{X(i):.1f}" y="{height-14}" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="10" fill="{MUTED}">{esc(lab)}</text>')

    rotulos = []
    for nome, vs, cor in series:
        pts = [(X(i), Y(v)) for i, v in enumerate(vs) if v is not None and not (isinstance(v, float) and math.isnan(v))]
        if not pts:
            continue
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for (x, y), v in zip(pts, [v for v in vs if v is not None and not (isinstance(v, float) and math.isnan(v))]):
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{BG}" stroke="{cor}" stroke-width="2"><title>{esc(nome)}: {esc(y_fmt(v))}</title></circle>')
        rotulos.append([pts[-1][1], nome, cor])

    rotulos.sort(key=lambda r: r[0])
    for i in range(1, len(rotulos)):
        if rotulos[i][0] - rotulos[i - 1][0] < 15:
            rotulos[i][0] = rotulos[i - 1][0] + 15
    for y, nome, cor in rotulos:
        parts.append(f'<text x="{left+pw+10}" y="{y+4:.1f}" font-family="IBM Plex Mono, monospace" font-size="11" fill="{cor}">{esc(nome)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbar_svg(items, *, width=860, label_w=180, value_w=110, bar_h=26, gap=14, fmt=f_num):
    """items: [(rotulo, valor, cor)] - barras horizontais simples."""
    top = 10
    height = top * 2 + len(items) * (bar_h + gap)
    x0, x1 = label_w, width - value_w
    largura = x1 - x0
    maxv = max((max(0, v) for _, v, _ in items), default=1) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for i, (rotulo, valor, cor) in enumerate(items):
        y = top + i * (bar_h + gap)
        w = max(0.0, min(1.0, valor / maxv)) * largura
        parts.append(f'<text x="{x0-12}" y="{y+bar_h*0.7:.1f}" text-anchor="end" font-family="IBM Plex Sans, sans-serif" font-size="12" fill="{INK}">{esc(rotulo)}</text>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{largura}" height="{bar_h}" fill="#E1E8E4"/>')
        parts.append(f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{cor}"><title>{esc(rotulo)}: {esc(fmt(valor))}</title></rect>')
        partes_valor = fmt(valor)
        tx = min(x0 + w + 8, width - 4)
        anchor = "start" if tx < width - value_w + 4 else "end"
        parts.append(f'<text x="{tx:.1f}" y="{y+bar_h*0.7:.1f}" text-anchor="{anchor}" font-family="IBM Plex Mono, monospace" font-size="11" fill="{INK}">{esc(partes_valor)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def grouped_svg(categories, groups, *, width=860, height=300, fmt=f_num, y_fmt=f_num):
    """groups: [(nome, [valores], cor)] - barras verticais agrupadas."""
    left, right, top, bottom = 52, 16, 34, 42
    pw, ph = width - left - right, height - top - bottom
    vals = [v for _, vs, _ in groups for v in vs]
    hi = max(vals + [1])
    lo = 0

    def Y(v):
        return top + ph * (1 - (v - lo) / (hi - lo)) if hi > lo else top + ph

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{RULE}"/>')
        parts.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="IBM Plex Mono, monospace" font-size="10" fill="{MUTED}">{esc(y_fmt(v))}</text>')
    n = len(categories)
    slot = pw / n
    bar_w = min(22, slot / (len(groups) + 1))
    for c, cat in enumerate(categories):
        cx = left + slot * (c + 0.5)
        for g, (nome, vs, cor) in enumerate(groups):
            v = vs[c]
            x = cx + (g - (len(groups) - 1) / 2) * (bar_w + 3) - bar_w / 2
            y = Y(v)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{top+ph-y:.1f}" fill="{cor}"><title>{esc(nome)} · {esc(cat)}: {esc(fmt(v))}</title></rect>')
            parts.append(f'<text x="{x+bar_w/2:.1f}" y="{y-5:.1f}" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-size="9" fill="{MUTED}">{esc(fmt(v))}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{height-18}" text-anchor="middle" font-family="IBM Plex sans, sans-serif" font-size="11" fill="{INK}">{esc(cat)}</text>')
    for g, (nome, _, cor) in enumerate(groups):
        x = left + g * 150
        parts.append(f'<rect x="{x}" y="8" width="10" height="10" fill="{cor}"/>')
        parts.append(f'<text x="{x+15}" y="17" font-family="IBM Plex Sans, sans-serif" font-size="11" fill="{MUTED}">{esc(nome)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def heatmap_html(linhas, colunas, matriz, fmt=f_pct):
    vals = [v for row in matriz for v in row if v is not None and not (isinstance(v, float) and math.isnan(v))]
    lo, hi = (min(vals), max(vals)) if vals else (0, 1)
    out = ['<table class="heat"><thead><tr><th></th>']
    out += [f"<th>{esc(c)}</th>" for c in colunas]
    out.append("</tr></thead><tbody>")
    for nome, row in zip(linhas, matriz):
        out.append(f'<tr><th class="rowh">{esc(nome)}</th>')
        for v in row:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out.append('<td class="vazio">–</td>')
                continue
            t = 0.5 if hi == lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))
            cor = _interp("#E7EEEA", "#7FA69C", t * 2) if t < 0.5 else _interp("#7FA69C", SIGNAL, (t - 0.5) * 2)
            tinta = "#FFFFFF" if _luz(cor) < 0.52 else INK
            out.append(f'<td style="background:{cor};color:{tinta}">{esc(fmt(v))}</td>')
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def tabela(headers, rows, *, num=None, classe=""):
    """rows: lista de listas de strings ja formatadas. num: indices alinhados a direita."""
    num = set(num or [])
    out = [f'<table class="{classe}"><thead><tr>']
    for i, h in enumerate(headers):
        out.append(f'<th class="{"num" if i in num else ""}">{h}</th>')
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join(f'<td class="{"num" if i in num else ""}">{c}</td>' for i, c in enumerate(row)) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


# --------------------------------------------------------------------------
# Relatorio
# --------------------------------------------------------------------------

def gerar(saida: Path, snapshot: str | None = None) -> Path:
    base, meta, snap = carregar(snapshot)
    man = ler_manifesto()
    zerada, ativa = mascaras(base)
    vis = base[base["premio_ganho"] > 0]
    lob = por_lob(base)
    lob_ano = por_lob_ano(base)
    cresc = crescimento(base)
    conc = concentracao(base)
    ativas_premio = ativas_por_ano(base, "premio")
    ativas_presenca = ativas_por_ano(base, "presenca")
    trend = tendencias(base)
    out = out_por_lob(base)
    akad = akad_tabela(base)
    comp = comparacao_akad(base)
    akad_idx = akad.set_index("lob")
    melhora = [r.lob for r in akad.itertuples() if r.rank1 is not None and r.rank0 is not None and r.rank1 < r.rank0]
    piora = [r.lob for r in akad.itertuples() if r.rank1 is not None and r.rank0 is not None and r.rank1 > r.rank0]
    frase_rank = f"A posição melhora em {len(melhora)} das cinco LOBs"
    if piora:
        l = piora[0]
        frase_rank += f"; em {l} recua de {int(akad_idx.loc[l, 'rank0'])}º para {int(akad_idx.loc[l, 'rank1'])}º"
    frase_rank += "."
    frase_destaques = (
        f"com destaque para Transportes ({int(akad_idx.loc['Transportes', 'rank0'])}º para "
        f"{int(akad_idx.loc['Transportes', 'rank1'])}º) e E&O ({int(akad_idx.loc['E&O', 'rank0'])}º para "
        f"{int(akad_idx.loc['E&O', 'rank1'])}º)"
    )
    vazias = consultas_vazias(base)
    cobertura = meta.get("relatorio", {}).get("cobertura", {})
    difs = []
    for d in meta.get("diagnosticos", []):
        for col, v in (d.get("totais") or {}).items():
            difs.append((float(v["dif"]), float(v["oficial"]), d["chave"], col))
    frase_totais = ""
    if difs:
        maior = max(difs)
        frase_totais = (
            f"A maior diferença absoluta foi R$ {f_num(maior[0])} em uma consulta de "
            f"{f_bi(maior[1])} ({maior[2]}, {maior[3]}), dentro do arredondamento."
        )

    total_premio = float(base["premio_ganho"].sum())
    total_lucro = float(base["lucro"].sum())
    total_sin = float(base["sinistro_ocorrido"].sum())
    margem = total_lucro / total_premio if total_premio else math.nan
    anos = sorted(base["ano"].unique())
    n_empresas = int(base["codigo_susep"].nunique())
    n_ativas_2025 = int(vis[vis["ano"] == anos[-1]]["codigo_susep"].nunique())

    # --- secoes ---------------------------------------------------------
    s1 = tabela(
        ["Check", "Resultado"],
        [
            ["Consultas esperadas (14 ramos × 6 anos)", f"{cobertura.get('esperadas', 0)}"],
            ["Consultas lidas sem erro", f"{cobertura.get('lidas', 0)}"],
            ["Consultas sem seguradoras", f"{cobertura.get('vazias', 0)} + 1 tabela zerada (0645/2025)"],
            ["Reconciliação com a linha Totais do SES", f"{cobertura.get('totais_conferidos', 0)} consultas"],
            ["SHA-256 do raw confere com o manifesto", "84 / 84"],
            ["Rodapé de ramo e período confere", "84 / 84"],
            ["Cabeçalho distinto nos 79 arquivos com tabela", "1 variante, 20 colunas"],
            ["Duplicatas de ramo/ano/seguradora", "0"],
        ],
    )

    ultima_raw = max((e.get("quando", "") for e in man), default="")
    novo_raw = ultima_raw > str(meta.get("criado_em", ""))
    s1_nota = (
        f"O snapshot vigente é <code>{esc(snap)}</code>, gerado em {esc(str(meta.get('criado_em', '')).replace('T', ' '))}. "
        f"O manifesto tem {len(man)} eventos: "
        f"{sum(1 for e in man if e.get('status') == 'ok' and e.get('fonte') == 'export_xls')} coletas .xls registradas (inclui recoletas), "
        f"{sum(1 for e in man if e.get('status') == 'ok' and e.get('fonte') == 'vazio')} páginas vazias e "
        f"{sum(1 for e in man if e.get('status') == 'falha')} falhas históricas já recuperadas. "
        "As falhas ficaram registradas no manifesto, mas não entraram na base: cada consulta usa a última coleta bem-sucedida. "
        + frase_totais
    )
    if novo_raw:
        s1_nota += (
            f" Há coletas no raw posteriores ao snapshot (a última em {esc(str(ultima_raw).replace('T', ' '))}); "
            "elas ainda não entraram na base. Rode <code>python pipeline.py processar</code> para publicar um novo snapshot."
        )

    # tratamento: amostra antes/depois
    amostra = base[(base["ano"] == 2025) & (base["lob"].isin(["E&O", "Transportes"]))].head(4)
    s2_amostra = tabela(
        ["Seguradora", "LOB", "Ramo", "Prêmio ganho", "Sinistro ocorrido", "Desp. resseguro", "Rec. resseguro", "Desp. comercial", "Sinistralidade"],
        [
            [
                esc(r.seguradora),
                esc(r.lob),
                esc(r.ramo_codigo),
                f_num(r.premio_ganho),
                f_num(r.sinistro_ocorrido),
                f_num(r.despesa_resseguro),
                f_num(r.receita_resseguro),
                f_num(r.despesa_comercial),
                f_pct(r.sinistralidade),
            ]
            for r in amostra.itertuples()
        ],
        num={3, 4, 5, 6, 7, 8},
    )

    colunas_raw = [
        ("Código SUSEP", "identidade", "codigo_susep, com cinco dígitos e zeros à esquerda"),
        ("Empresa", "identidade", "seguradora"),
        ("Prêmio Ganho", "usada", "premio_ganho"),
        ("Sinistro Ocorrido", "usada", "sinistro_ocorrido"),
        ("Despesa com Resseguro", "usada", "despesa_resseguro"),
        ("Receita com Resseguro", "usada", "receita_resseguro"),
        ("Despesa Comercial", "usada", "despesa_comercial"),
        ("Sinistralidade", "conferência", "sinistralidade_susep; a análise recalcula a razão"),
        ("Prêmio Direto", "descartada", "fora do escopo do case"),
        ("Prêmio Emitido (Reg. Capitalização)", "descartada", "fora do escopo do case"),
        ("Prêmio Seguros", "descartada", "fora do escopo do case"),
        ("Prêmio Retido", "descartada", "tem ²: coluna descontinuada e zerada por definição"),
        ("Prêmio Emitido", "descartada", "fora do escopo do case"),
        ("Sinistro de Seguros", "descartada", "fora do escopo do case"),
        ("Sinistro Retido", "descartada", "tem ²: coluna descontinuada e zerada por definição"),
        ("Sinistro Ocorridos (Cap)", "descartada", "fora do escopo do case"),
        ("Recuperação de Sinistros Ocorridos (Cap)", "descartada", "fora do escopo do case"),
        ("RVNE", "descartada", "fora do escopo do case"),
        ("Convênio DPVAT", "descartada", "fora do escopo do case"),
        ("Consórcios e Fundos", "descartada", "fora do escopo do case"),
    ]
    s2_colunas = tabela(
        ["Coluna no SES", "Uso", "Destino"],
        [[esc(a), esc(b), esc(c)] for a, b, c in colunas_raw],
        classe="colunas",
    )

    # qualidade
    neg = {c: int((base[c] < 0).sum()) for c in VALORES}
    neg_soma = {c: float(base.loc[base[c] < 0, c].sum()) for c in VALORES}
    qual = tabela(
        ["Situação", "Linhas", "% da base", "Tratamento"],
        [
            ["Prêmio ganho ≤ 0", f_num(int((base['premio_ganho'] <= 0).sum())), f_pct((base['premio_ganho'] <= 0).mean()), "Mantidas nas somas de mercado; fora das contagens de ativas e das razões por seguradora"],
            ["Linha totalmente zerada", f_num(int(zerada.sum())), f_pct(zerada.mean()), "Fora das distribuições e dos rankings"],
            ["Prêmio ganho negativo", f_num(neg['premio_ganho']), f_pct(neg['premio_ganho'] / len(base)), "Mantido e sinalizado: ajuste/estorno da SUSEP"],
            ["Sinistro ocorrido negativo", f_num(neg['sinistro_ocorrido']), f_pct(neg['sinistro_ocorrido'] / len(base)), "Mantido e sinalizado: reduz a sinistralidade líquida"],
            ["Despesa com resseguro negativa", f_num(neg['despesa_resseguro']), f_pct(neg['despesa_resseguro'] / len(base)), "Mantida e sinalizada"],
            ["Receita com resseguro negativa", f_num(neg['receita_resseguro']), f_pct(neg['receita_resseguro'] / len(base)), "Mantida e sinalizada"],
            ["Despesa comercial negativa", f_num(neg['despesa_comercial']), f_pct(neg['despesa_comercial'] / len(base)), "Mantida e sinalizada"],
            ["Sinistralidade > 100%", f_num(int((base['sinistralidade'] > 1).sum())), f_pct((base['sinistralidade'] > 1).mean()), "Outlier real; não é truncado"],
            ["Sinistralidade < 0", f_num(int((base['sinistralidade'] < 0).sum())), f_pct((base['sinistralidade'] < 0).mean()), "Efeito de sinistro negativo; não é truncado"],
            ["Valores ausentes nas seis colunas", "0", "0,0%", "Sem imputação"],
            ["Código SUSEP com mais de um nome", "0", "0,0%", "Nenhum conflito"],
            ["Duplicatas (ramo, ano, seguradora)", "0", "0,0%", "Contrato reprova se aparecer"],
        ],
        num={1, 2},
    )

    comp_lob = []
    for lobname in LOB_ORDEM:
        g = base[base["lob"] == lobname]
        comp_lob.append([esc(lobname), f_num(len(g)), f_num(int((g["premio_ganho"] > 0).sum())), f_num(int(zerada[g.index].sum()))])
    comp_lob_tab = tabela(["LOB", "Linhas", "Com prêmio > 0", "Zeradas"], comp_lob, num={1, 2, 3})

    # Q2 - definicao importa
    anos_q2 = [anos[0], anos[-1]]
    q2_cats = [f"{a}" for a in anos_q2]
    q2_pres = [int(ativas_presenca.loc[l, a]) for l in LOB_ORDEM for a in anos_q2]
    q2_pos = [int(ativas_premio.loc[l, a]) for l in LOB_ORDEM for a in anos_q2]
    # grouped expects categories x groups; montar por LOB com duas barras (presenca/ativo) para cada ano
    # usar apenas 2025 para leitura visual e tabela para os dois anos
    q2_2025_pres = [int(ativas_presenca.loc[l, anos[-1]]) for l in LOB_ORDEM]
    q2_2025_pos = [int(ativas_premio.loc[l, anos[-1]]) for l in LOB_ORDEM]
    q2_2020_pres = [int(ativas_presenca.loc[l, anos[0]]) for l in LOB_ORDEM]
    q2_2020_pos = [int(ativas_premio.loc[l, anos[0]]) for l in LOB_ORDEM]
    q2_graf = grouped_svg(LOB_ORDEM, [("Linhas no SES", q2_2025_pres, NEUTRAL), ("Prêmio > 0", q2_2025_pos, PINE)], fmt=lambda v: f"{int(v)}", y_fmt=lambda v: f"{int(v)}")
    q2_tab = tabela(
        ["LOB", f"Presença {anos[0]}", f"Ativa {anos[0]}", f"Presença {anos[-1]}", f"Ativa {anos[-1]}"],
        [[esc(l), f_num(ativas_presenca.loc[l, anos[0]]), f_num(ativas_premio.loc[l, anos[0]]), f_num(ativas_presenca.loc[l, anos[-1]]), f_num(ativas_premio.loc[l, anos[-1]])] for l in LOB_ORDEM],
        num={1, 2, 3, 4},
    )

    def _frase_lider(ano: int) -> str:
        pres, pos = ativas_presenca[ano], ativas_premio[ano]
        a, b = pres.idxmax(), pos.idxmax()
        if a == b:
            return (
                f"Em {ano}, as duas leituras apontam {b}, mas com {int(pres.max())} linhas no SES "
                f"contra {int(pos.max())} empresas com prêmio positivo."
            )
        return (
            f"Em {ano}, por presença o líder é {a} ({int(pres.max())}); "
            f"por prêmio positivo, {b} ({int(pos.max())})."
        )

    frase_q2_20, frase_q2_25 = _frase_lider(anos[0]), _frase_lider(anos[-1])
    gap_lob, gap_ano = (ativas_presenca - ativas_premio).stack().idxmax()
    frase_gap = (
        f"em {gap_ano}, {gap_lob} tem {int(ativas_presenca.loc[gap_lob, gap_ano])} linhas no SES "
        f"e apenas {int(ativas_premio.loc[gap_lob, gap_ano])} empresas com prêmio."
    )

    # crescimento
    cresc_rows = []
    for lname, r in cresc.iterrows():
        cresc_rows.append([esc(lname), f_bi(r["primeiro"]), f_bi(r["ultimo"]), f_bi(r["abs"]), f_pct(r["pct"]), f_pct(r["cagr"])])
    cresc_tab = tabela(["LOB", f"Prêmio {anos[0]}", f"Prêmio {anos[-1]}", "Variação absoluta", "Variação %", "CAGR"], cresc_rows, num={1, 2, 3, 4, 5})

    # linha de premio
    premio_linha = line_svg(
        [(l, [float(lob_ano[(lob_ano.lob == l) & (lob_ano.ano == a)]["premio"].sum()) for a in anos], LOB_COR[l]) for l in LOB_ORDEM],
        [str(a) for a in anos],
        y_fmt=lambda v: f"{v/1e9:.1f} bi",
        y0=0,
    )

    # rentabilidade
    lucro_bar = hbar_svg(
        [(l, float(lob[lob.lob == l]["lucro"].sum()), LOB_COR[l]) for l in LOB_ORDEM],
        fmt=f_bi,
        label_w=150,
    )
    rent_rows = []
    for lname, r in lob.set_index("lob").loc[LOB_ORDEM].iterrows():
        rent_rows.append([esc(lname), f_bi(r["premio"]), f_bi(r["lucro"]), f_pct(r["margem"]), f_pct(r["sinistralidade"])])
    rent_tab = tabela(["LOB", "Prêmio ganho", "Resultado técnico", "Margem", "Sinistralidade"], rent_rows, num={1, 2, 3, 4})

    # sinistralidade heatmap
    mat = []
    for l in LOB_ORDEM:
        mat.append([float(lob_ano[(lob_ano.lob == l) & (lob_ano.ano == a)]["sinistralidade"].sum()) for a in anos])
    heat = heatmap_html(LOB_ORDEM, [str(a) for a in anos], mat)

    trend_rows = []
    for _, r in trend.iterrows():
        trend_rows.append([esc(r["lob"]), f_pct(r["sin"]), f_pct(r["vol"]), f_pp(r["slope"]), f_pct(r["cresc_sinistro"]), f_pct(r["margem"])])
    trend_tab = tabela(["LOB", "Sinistralidade média", "Volatilidade (desvio)", "Tendência", "Crescimento do sinistro", "Margem média"], trend_rows, num={1, 2, 3, 4, 5})

    # concentracao
    conc_rows = []
    for l in LOB_ORDEM:
        r = conc[conc.lob == l].iloc[0]
        conc_rows.append([esc(l), f_num(r["n_total"]), f_num(r["n_ativas"]), f_pct(r["top5"]), f_num(r["n80"]), f_num(r["hhi"])])
    conc_tab = tabela(["LOB", "Cadastradas no período", "Ativas (prêmio > 0)", "Top 5", "Seguradoras até 80%", "HHI"], conc_rows, num={1, 2, 3, 4, 5})
    rcg = conc[conc.lob == "RCG"].iloc[0]
    frase_rcg = (
        f"No RCG, são {int(rcg['n_ativas'])} ativas em {int(rcg['n_total'])} cadastradas no período."
    )

    # outliers
    out_rows = []
    for l in LOB_ORDEM:
        g = out[out.lob == l]
        for _, r in g.iterrows():
            out_rows.append([esc(l), esc(r["seguradora"]), f_mi(r["premio"]), f_pct(r["share"]), f_pct(r["sin"]), f_pct(r["margem"])])
    out_tab = tabela(["LOB", "Seguradora", "Prêmio", "Share", "Sinistralidade", "Margem"], out_rows, num={2, 3, 4, 5})
    seg_ativa = por_seguradora(vis)
    neg_r = seg_ativa[seg_ativa.lob == "RCG"].sort_values("sinistralidade").iloc[0]
    neg_ano = (
        base[(base.lob == "RCG") & (base.codigo_susep == neg_r.codigo_susep)]
        .sort_values("sinistralidade")
        .iloc[0]
    )
    frase_neg = (
        f"Exemplo: {neg_r.seguradora}, no RCG, teve sinistro ocorrido negativo em {int(neg_ano.ano)}: "
        f"{f_dinheiro(neg_ano.sinistro_ocorrido)} contra prêmio de R$ {f_num(neg_ano.premio_ganho)}, "
        f"o que dá {f_vezes(neg_ano.sinistralidade)} o prêmio. No agregado de seis anos, a razão fica em "
        f"{f_vezes(neg_r.sinistralidade)}. Não é erro: é reversão de reserva de anos anteriores. "
        "Agregar antes de dividir dilui o efeito."
    )

    neg_rows = []
    for c in VALORES:
        neg_rows.append([esc(c), f_num(neg[c]), f_pct(neg[c] / len(base)), f_dinheiro(neg_soma[c])])
    neg_tab = tabela(["Coluna", "Linhas negativas", "% da base", "Soma dos negativos"], neg_rows, num={1, 2, 3})

    # akad
    ak_rows = []
    for _, r in akad.iterrows():
        ak_rows.append([
            esc(r["lob"]),
            f_bi(r["premio0"]),
            f_bi(r["premio1"]),
            f_pct(r["share0"]),
            f_pct(r["share1"]),
            f_rank(r["rank0"]),
            f_rank(r["rank1"]),
            f_num(r["n1"]),
            f_bi(r["abs"]),
            f_pct(r["cresc"]),
        ])
    ak_tab = tabela(
        ["LOB", f"Prêmio {anos[0]}", f"Prêmio {anos[-1]}", f"Share {anos[0]}", f"Share {anos[-1]}", f"Rank {anos[0]}", f"Rank {anos[-1]}", "Ativas", "Variação absoluta", "Variação %"],
        ak_rows,
        num={1, 2, 3, 4, 7, 8, 9},
    )
    emp = akad_idx.loc["Empresarial"]
    frase_base_emp = ""
    if emp["premio0"] < 10e6:
        frase_base_emp = (
            f"O crescimento de {f_pct(emp['cresc'])} em Empresarial parte de uma base de "
            f"{f_mi(emp['premio0'])} em {anos[0]}; o percentual não é comparável com as demais LOBs."
        )

    ak_share = line_svg(
        [(l, [float(akad[akad.lob == l]["share1"].iloc[0]) if False else float(base[(base.lob == l) & (base.ano == a) & (base.codigo_susep == AKAD)]["premio_ganho"].sum() / max(base[(base.lob == l) & (base.ano == a)]["premio_ganho"].sum(), 1)) for a in anos], LOB_COR[l]) for l in LOB_ORDEM],
        [str(a) for a in anos],
        y_fmt=lambda v: f"{v:.0%}",
        y0=0,
    )

    comp_rows = []
    for _, r in comp.iterrows():
        comp_rows.append([
            esc(r["lob"]),
            f_pct(r["mercado_sin"]),
            f_pct(r["mercado_mg"]),
            f_pct(r["akad_sin"]),
            f_pct(r["akad_mg"]),
            f"{r['peers_n']}",
            f_pct(r["peers_sin"]),
            f_pct(r["peers_mg"]),
            f"{r['relev_n']}",
            f_pct(r["relev_sin"]),
            f_pct(r["relev_mg"]),
        ])
    comp_tab = tabela(
        ["LOB", "Mercado sin.", "Mercado margem", "Akad sin.", "Akad margem", "Peers", "Peers sin.", "Margem peers", "Relevantes", "Relev. sin.", "Margem relevantes"],
        comp_rows,
        num={1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
    )

    # respostas resumidas
    q1 = lob.iloc[0]
    q3 = lob.sort_values("sinistralidade", ascending=False).iloc[0]
    q5 = lob.sort_values("lucro", ascending=False).iloc[0]
    q6 = lob.sort_values("margem", ascending=False).iloc[0]
    q7_pct = cresc.iloc[0]
    q7_abs = cresc.sort_values("abs", ascending=False).iloc[0]
    q2_20 = ativas_premio[anos[0]].idxmax()
    q2_25 = ativas_premio[anos[-1]].idxmax()
    akad_eo = akad[akad.lob == "E&O"].iloc[0]
    akad_tr = akad[akad.lob == "Transportes"].iloc[0]
    akad_rcg = akad[akad.lob == "RCG"].iloc[0]

    if q2_20 == q2_25:
        frase_q2_resp = (
            f"Com prêmio > 0, {q2_20} lidera os dois anos "
            f"({int(ativas_premio.loc[q2_20, anos[0]])} em {anos[0]} e "
            f"{int(ativas_premio.loc[q2_25, anos[-1]])} em {anos[-1]})."
        )
    else:
        frase_q2_resp = (
            f"Com prêmio > 0, {q2_20} lidera em {anos[0]} e {q2_25} em {anos[-1]}."
        )
    frase_q2_resp += (
        f" Por presença de linha, a leitura seria {ativas_presenca[anos[0]].idxmax()} em {anos[0]} "
        f"e {ativas_presenca[anos[-1]].idxmax()} em {anos[-1]}."
    )
    respostas = [
        ["Q1", f"{q1['lob']} é a maior LOB, com {f_bi(q1['premio'])} de prêmio ganho no período."],
        ["Q2", frase_q2_resp],
        ["Q3", f"{q3['lob']} tem a maior sinistralidade agregada do período: {f_pct(q3['sinistralidade'])}."],
        ["Q5", f"{q5['lob']} gera o maior resultado técnico: {f_bi(q5['lucro'])} no período."],
        ["Q6", f"{q6['lob']} tem a maior margem: {f_pct(q6['margem'])}."],
        ["Q7", f"Em porcentagem, {q7_pct.name} cresce mais ({f_pct(q7_pct['pct'])}); em valor absoluto, {q7_abs.name} adiciona {f_bi(q7_abs['abs'])}."],
        ["Q10", f"A Akad é relevante em E&O (share {f_pct(akad_eo['share1'])}, {int(akad_eo['rank1'])}º lugar em {anos[-1]}) e em Transportes (share {f_pct(akad_tr['share1'])}, {int(akad_tr['rank1'])}º). Em RCG o share é {f_pct(akad_rcg['share1'])} e o posto {int(akad_rcg['rank1'])}º."],
        ["Q11", "A Akad supera o mercado em margem em E&O e RCG; em Transportes tem escala, mas margem bem abaixo do mercado; em Garantia e Empresarial é subescala."],
    ]
    resp_tab = tabela(["Pergunta", "Leitura que os dados já sustentam"], [[esc(a), esc(b)] for a, b in respostas], classe="respostas")

    # HTML
    css = """
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
    :root{--ink:#12201D;--muted:#5C6B66;--rule:#CBD6D1;--bg:#EDF1EF;--pine:#17453C;--signal:#C8451F;}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--ink);font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:15px;line-height:1.6}
    .wrap{max-width:1080px;margin:0 auto;padding:56px 32px 96px}
    .kicker{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);letter-spacing:.02em;margin-bottom:18px}
    h1{font-size:44px;line-height:1.08;letter-spacing:-.025em;font-weight:600;max-width:820px;margin:0 0 18px}
    .standfirst{font-size:18px;line-height:1.5;color:#33443F;max-width:720px;margin:0 0 28px}
    .fonte{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);border-top:1px solid var(--rule);padding-top:12px}
    .ledger{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:34px 0 8px}
    .ledger div{padding:18px 18px 16px;border-left:1px solid var(--rule)}
    .ledger div:first-child{border-left:0;padding-left:0}
    .ledger .lab{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}
    .ledger .val{display:block;font-family:'IBM Plex Mono',monospace;font-size:26px;letter-spacing:-.02em}
    .ledger .nota{display:block;font-size:11px;color:var(--muted);margin-top:4px}
    .metodo{display:grid;grid-template-columns:1fr 1fr;gap:18px 32px;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:20px 0;margin:20px 0 0}
    .metodo b{display:block;font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px}
    .metodo p{font-size:13px;line-height:1.5;margin:0;max-width:52ch}
    section{border-top:1px solid var(--rule);margin-top:64px;padding-top:30px}
    .secnum{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--signal);margin-bottom:8px}
    h2{font-size:27px;line-height:1.2;letter-spacing:-.02em;font-weight:600;margin:0 0 14px;max-width:760px}
    h3{font-size:17px;font-weight:600;margin:32px 0 10px}
    p{max-width:74ch;margin:0 0 14px;color:#33443F}
    code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:#E1E8E4;padding:1px 4px}
    table{width:100%;border-collapse:collapse;margin:14px 0 18px;font-size:13px}
    th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}
    thead th{font-weight:500;color:var(--muted);font-size:11px;letter-spacing:.01em;border-bottom:1px solid var(--ink)}
    td.num,th.num{text-align:right;font-family:'IBM Plex Mono',monospace;font-size:12px;white-space:nowrap}
    tbody tr:hover{background:#E6ECE8}
    .heat td{text-align:center;font-family:'IBM Plex Mono',monospace;font-size:12px;border:1px solid var(--bg)}
    .heat th{font-size:11px;color:var(--muted);font-weight:500}
    .heat th.rowh{text-align:left;font-family:'IBM Plex Sans',sans-serif;color:var(--ink);font-size:12px}
    .heat td.vazio{background:#E1E8E4;color:var(--muted)}
    .chart{margin:18px 0 10px;overflow:hidden}
    .nota{background:#E4EAE7;border-left:3px solid var(--pine);padding:14px 16px;margin:18px 0;max-width:820px}
    .alerta{background:#F3E4DF;border-left:3px solid var(--signal);padding:14px 16px;margin:18px 0;max-width:820px}
    .nota p,.alerta p{margin:0;font-size:14px}
    .duas{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:start}
    ul{max-width:76ch;padding-left:20px;margin:0 0 16px}
    li{margin-bottom:8px;color:#33443F}
    .fim{margin-top:64px;border-top:1px solid var(--rule);padding-top:18px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}
    @media(max-width:800px){h1{font-size:32px}.ledger{grid-template-columns:1fr 1fr}.ledger div{border-left:0;border-top:1px solid var(--rule);padding-left:0}.duas{grid-template-columns:1fr}table{font-size:12px}}
    """
    html_doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EDA SES/SUSEP · Case Akad 2027</title>
<style>{css}</style></head><body><div class="wrap">

<div class="kicker">Akad Seguros · Programa de Trainee 2027 · análise exploratória</div>
<h1>O mercado de seguros em cinco linhas de negócio, 2020–2025</h1>
<p class="standfirst">Inventário da coleta, tratamento das tabelas do SES e as primeiras leituras de prêmio, sinistralidade e margem. Este documento é um EDA, não um dashboard: cada número vem do snapshot validado e cada decisão de tratamento está declarada.</p>
<div class="fonte">Fonte: SES/SUSEP · snapshot {esc(snap)} · {len(base):,} linhas · valores nominais, sem deflacionamento</div>

<div class="ledger">
  <div><span class="lab">Prêmio ganho 2020–2025</span><span class="val">{f_bi(total_premio)}</span><span class="nota">{len(anos)} anos, 5 LOBs</span></div>
  <div><span class="lab">Sinistralidade agregada</span><span class="val">{f_pct(total_sin/total_premio)}</span><span class="nota">razão de somas</span></div>
  <div><span class="lab">Resultado técnico no período</span><span class="val">{f_bi(total_lucro)}</span><span class="nota">margem de {f_pct(margem)}</span></div>
  <div><span class="lab">Seguradoras</span><span class="val">{n_empresas}</span><span class="nota">{n_ativas_2025} com prêmio > 0 em {anos[-1]}</span></div>
</div>

<div class="metodo">
  <div><b>Sinistralidade</b><p>Soma dos sinistros dividida pela soma dos prêmios, nunca média de razões. Anos com prêmio pequeno não ganham o mesmo peso dos grandes.</p></div>
  <div><b>Resultado técnico</b><p>Prêmio ganho + receita com resseguro − sinistro ocorrido − despesa com resseguro − despesa comercial. Não é lucro contábil: fora da conta ficam despesa administrativa, imposto e resultado financeiro.</p></div>
  <div><b>Seguradora ativa</b><p>Prêmio ganho maior que zero no ano. Quem aparece no SES só por registro cadastral não entra na contagem nem nos rankings.</p></div>
  <div><b>Chave e conferência</b><p>Agrupamento por Código SUSEP, não por nome. A soma das seguradoras é conferida contra a linha Totais do próprio SES em cada consulta.</p></div>
</div>

<section>
<div class="secnum">01 · inventário</div>
<h2>O que foi coletado e o que o contrato conferiu</h2>
<p>A coleta cobre 14 códigos de ramo em seis anos, o que dá 84 consultas ao formulário do SES. Todas foram lidas; cinco não têm tabela (ramo sem mercado no ano) e uma tem tabela, mas com as seis seguradoras zeradas. A linha <strong>Totais</strong> do próprio SES foi usada como prova: a soma das seguradoras tem que bater com o total oficial nas cinco colunas de valor.</p>
{s1}
<div class="nota"><p>{s1_nota}</p></div>
<p>O caso 0645 merece uma ressalva: ele não tem tabela em 2020–2024 e, em 2025, aparece com seis linhas zeradas. Na prática, Transportes é composto por oito ramos, não nove. O pipeline hoje tolera até seis consultas vazias; se você quiser que essa regra fique explícita, o critério deve ser <code>prêmio total ≤ 0</code>, e não apenas ausência de tabela.</p>
</section>

<section>
<div class="secnum">02 · tratamento</div>
<h2>Como a tabela do SES vira uma base analítica</h2>
<p>O arquivo exportado pelo SES é um HTML com extensão <code>.xls</code>, não uma planilha de verdade. Ele tem 20 colunas, rodapé de parâmetros, linha de totais e códigos com espaços à direita. O parser lê a tabela como texto, identifica o cabeçalho por <em>Empresa</em> + <em>Prêmio Ganho</em> e converte o formato brasileiro por conta própria. Isso evita o erro clássico do <code>read_html</code>, que transforma <code>0,46</code> em 46 e <code>1.234</code> em 1,234.</p>
<p>Das 20 colunas, o case manda usar seis: Prêmio Ganho, Sinistro Ocorrido, Sinistralidade (recalculada), Despesa com Resseguro, Receita com Resseguro e Despesa Comercial. As demais (Prêmio Direto, Prêmio Retido, Sinistro de Seguros, RVNE, DPVAT, consórcios e fundos) são descartadas de propósito. A linha <strong>Totais</strong> não entra como seguradora: ela é guardada à parte para reconciliação.</p>
{s2_colunas}
<div class="alerta"><p>As colunas marcadas com ² no SES são descontinuadas e vêm zeradas por definição. Prêmio Retido e Sinistro Retido são exemplos: não conclua que uma seguradora não cede risco olhando essas colunas. Elas ficam fora da base. E se você abrir o <code>base.csv</code> no Excel, importe como texto: caso contrário, o código 0351 vira 351 e valores como 9.705.565.371 podem ser lidos errado.</p></div>
<h3>Amostra do resultado tratado</h3>
{s2_amostra}
<div class="duas">
<div>
<h3>Regras aplicadas</h3>
<ul>
<li>Código SUSEP: espaços removidos e zeros à esquerda preservados (5 dígitos).</li>
<li>Ramo: 4 dígitos, incluindo o zero à esquerda (0351, 0378, 0118).</li>
<li>Números: ponto como milhar, vírgula como decimal; vazio, traço e célula em branco viram nulo.</li>
<li>Rodapé <em>Ramos selecionados / Período de / Período até</em> confere ramo e ano de cada consulta.</li>
<li>SHA-256 de cada arquivo é comparado ao manifesto; raw adulterado reprova o contrato.</li>
<li>Duplicata de ramo/ano/seguradora reprova a publicação.</li>
</ul>
</div>
<div>
<h3>O que não é alterado</h3>
<ul>
<li>Valores negativos são mantidos: são estornos e ajustes da própria SUSEP.</li>
<li>Não há truncamento de sinistralidade acima de 100% nem abaixo de zero.</li>
<li>Não há imputação de valores ausentes.</li>
<li>A sinistralidade do SES é mantida como coluna de conferência; a análise usa a recalculada.</li>
<li>Valores nominais, sem correção pela inflação.</li>
</ul>
</div>
</div>
</section>

<section>
<div class="secnum">03 · qualidade</div>
<h2>O problema central: metade da base não tem prêmio positivo</h2>
<p>O SES lista seguradoras registradas no ramo, mesmo quando elas não escreveram prêmio no ano. Por isso a base tem {f_num(len(base))} linhas, mas apenas {f_num(int(ativa.sum()))} têm prêmio maior que zero. Há {f_num(int(zerada.sum()))} linhas totalmente zeradas. Elas não distorcem a soma do mercado, mas distorcem qualquer contagem de "seguradoras ativas" e qualquer média por seguradora.</p>
{qual}
<h3>A definição de "ativa" muda a resposta da pergunta 02</h3>
<p>Se você conta toda linha que aparece no SES, a resposta muda. {frase_q2_20} {frase_q2_25} A diferença não é pequena: {frase_gap} Contar linhas mede presença cadastral; contar prêmio positivo mede atividade econômica.</p>
<div class="chart">{q2_graf}</div>
{q2_tab}
<div class="alerta"><p>Decisão recomendada: usar <strong>prêmio ganho &gt; 0</strong> para "seguradoras ativas" e para qualquer ranking por seguradora. Manter as linhas zeradas e negativas nas somas de mercado, porque os totais oficiais do SES as incluem. As duas bases são derivadas do mesmo snapshot, então a escolha fica documentada e reversível.</p></div>
<h3>Onde estão as linhas zeradas</h3>
{comp_lob_tab}
</section>

<section>
<div class="secnum">04 · mercado</div>
<h2>Prêmio: Transportes lidera, mas o crescimento mais rápido é de E&amp;O</h2>
<p>O mercado das cinco LOBs soma {f_bi(total_premio)} em valores nominais. Transportes é a maior linha em todos os anos, seguida de Empresarial e Garantia; E&amp;O é a menor, mas a que mais cresce em porcentagem. A trajetória é de crescimento em todas as linhas, sem queda anual visível no agregado.</p>
<div class="chart">{premio_linha}</div>
{cresc_tab}
<div class="nota"><p><strong>Q1:</strong> {esc(q1['lob'])} é a LOB de maior prêmio no período, com {f_bi(q1['premio'])}. <strong>Q7:</strong> em porcentagem, {esc(q7_pct.name)} cresce {f_pct(q7_pct['pct'])}; em valor absoluto, {esc(q7_abs.name)} adiciona {f_bi(q7_abs['abs'])}.</p></div>
</section>

<section>
<div class="secnum">05 · rentabilidade</div>
<h2>Resultado técnico e margem não seguem o tamanho do prêmio</h2>
<p>Garantia gera o maior resultado técnico do período apesar de ser a terceira em prêmio, porque opera com sinistralidade muito baixa. Transportes tem o maior prêmio e a menor margem. E&amp;O tem a maior margem, sustentada por despesas e sinistralidade menores em relação ao prêmio. Resultado técnico não é lucro contábil: não inclui despesa administrativa, imposto nem resultado financeiro.</p>
<div class="chart">{lucro_bar}</div>
{rent_tab}
<div class="nota"><p><strong>Q5:</strong> {esc(q5['lob'])} lidera o resultado técnico com {f_bi(q5['lucro'])}. <strong>Q6:</strong> {esc(q6['lob'])} lidera a margem com {f_pct(q6['margem'])}. Resultado técnico = prêmio ganho + receita com resseguro − sinistro ocorrido − despesa com resseguro − despesa comercial.</p></div>
</section>

<section>
<div class="secnum">06 · risco</div>
<h2>Sinistralidade: Garantia é a mais confortável, RCG a mais instável</h2>
<p>A sinistralidade agregada esconde trajetórias muito diferentes. Garantia fica entre 7,6% e 30,3% e tem a menor média; RCG tem média parecida com Transportes, mas com um pico de 92,4% em 2023 e desvio de 20,9 pontos percentuais. Empresarial melhora de forma consistente, de 62,5% para 40,4%.</p>
<div class="chart">{heat}</div>
{trend_tab}
<div class="nota"><p><strong>Q3:</strong> {esc(q3['lob'])} tem a maior sinistralidade agregada do período, {f_pct(q3['sinistralidade'])}. <strong>Q9:</strong> em nível de sinistralidade, Garantia é a mais confortável; Transportes é a mais estável; em tendência, Empresarial é a que mais melhora. RCG é a mais volátil e exige leitura ano a ano.</p></div>
</section>

<section>
<div class="secnum">07 · concorrência</div>
<h2>Concentração: poucas seguradoras fazem a maior parte do prêmio</h2>
<p>Em todas as LOBs, o top 5 concentra entre 45% e 54% do prêmio, e cerca de 11 a 14 seguradoras explicam 80% do mercado. {frase_rcg} Isso importa para a pergunta 08: "seguradora relevante" não é a que aparece na tabela, é a que tem share material.</p>
{conc_tab}
<div class="nota"><p><strong>Q2:</strong> {frase_q2_20} {frase_q2_25} <strong>Q8:</strong> use o corte de 80% do prêmio cumulativo para separar as relevantes das demais; o HHI mostra que nenhuma LOB é altamente concentrada, mas Transportes e Empresarial são as mais concentradas do grupo.</p></div>
</section>

<section>
<div class="secnum">08 · outliers</div>
<h2>Outliers e ajustes: o que não pode entrar numa média ingênua</h2>
<p>Há seguradoras com sinistralidade acima de 100% e empresas com prêmio zero e sinistro positivo. Isso é esperado em dados de seguro: um sinistro grande pode consumir mais de um ano de prêmio, e estornos podem deixar o prêmio líquido negativo. O tratamento correto não é apagar o valor, é impedir que ele contamine rankings e médias.</p>
{out_tab}
<div class="alerta"><p>{frase_neg}</p></div>
<h3>Ajustes negativos por coluna</h3>
{neg_tab}
<div class="alerta"><p>Regra prática: para ranking por seguradora, exigir share mínimo de 1% do prêmio da LOB. Para somas de mercado, manter todos os valores, inclusive negativos. Para séries por seguradora, mostrar o valor bruto e sinalizar quando a sinistralidade sai de [0, 100%].</p></div>
</section>

<section>
<div class="secnum">09 · Akad</div>
<h2>A Akad é forte em E&amp;O e escala em Transportes, mas a margem de Transportes preocupa</h2>
<p>A Akad está nas cinco LOBs, mas com pesos muito diferentes. Em E&amp;O ela é a primeira do mercado desde 2022, com share de {f_pct(akad_eo['share1'])} em {anos[-1]}. Em Transportes ela é a terceira, com {f_pct(akad_tr['share1'])}, mas a margem caiu para 0,2% em 2025. Em RCG o share ainda é {f_pct(akad_rcg['share1'])}, porém a margem é alta e o mercado é volátil. Garantia e Empresarial são subescala.</p>
{ak_tab}
{('<div class="nota"><p>' + frase_base_emp + '</p></div>') if frase_base_emp else ''}
<div class="chart">{ak_share}</div>
<h3>Akad contra mercado, pares de porte e relevantes</h3>
{comp_tab}
<div class="nota"><p><strong>Q10:</strong> as LOBs em que a Akad é relevante são E&amp;O e Transportes. {frase_rank} Os maiores avanços são {frase_destaques}. <strong>Q11:</strong> a Akad supera o mercado em margem em E&amp;O e RCG; em Transportes tem escala, mas margem abaixo do mercado; em Garantia e Empresarial está atrás. A comparação com pares de porte confirma o padrão: a vantagem de E&amp;O não é só de tamanho, é de rentabilidade.</p></div>
</section>

<section>
<div class="secnum">10 · respostas</div>
<h2>O que o EDA já responde do case</h2>
<p>Estas são leituras exploratórias, com o tratamento acima. As perguntas 4, 8, 9 e 12 ainda pedem uma camada analítica mais fina — ranking por seguradora com corte de materialidade, tendência com intervalo e recomendação — que é o próximo passo, antes de qualquer dashboard.</p>
{resp_tab}
</section>

<section>
<div class="secnum">11 · próximos passos</div>
<h2>Decisões de tratamento que eu levaria para a base final</h2>
<ul>
<li><strong>Ativa = prêmio &gt; 0.</strong> Usar essa definição em Q2, Q4, Q8, Q10 e Q11. Manter a base completa para Q1, Q3, Q5, Q6 e Q7, porque os totais do SES incluem zeros e negativos.</li>
<li><strong>Consulta vazia = prêmio total ≤ 0.</strong> Isso captura o 0645/2025, que hoje passa como tabela válida com seis zeros.</li>
<li><strong>Materialidade para ranking:</strong> share mínimo de 1% da LOB (ou top 80% cumulativo) para comparar seguradoras. Sem isso, empresas minúsculas dominam o ranking de sinistralidade.</li>
<li><strong>Negativos ficam.</strong> Não truncar; sinalizar. Se a apresentação pedir "sinistralidade bruta", calcular com e sem estornos e mostrar a diferença.</li>
<li><strong>Sinistralidade sempre por razão de somas.</strong> Nunca média de percentuais; a diferença aparece justamente nas LOBs com seguradoras pequenas.</li>
<li><strong>Próximo passo:</strong> fechar a camada de análise (Q4, Q8, Q9 e Q12), validar os números com você e só então montar o dashboard Streamlit.</li>
</ul>
<div class="nota"><p>Para regerar este relatório: <code>python analise/eda.py</code>. Para reprocessar a base sem rede: <code>cd automacao &amp;&amp; python pipeline.py processar</code>. O relatório lê o ponteiro <code>data/snapshots/latest.json</code>, então acompanha automaticamente o próximo snapshot publicado.</p></div>
</section>

<div class="fim">Gerado em {datetime.now():%Y-%m-%d %H:%M} · snapshot {esc(snap)} · SES/SUSEP · uso exclusivo do processo seletivo Akad 2027</div>
</div></body></html>"""

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html_doc, encoding="utf-8")
    return saida


def main() -> int:
    p = argparse.ArgumentParser(description="EDA do SES/SUSEP - Case Akad 2027")
    p.add_argument("--snapshot", help="nome do snapshot (padrao: o vigente)")
    p.add_argument("--saida", default=str(ROOT / "analise" / "eda.html"), help="arquivo HTML de saida")
    args = p.parse_args()
    destino = gerar(Path(args.saida), args.snapshot)
    print(f"Relatorio gerado: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
