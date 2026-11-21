#!/usr/bin/env python3
"""CLI da automacao SES/SUSEP - Case Trainee Akad 2027.

  python pipeline.py atualizar              coleta (o que falta) + processa + publica
  python pipeline.py atualizar --offline    so processa o raw/ (sem rede)
  python pipeline.py coletar [--headless]   so coleta no SES
  python pipeline.py processar              raw/ -> contrato -> snapshot (sem rede)
  python pipeline.py status [--checar-fonte]
  python pipeline.py snapshots
  python pipeline.py rollback [--para <snapshot>]

Codigo de saida: 0 = ok, 1 = coleta incompleta ou contrato reprovado
(o dashboard continua no ultimo snapshot valido).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from ses import publish
from ses.config import Config
from ses.status import coletar_status
from ses.transform import construir_base
from ses.validate import validar


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
