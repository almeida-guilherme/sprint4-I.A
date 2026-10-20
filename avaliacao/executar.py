"""Pipeline de avaliação sistemática — Sprint 04.

Executa o golden dataset contra uma ou mais versões do agente, mede cada
resposta com o juiz LLM e grava resultados brutos, agregados e tabelas.

Exemplos:
    # comparativo principal (Bloco B): Sprint 2 × Sprint 3, 3 execuções
    python -m avaliacao.executar --versoes sprint2:gpt-4o-mini sprint3:gpt-4o-mini

    # inclui a variação de modelo da Sprint 3 como terceira versão
    python -m avaliacao.executar --versoes sprint2:gpt-4o-mini sprint3:gpt-4o-mini sprint3:gpt-4.1-mini

    # teste rápido, só alguns casos, 1 execução
    python -m avaliacao.executar --casos F1 F5 S4 --execucoes 1

    # testar o encanamento sem API (números sem significado)
    python -m avaliacao.executar --simulado

Saída em resultados/sprint4/<carimbo>/:
    bruto_<versao>.json   todas as respostas, métricas e justificativas do juiz
    resumo.json           agregados por versão, por caso, classificação e confronto
    resumo.md             todas as tabelas prontas para o relatório
"""

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from avaliacao import analise, tabelas
from avaliacao.golden_dataset import filtrar
from avaliacao.metricas import JuizLLM, avaliar_resposta

PASTA = Path("resultados") / "sprint4"


def carregar_versao(arquitetura, simulado=False):
    if simulado:
        from avaliacao.simulado import construir_agente_simulado

        return construir_agente_simulado(arquitetura)
    if arquitetura == "sprint2":
        from legacy import sprint2

        return sprint2.construir_agente, sprint2.conversar
    if arquitetura == "sprint3":
        from src import agent

        return agent.construir_agente, agent.conversar
    raise ValueError(f"Arquitetura desconhecida: {arquitetura}")


def executar_caso(agente, conversar, juiz, caso, execucao, rotulo):
    thread_id = f"s4-{rotulo}-{caso['id']}-{execucao}"
    turnos = []
    for mensagem in caso["turnos"]:
        inicio = time.perf_counter()
        resposta, metricas = conversar(agente, mensagem, thread_id)
        turnos.append(
            {
                "usuario": mensagem,
                "agente": resposta,
                "latencia_s": round(time.perf_counter() - inicio, 2),
                **{k: v for k, v in metricas.items() if k != "contexto"},
            }
        )
    ultimo = turnos[-1]
    contexto = metricas.get("contexto", "")
    bloqueou = ultimo.get("guardrail") is not None

    resultado_metricas = avaliar_resposta(juiz, caso, ultimo["agente"], contexto, bloqueou)

    return {
        "versao": rotulo,
        "execucao": execucao,
        "id": caso["id"],
        "categoria": caso["categoria"],
        "origem": caso["origem"],
        "comportamento": caso["comportamento"],
        "turnos": turnos,
        "resposta": ultimo["agente"],
        "contexto_chars": len(contexto or ""),
        "contexto": contexto,
        "metricas": resultado_metricas,
        "bloqueio_esperado": caso["espera_bloqueio"],
        "bloqueio_ocorreu": bloqueou,
        "guardrail": ultimo.get("guardrail"),
        "ferramentas": ultimo.get("ferramentas", []),
        "latencia_media_caso_s": round(statistics.mean(t["latencia_s"] for t in turnos), 2),
        "tokens_medios_por_turno": round(statistics.mean(t.get("tokens_total", 0) for t in turnos)),
    }


def rodar_versao(spec, casos, execucoes, juiz, paralelo, simulado):
    arquitetura, modelo = spec.split(":", 1) if ":" in spec else (spec, "gpt-4o-mini")
    rotulo = f"{arquitetura}_{modelo}"
    construir, conversar = carregar_versao(arquitetura, simulado)
    agente = construir(modelo)

    if not simulado:
        from src.rag import obter_store

        obter_store()  # indexa antes de paralelizar

    tarefas = [(caso, i) for i in range(execucoes) for caso in casos]
    resultados = []
    print(f"\n=== {rotulo}: {len(casos)} casos × {execucoes} execuções ===")

    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        futuros = {
            pool.submit(executar_caso, agente, conversar, juiz, caso, i, rotulo): (caso, i)
            for caso, i in tarefas
        }
        for futuro in as_completed(futuros):
            caso, i = futuros[futuro]
            try:
                r = futuro.result()
                m = r["metricas"]
                print(
                    f"  [{rotulo}] exec {i + 1} {caso['id']:<4} "
                    f"correção={_v(m['correcao'])} escopo={_v(m['aderencia_escopo'])} "
                    f"fidelidade={_v(m['fidelidade'])} recusa={_n(m['recusa_correta'])} "
                    f"veredito={m['veredito'].get('avaliacao', 'ERRO')}"
                    + (" 🛡" if r["bloqueio_ocorreu"] else "")
                )
            except Exception as erro:  # noqa: BLE001 — um caso não derruba a suíte
                print(f"  [{rotulo}] exec {i + 1} {caso['id']:<4} ERRO: {erro}")
                r = {
                    "versao": rotulo, "execucao": i, "id": caso["id"],
                    "categoria": caso["categoria"], "origem": caso["origem"],
                    "erro": f"{type(erro).__name__}: {erro}",
                }
            resultados.append(r)

    ordem = {c["id"]: n for n, c in enumerate(casos)}
    resultados.sort(key=lambda r: (r["execucao"], ordem[r["id"]]))
    return rotulo, modelo, resultados


def _v(m):
    return "—" if m.get("valor") is None else f"{m['valor']:.2f}"


def _n(x):
    return "—" if x is None else f"{x:.0f}"


def montar_resumo(por_versao, meta):
    agregados = {v: analise.agregar_versao(rs) for v, rs in por_versao.items()}
    casos = {v: analise.por_caso(rs) for v, rs in por_versao.items()}
    classificacao = analise.classificar(agregados)
    confrontos = {
        v: c for v in casos if (c := analise.confrontar_manual(v, casos[v])) is not None
    }
    return {
        "meta": meta,
        "agregados": agregados,
        "casos": casos,
        "classificacao": classificacao,
        "confronto_manual": confrontos,
    }


def resumo_markdown(resumo):
    meta = resumo["meta"]
    partes = [
        f"# Resultados do pipeline de avaliação — {meta['carimbo']}",
        "",
        f"- Versões: {', '.join(meta['versoes'])}",
        f"- Casos: {meta['casos']} · Execuções por versão: {meta['execucoes']} · "
        f"Juiz: `{meta['juiz']}` (temperature=0)" + (" · **MODO SIMULADO**" if meta["simulado"] else ""),
        "",
        "## Tabela de resultados por versão (média ± desvio-padrão entre execuções)",
        "",
        tabelas.tabela_versoes(resumo["agregados"]),
        "",
        "## Classificação",
        "",
        "Ordem: " + " > ".join(resumo["classificacao"]["ordem"]),
        "",
        resumo["classificacao"]["motivo"],
        "",
        "## Nota por categoria",
        "",
        tabelas.tabela_categorias(resumo["agregados"]),
        "",
        "## Guardrail determinístico",
        "",
        tabelas.tabela_guardrail(resumo["agregados"]),
        "",
        "## Nota por caso (⚠ = veredito variou entre execuções · 🛡 = bloqueado pelo guardrail)",
        "",
        tabelas.tabela_por_caso(resumo["casos"]),
        "",
    ]
    for versao, casos in resumo["casos"].items():
        partes += [f"### Métricas por caso — {versao}", "", tabelas.tabela_metricas_por_caso(casos, versao), ""]

    for versao, c in resumo["confronto_manual"].items():
        conc = "—" if c["concordancia"] is None else f"{100 * c['concordancia']:.0f}%"
        kappa = "—" if c["kappa"] is None else f"{c['kappa']:.2f}"
        conc_c = "—" if c["concordancia_correcao"] is None else f"{100 * c['concordancia_correcao']:.0f}%"
        partes += [
            f"## Confronto com a avaliação manual da Sprint 3 — {versao}",
            "",
            f"Casos com avaliação manual: {c['n']} · Concordância (veredito): {conc} · "
            f"Kappa de Cohen: {kappa} · Concordância (correção → 3 níveis): {conc_c}",
            "",
            tabelas.tabela_confronto(c),
            "",
        ]
        if c["divergencias"]:
            partes += ["Divergências — justificativa do juiz:", ""]
            partes += [f"- **{d['id']}** (manual: {d['manual']}; pipeline: {d['pipeline_veredito']}): {d['justificativa']}"
                       for d in c["divergencias"]]
            partes.append("")
    return "\n".join(partes)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--versoes", nargs="+", default=["sprint2:gpt-4o-mini", "sprint3:gpt-4o-mini"],
                        help="arquitetura:modelo (arquitetura = sprint2 | sprint3)")
    parser.add_argument("--execucoes", type=int, default=3)
    parser.add_argument("--juiz", default=None, help="modelo do juiz (padrão: config.MODELO_JUIZ)")
    parser.add_argument("--categoria", default=None)
    parser.add_argument("--casos", nargs="+", default=None, help="ids específicos, ex.: F1 S4")
    parser.add_argument("--paralelo", type=int, default=4, help="casos executados em paralelo")
    parser.add_argument("--simulado", action="store_true", help="agente e juiz falsos, sem API")
    parser.add_argument("--saida", default=None)
    args = parser.parse_args()

    casos = filtrar(args.categoria, args.casos)
    if not casos:
        raise SystemExit("Nenhum caso selecionado.")

    if args.simulado:
        from avaliacao.simulado import juiz_simulado

        juiz, nome_juiz = juiz_simulado, "simulado"
    else:
        from src import config

        nome_juiz = args.juiz or config.MODELO_JUIZ
        modelos_agente = {v.split(":", 1)[1] for v in args.versoes if ":" in v}
        if nome_juiz in modelos_agente:
            print(f"⚠ O juiz ({nome_juiz}) é o mesmo modelo de uma versão avaliada — "
                  "risco de viés de autopreferência.")
        juiz = JuizLLM(nome_juiz)

    carimbo = datetime.now().strftime("%Y%m%d-%H%M")
    pasta = Path(args.saida) if args.saida else PASTA / (carimbo + ("-simulado" if args.simulado else ""))
    pasta.mkdir(parents=True, exist_ok=True)

    por_versao, versoes = {}, []
    for spec in args.versoes:
        rotulo, modelo, resultados = rodar_versao(spec, casos, args.execucoes, juiz, args.paralelo, args.simulado)
        por_versao[rotulo] = resultados
        versoes.append(rotulo)
        (pasta / f"bruto_{rotulo}.json").write_text(
            json.dumps({"versao": rotulo, "modelo": modelo, "juiz": nome_juiz, "resultados": resultados},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    meta = {
        "carimbo": carimbo, "versoes": versoes, "execucoes": args.execucoes,
        "casos": len(casos), "ids_casos": [c["id"] for c in casos],
        "juiz": nome_juiz, "simulado": args.simulado,
    }
    resumo = montar_resumo(por_versao, meta)
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    md = resumo_markdown(resumo)
    (pasta / "resumo.md").write_text(md, encoding="utf-8")

    print("\n" + tabelas.tabela_versoes(resumo["agregados"]))
    print("\n" + resumo["classificacao"]["motivo"])
    print(f"\n→ {pasta}/resumo.md")
    print(f"→ relatório: python -m avaliacao.relatorio {pasta}")


if __name__ == "__main__":
    main()
