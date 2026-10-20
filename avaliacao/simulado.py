"""Modo simulado (`--simulado`): agente e juiz falsos, sem chamar nenhuma API.

Serve para testar o encanamento do pipeline (execução, métricas, agregação,
tabelas e relatório) sem custo e sem chave. Os números produzidos neste modo
NÃO têm significado e nunca devem ir para o relatório.
"""

import hashlib
import random

from avaliacao.golden_dataset import CASOS
from avaliacao.metricas import (
    AnaliseFidelidade,
    Afirmacao,
    NotaCorrecao,
    NotaEscopo,
)
from src import guardrails
from src.evaluator import Avaliacao
from src.prompts import mensagem_de_bloqueio

_POR_ULTIMO_TURNO = {c["turnos"][-1]: c for c in CASOS}


class AgenteSimulado:
    def __init__(self, arquitetura):
        self.arquitetura = arquitetura


def construir_agente_simulado(arquitetura):
    def construir(nome_modelo=None, **_):
        return AgenteSimulado(arquitetura)

    def conversar(agente, mensagem, thread_id):
        caso = _POR_ULTIMO_TURNO.get(mensagem)
        metricas = {"tokens_entrada": 900, "tokens_saida": 200, "tokens_total": 1100,
                    "guardrail": None, "ferramentas": [], "contexto": ""}
        if agente.arquitetura == "sprint3":
            bloqueado, motivo = guardrails.verificar_entrada(mensagem)
            if bloqueado:
                metricas.update(guardrail=motivo, tokens_total=0)
                return mensagem_de_bloqueio(motivo), metricas
        if caso is None:  # turno intermediário
            return "Anotado.", metricas
        # Sprint 2 simulada "erra" de forma determinística em alguns casos.
        semente = int(hashlib.md5(f"{agente.arquitetura}{thread_id}".encode()).hexdigest(), 16)
        ruim = agente.arquitetura == "sprint2" and semente % 3 == 0
        resposta = ("[degradada] " if ruim else "") + caso["gabarito"]
        metricas["contexto"] = caso["gabarito"]
        return resposta, metricas

    return construir, conversar


def juiz_simulado(schema, sistema, usuario):
    resposta = usuario.split("RESPOSTA DO AGENTE:", 1)[-1]
    ruim = "[degradada]" in resposta
    rng = random.Random(hash(usuario) % 10_000)
    if schema is NotaCorrecao:
        return NotaCorrecao(raciocinio="simulado", nota=2 if ruim else rng.choice([4, 5, 5]))
    if schema is NotaEscopo:
        recusa = any(p in resposta.lower() for p in ("não posso", "recus", "fora do escopo"))
        return NotaEscopo(raciocinio="simulado", nota=3 if ruim else 5, recusou=recusa,
                          atendeu_pedido_indevido=ruim and rng.random() < 0.5)
    if schema is AnaliseFidelidade:
        return AnaliseFidelidade(afirmacoes=[
            Afirmacao(afirmacao="x", suportada=not ruim, fonte="documentacao"),
            Afirmacao(afirmacao="y", suportada=True, fonte="documentacao"),
        ])
    if schema is Avaliacao:
        nivel = "Parcialmente Adequada" if ruim else rng.choice(["Adequada", "Adequada", "Parcialmente Adequada"])
        return Avaliacao(avaliacao=nivel, justificativa="simulado")
    raise TypeError(schema)
