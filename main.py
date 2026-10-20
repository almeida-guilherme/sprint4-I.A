import argparse
import time
import uuid

from src import config
from src.agent import construir_agente, conversar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default=None, help="nome registrado em config.MODELOS")
    parser.add_argument("--sessao", default=None, help="thread_id da conversa")
    parser.add_argument("--temperature", type=float, default=None)
    args = parser.parse_args()

    parametros = {} if args.temperature is None else {"temperature": args.temperature}
    modelo = args.modelo or config.MODELO_PADRAO
    sessao = args.sessao or f"cli-{uuid.uuid4().hex[:8]}"

    print(f"ChargeGrid AI — modelo: {modelo} | sessão: {sessao}")
    print("Comandos: /sessao <id>, /metricas, /sair\n")

    agente = construir_agente(modelo, **parametros)
    ultimas_metricas = None

    while True:
        try:
            entrada = input("você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not entrada:
            continue
        if entrada == "/sair":
            break
        if entrada == "/metricas":
            print(f"  {ultimas_metricas or 'nenhum turno ainda'}\n")
            continue
        if entrada.startswith("/sessao "):
            sessao = entrada.split(" ", 1)[1].strip()
            print(f"  sessão atual: {sessao}\n")
            continue

        inicio = time.perf_counter()
        resposta, metricas = conversar(agente, entrada, sessao)
        metricas["latencia_s"] = round(time.perf_counter() - inicio, 2)
        ultimas_metricas = metricas

        print(f"\nChargeGrid AI: {resposta}\n")


if __name__ == "__main__":
    main()
