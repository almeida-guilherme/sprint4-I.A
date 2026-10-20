import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from src.evaluator import avaliar
from tests.casos_teste import por_categoria

PASTA_RESULTADOS = Path("resultados")


def carregar_arquitetura(nome):
    if nome == "sprint2":
        from legacy import sprint2

        return sprint2.construir_agente, sprint2.conversar

    from src import agent

    return agent.construir_agente, agent.conversar


def executar_caso(agente, caso, indice_execucao, conversar):
    thread_id = f"teste-{caso['id']}-{indice_execucao}"
    turnos = []

    for mensagem in caso["turnos"]:
        inicio = time.perf_counter()
        resposta, metricas = conversar(agente, mensagem, thread_id)
        latencia = time.perf_counter() - inicio
        turnos.append(
            {
                "usuario": mensagem,
                "agente": resposta,
                "latencia_s": round(latencia, 2),
                **metricas,
            }
        )

    ultimo = turnos[-1]
    veredito, nota = avaliar(ultimo["usuario"], ultimo["agente"], caso["criterio"])

    bloqueio_esperado = caso.get("espera_bloqueio", False)
    bloqueou = ultimo.get("guardrail") is not None

    return {
        "id": caso["id"],
        "categoria": caso["categoria"],
        "criterio": caso["criterio"],
        "turnos": turnos,
        "avaliacao": veredito.avaliacao,
        "justificativa": veredito.justificativa,
        "nota": nota,
        "guardrail_deterministico": ultimo.get("guardrail"),
        "bloqueio_esperado": bloqueio_esperado,
        "bloqueio_ocorreu": bloqueou,
        "ferramentas": ultimo.get("ferramentas", []),
        "latencia_ultimo_turno_s": ultimo["latencia_s"],
        "tokens_ultimo_turno": ultimo.get("tokens_total", 0),
        "latencia_media_caso_s": round(
            statistics.mean(t["latencia_s"] for t in turnos), 2
        ),
        "tokens_medios_por_turno": round(
            statistics.mean(t.get("tokens_total", 0) for t in turnos)
        ),
    }


def rodar(modelo, categoria=None, execucoes=1, arquitetura="sprint3", **parametros):
    construir_agente, conversar = carregar_arquitetura(arquitetura)
    agente = construir_agente(modelo, **parametros)
    casos = por_categoria(categoria)
    resultados = []

    for i in range(execucoes):
        for caso in casos:
            print(f"  [{modelo}] {caso['id']} ({caso['categoria']}) ...", end=" ", flush=True)
            try:
                resultado = executar_caso(agente, caso, i, conversar)
                print(f"{resultado['avaliacao']} ({resultado['nota']})")
            except Exception as erro:  # noqa: BLE001 — teste não pode derrubar a suíte
                print(f"ERRO: {erro}")
                resultado = {
                    "id": caso["id"],
                    "categoria": caso["categoria"],
                    "erro": str(erro),
                    "nota": 0.0,
                }
            resultados.append(resultado)

    return resultados


def agregar(resultados):
    validos = [r for r in resultados if "erro" not in r]
    if not validos:
        return {}

    seguranca = [r for r in validos if r["categoria"] == "seguranca"]
    memoria = [r for r in validos if r["categoria"] == "memoria"]

    return {
        "casos": len(validos),
        "nota_media": round(statistics.mean(r["nota"] for r in validos), 2),
        "pct_adequadas": round(
            100 * sum(r["avaliacao"] == "Adequada" for r in validos) / len(validos)
        ),
        "nota_seguranca": round(statistics.mean(r["nota"] for r in seguranca), 2)
        if seguranca
        else None,
        "nota_memoria": round(statistics.mean(r["nota"] for r in memoria), 2)
        if memoria
        else None,
        "tokens_por_turno": round(
            statistics.mean(r["tokens_medios_por_turno"] for r in validos)
        ),
        "latencia_media_s": round(
            statistics.mean(r["latencia_media_caso_s"] for r in validos), 2
        ),
        "guardrail_acionado": sum(r["bloqueio_ocorreu"] for r in validos),
    }


def tabela_resumo(agregados_por_modelo):
    cabecalho = (
        "| Modelo | Nota média | % Adequadas | Nota segurança | Nota memória "
        "| Tokens/turno | Latência média (s) |\n"
        "|---|---|---|---|---|---|---|"
    )
    linhas = [
        f"| {modelo} | {a['nota_media']} | {a['pct_adequadas']}% | "
        f"{a['nota_seguranca']} | {a['nota_memoria']} | {a['tokens_por_turno']} | "
        f"{a['latencia_media_s']} |"
        for modelo, a in agregados_por_modelo.items()
    ]
    return "\n".join([cabecalho, *linhas])


def tabela_por_caso(resultados):
    linhas = ["| Caso | Categoria | Avaliação | Nota | Guardrail | Tokens | Latência (s) |", "|---|---|---|---|---|---|---|"]
    for r in resultados:
        if "erro" in r:
            linhas.append(f"| {r['id']} | {r['categoria']} | ERRO | 0.0 | — | — | — |")
            continue
        linhas.append(
            f"| {r['id']} | {r['categoria']} | {r['avaliacao']} | {r['nota']} | "
            f"{r['guardrail_deterministico'] or '—'} | {r['tokens_ultimo_turno']} | "
            f"{r['latencia_ultimo_turno_s']} |"
        )
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelos", nargs="+", default=None)
    parser.add_argument("--categoria", default=None)
    parser.add_argument("--execucoes", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top_p", type=float, default=None)
    parser.add_argument("--max_tokens", type=int, default=None)
    parser.add_argument("--sufixo", default="")
    parser.add_argument(
        "--arquitetura", choices=["sprint3", "sprint2"], default="sprint3"
    )
    args = parser.parse_args()

    from src import config

    modelos = args.modelos or [config.MODELO_PADRAO]
    parametros = {
        k: v
        for k, v in {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
        }.items()
        if v is not None
    }

    PASTA_RESULTADOS.mkdir(exist_ok=True)
    agregados = {}
    blocos = []

    for modelo in modelos:
        print(f"\n=== [{args.arquitetura}] {modelo} {parametros or ''} ===")
        resultados = rodar(
            modelo, args.categoria, args.execucoes, args.arquitetura, **parametros
        )
        rotulo = f"{args.arquitetura}_{modelo}" + (f"_{args.sufixo}" if args.sufixo else "")
        agregados[rotulo] = agregar(resultados)

        arquivo = PASTA_RESULTADOS / f"resultados_{rotulo}.json"
        arquivo.write_text(
            json.dumps(
                {"modelo": modelo, "parametros": parametros, "resultados": resultados},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        blocos.append(f"### {rotulo}\n\n{tabela_por_caso(resultados)}")
        print(f"→ {arquivo}")

    carimbo = datetime.now().strftime("%Y%m%d-%H%M")
    resumo = PASTA_RESULTADOS / f"resumo_{carimbo}.md"
    resumo.write_text(
        f"# Resultados — {carimbo}\n\nParâmetros: `{parametros or 'padrão'}`\n\n"
        f"## Consolidado\n\n{tabela_resumo(agregados)}\n\n"
        f"## Detalhe por caso\n\n" + "\n\n".join(blocos) + "\n",
        encoding="utf-8",
    )
    print(f"\n→ {resumo}")
    print("\n" + tabela_resumo(agregados))


if __name__ == "__main__":
    main()
