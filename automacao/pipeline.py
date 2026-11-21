#!/usr/bin/env python3
"""CLI da automacao SES/SUSEP - Case Trainee Akad 2027.

  python pipeline.py atualizar              coleta (o que falta) + processa + publica
  python pipeline.py atualizar --offline    so processa o raw/ (sem rede)
  python pipeline.py coletar [--headless]   so coleta no SES
  python pipeline.py processar              raw/ -> contrato -> snapshot (sem rede)
  python pipeline.py periodo --periodo-ini 202501 --periodo-fim 202503 [--ramos 0351]
  python pipeline.py status [--checar-fonte]
  python pipeline.py snapshots
  python pipeline.py rollback [--para <snapshot>]

Codigo de saida: 0 = ok, 1 = coleta incompleta ou contrato reprovado
(o dashboard continua no ultimo snapshot valido).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

from ses import publish
from ses.config import Config
from ses.status import coletar_status
from ses.transform import construir_base, construir_periodo
from ses.validate import validar, validar_periodo


def _salvar_run(cfg: Config, relatorio: dict) -> None:
    cfg.runs.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    relatorio = {"run_id": run_id, **relatorio}
    (cfg.runs / f"{run_id}.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def cmd_coletar(cfg: Config, args) -> dict:
    from ses.extract import extrair  # import tardio: playwright so quando precisa

    return extrair(
        cfg,
        headless=args.headless,
        forcar=args.forcar,
        anos=args.anos,
        ramos=args.ramos,
        limite=args.limite,
    )


def cmd_processar(cfg: Config) -> dict:
    base, diagnosticos = construir_base(cfg)
    relatorio = validar(cfg, base, diagnosticos)

    print(f"Cobertura: {relatorio['cobertura']['lidas']}/{relatorio['cobertura']['esperadas']} consultas lidas, "
          f"{relatorio['cobertura']['totais_conferidos']} conferidas com 'Totais' do SES, "
          f"{relatorio['linhas']} linhas.")
    for a in relatorio["avisos"]:
        print(f"  aviso: {a}")

    if not relatorio["aprovado"]:
        print(f"\nCONTRATO REPROVADO ({len(relatorio['erros'])} erros). Snapshot NAO publicado.")
        for e in relatorio["erros"][:25]:
            print(f"  x {e}")
        if len(relatorio["erros"]) > 25:
            print(f"  ... e mais {len(relatorio['erros']) - 25}")
        print(f"Dashboard segue no snapshot: {publish.atual(cfg)}")
        return {"processamento": {"aprovado": False, "erros": relatorio["erros"]}}

    resultado = publish.publicar(
        cfg, base, relatorio,
        extra_meta={"diagnosticos": [d.a_dict() for d in diagnosticos]},
    )
    if resultado["publicado"]:
        print(f"\nSnapshot publicado: {resultado['snapshot']}")
        d = resultado["diff"]
        if d:
            print(f"  vs anterior: {d['linhas_alteradas']} linhas retificadas, "
                  f"{d['linhas_novas']} novas, {d['linhas_removidas']} removidas")
            for lob, v in d["delta_premio_ganho_por_lob"].items():
                print(f"    {lob}: variacao de premio ganho R$ {v:,.0f}")
    else:
        print(f"\nNada a publicar: {resultado['motivo']} ({resultado['snapshot']}).")
    return {"processamento": {"aprovado": True, **resultado}}


def _parse_aaaamm(valor: str) -> tuple[int, int]:
    if not re.fullmatch(r"\d{6}", valor or ""):
        raise ValueError(f"periodo invalido: {valor!r} (use AAAAMM)")
    ano, mes = int(valor[:4]), int(valor[4:])
    if not 1 <= mes <= 12:
        raise ValueError(f"mes invalido em {valor!r}")
    return ano, mes


def cmd_periodo(cfg: Config, args) -> dict:
    """Coleta e publica um recorte parcial (trimestre/mes) em data/atualizacoes."""
    ano_i, mes_i = _parse_aaaamm(args.periodo_ini)
    ano_f, mes_f = _parse_aaaamm(args.periodo_fim)
    if ano_i != ano_f:
        raise ValueError("por enquanto o periodo precisa estar no mesmo ano")
    if mes_i > mes_f:
        raise ValueError("mes inicial nao pode ser maior que o final")
    if mes_i == 1 and mes_f == 12:
        raise ValueError("ano fechado deve usar o comando 'atualizar'")

    consultas = cfg.consultas_periodo(ano_i, mes_i, mes_f, ramos=args.ramos, lobs=args.lobs)
    if not consultas:
        raise ValueError("nenhuma consulta no recorte")

    falhas_coleta: list[str] = []
    if not args.offline:
        from ses.extract import extrair

        coleta = extrair(
            cfg,
            headless=args.headless,
            forcar=args.forcar,
            consultas=consultas,
            pasta=cfg.raw_periodos,
        )
        print(
            f"\nColeta parcial: {len(coleta['coletadas'])} novas, "
            f"{len(coleta['puladas'])} ja existiam, {len(coleta['falhas'])} falhas."
        )
        falhas_coleta = list(coleta["falhas"])

    base, diag = construir_periodo(cfg, consultas)
    rel = validar_periodo(cfg, base, diag, consultas)
    print(
        f"Cobertura parcial: {rel['cobertura']['lidas']}/{rel['cobertura']['esperadas']} consultas, "
        f"{rel['cobertura']['totais_conferidos']} conferidas com 'Totais' do SES, "
        f"{rel['linhas']} linhas."
    )
    for a in rel["avisos"]:
        print(f"  aviso: {a}")

    if not rel["aprovado"]:
        print(f"\nCONTRATO PARCIAL REPROVADO ({len(rel['erros'])} erros). Nada publicado.")
        for e in rel["erros"][:25]:
            print(f"  x {e}")
        return {
            "periodo": {
                "aprovado": False,
                "erros": rel["erros"],
                "falhas_coleta": falhas_coleta,
                "periodo_ini": args.periodo_ini,
                "periodo_fim": args.periodo_fim,
            }
        }

    meta = {
        "periodo_ini": args.periodo_ini,
        "periodo_fim": args.periodo_fim,
        "ano": ano_i,
        "mes_inicio": mes_i,
        "mes_fim": mes_f,
        "meses": mes_f - mes_i + 1,
        "ramos": sorted({c.ramo for c in consultas}),
        "lobs": sorted({c.lob for c in consultas}),
        "parcial": True,
    }
    resultado = publish.publicar_periodo(
        cfg,
        base,
        rel,
        meta_periodo=meta,
        extra_meta={"diagnosticos": [d.a_dict() for d in diag]},
    )
    print(f"\nAtualizacao parcial publicada: {resultado['atualizacao']}")
    return {
        "periodo": {
            "aprovado": True,
            "falhas_coleta": falhas_coleta,
            **resultado,
            **meta,
        }
    }


def cmd_status(cfg: Config, args) -> None:
    s = coletar_status(cfg, checar_fonte=args.checar_fonte)

    def sem(ok):
        return "[OK]" if ok else "[!!]"

    print(f"{sem(s['dados_ok'])} dados     snapshot {s['snapshot_vigente']} "
          f"({s['dados_atualizados_em']}, {s['idade_dias']} dias) {sem(s['dados_frescos'])} frescor")
    print(f"     cobertura raw {s['cobertura_raw']} | snapshot {s['cobertura_snapshot']} "
          f"| totais SES conferidos {s['totais_conferidos']}")
    print(f"     ultima coleta no SES: {s['ultima_coleta_raw']}")
    if s["fonte_ses_disponivel"] is not None:
        print(f"{sem(s['fonte_ses_disponivel'])} fonte     portal do SES")
    for a in s["avisos"]:
        print(f"     aviso: {a}")


def main() -> int:
    p = argparse.ArgumentParser(description="Automacao SES/SUSEP - case Akad 2027")
    sub = p.add_subparsers(dest="cmd", required=True)

    def opcoes_coleta(sp):
        sp.add_argument("--headless", action="store_true",
                        help="sem janela (padrao: navegador visivel, como no ses_coleta.py original)")
        sp.add_argument("--forcar", action="store_true", help="re-extrai mesmo o que ja existe")
        sp.add_argument("--anos", type=int, nargs="+", help="limita a estes anos")
        sp.add_argument("--ramos", nargs="+", help="limita a estes codigos de ramo")
        sp.add_argument("--limite", type=int, help="maximo de consultas (teste)")

    a = sub.add_parser("atualizar", help="coleta + processa + publica")
    opcoes_coleta(a)
    a.add_argument("--offline", action="store_true", help="nao acessa a rede: so reprocessa o raw/")

    c = sub.add_parser("coletar", help="so coleta no SES")
    opcoes_coleta(c)

    sub.add_parser("processar", help="raw/ -> contrato -> snapshot (sem rede)")

    per = sub.add_parser("periodo", help="coleta/processa um recorte parcial (trimestre/mes)")
    per.add_argument("--periodo-ini", required=True, help="AAAAMM inicial")
    per.add_argument("--periodo-fim", required=True, help="AAAAMM final")
    per.add_argument("--ramos", nargs="+", help="limita a estes codigos de ramo")
    per.add_argument("--lobs", nargs="+", help="limita a estas LOBs")
    per.add_argument("--headless", action="store_true", help="sem janela do navegador")
    per.add_argument("--forcar", action="store_true", help="re-extrai o que ja existe")
    per.add_argument("--offline", action="store_true", help="nao acessa a rede")

    s = sub.add_parser("status", help="painel de saude")
    s.add_argument("--checar-fonte", action="store_true")

    sub.add_parser("snapshots", help="lista snapshots")

    r = sub.add_parser("rollback", help="volta ao snapshot anterior")
    r.add_argument("--para", help="nome do snapshot (padrao: o anterior)")

    args = p.parse_args()
    cfg = Config()

    if args.cmd == "status":
        cmd_status(cfg, args)
        return 0

    if args.cmd == "snapshots":
        vigente = publish.atual(cfg)
        for nome in publish.listar(cfg):
            print(("* " if nome == vigente else "  ") + nome)
        return 0

    if args.cmd == "rollback":
        destino = publish.rollback(cfg, args.para)
        print(f"Dashboard agora aponta para o snapshot {destino}")
        return 0

    relatorio: dict = {"comando": args.cmd, "inicio": datetime.now().isoformat(timespec="seconds")}
    sucesso = True

    if args.cmd == "periodo":
        try:
            proc = cmd_periodo(cfg, args)
        except ValueError as e:
            print(f"erro: {e}")
            return 2
        relatorio.update(proc)
        sucesso = proc["periodo"]["aprovado"] and not proc["periodo"].get("falhas_coleta")
    else:
        if args.cmd in ("coletar", "atualizar") and not getattr(args, "offline", False):
            coleta = cmd_coletar(cfg, args)
            relatorio["coleta"] = coleta
            print(f"\nColeta: {len(coleta['coletadas'])} novas, {len(coleta['puladas'])} ja existiam, "
                  f"{len(coleta['falhas'])} falhas.")
            if coleta["falhas"]:
                sucesso = False

        if args.cmd in ("processar", "atualizar"):
            proc = cmd_processar(cfg)
            relatorio.update(proc)
            if not proc["processamento"]["aprovado"]:
                sucesso = False

    relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
    relatorio["sucesso"] = sucesso
    _salvar_run(cfg, relatorio)
    return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
