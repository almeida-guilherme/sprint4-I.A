from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src import config, guardrails
from src.prompts import SYSTEM_PROMPT, mensagem_de_bloqueio
from src.rag import FERRAMENTAS

LIMITE_TOKENS_HISTORICO = 4000


class Estado(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    bloqueado: bool
    motivo: str | None


def _guardrail_entrada(estado: Estado) -> dict:
    ultima = estado["messages"][-1]
    texto = ultima.content if isinstance(ultima, HumanMessage) else ""
    bloqueado, motivo = guardrails.verificar_entrada(str(texto))
    return {"bloqueado": bloqueado, "motivo": motivo}


def _resposta_bloqueio(estado: Estado) -> dict:
    resposta = mensagem_de_bloqueio(estado.get("motivo"))
    return {
        "messages": [
            AIMessage(
                content=resposta,
                response_metadata={"guardrail": estado.get("motivo")},
            )
        ]
    }


def _rotear_guardrail(estado: Estado) -> str:
    return "resposta_bloqueio" if estado.get("bloqueado") else "call_llm"


def construir_agente(nome_modelo=None, checkpointer=None, **parametros_modelo):

    modelo = config.carregar_modelo(nome_modelo, **parametros_modelo).bind_tools(
        FERRAMENTAS
    )

    def call_llm(estado: Estado) -> dict:
        historico = trim_messages(
            estado["messages"],
            max_tokens=LIMITE_TOKENS_HISTORICO,
            strategy="last",
            token_counter=modelo,
            include_system=False,
            start_on="human",
            allow_partial=False,
        )
        resposta = modelo.invoke([SystemMessage(content=SYSTEM_PROMPT), *historico])

        if isinstance(resposta.content, str):
            vazou, motivo = guardrails.verificar_saida(resposta.content)
            if vazou:
                return {
                    "messages": [
                        AIMessage(
                            content=mensagem_de_bloqueio("prompt_injection"),
                            response_metadata={
                                "guardrail": motivo,
                                **(resposta.response_metadata or {}),
                            },
                            usage_metadata=resposta.usage_metadata,
                        )
                    ],
                    "bloqueado": True,
                    "motivo": motivo,
                }

        return {"messages": [resposta]}

    grafo = StateGraph(Estado)
    grafo.add_node("guardrail_entrada", _guardrail_entrada)
    grafo.add_node("resposta_bloqueio", _resposta_bloqueio)
    grafo.add_node("call_llm", call_llm)
    grafo.add_node("ferramentas", ToolNode(FERRAMENTAS))

    grafo.add_edge(START, "guardrail_entrada")
    grafo.add_conditional_edges(
        "guardrail_entrada",
        _rotear_guardrail,
        {"resposta_bloqueio": "resposta_bloqueio", "call_llm": "call_llm"},
    )
    grafo.add_edge("resposta_bloqueio", END)
    grafo.add_conditional_edges(
        "call_llm", tools_condition, {"tools": "ferramentas", END: END}
    )
    grafo.add_edge("ferramentas", "call_llm")

    return grafo.compile(checkpointer=checkpointer or MemorySaver())


def conversar(agente, mensagem, thread_id):

    cfg = {"configurable": {"thread_id": thread_id}}

    # Quantas mensagens já existiam na sessão, para medir só o turno atual.
    anterior = agente.get_state(cfg)
    ja_existiam = len((anterior.values or {}).get("messages", []))

    resultado = agente.invoke(
        {"messages": [HumanMessage(content=mensagem)], "bloqueado": False, "motivo": None},
        config=cfg,
    )

    resposta = resultado["messages"][-1]
    novas = resultado["messages"][ja_existiam:]

    entrada = saida = 0
    ferramentas_usadas = []
    for msg in novas:
        if isinstance(msg, AIMessage):
            uso = msg.usage_metadata or {}
            entrada += uso.get("input_tokens", 0)
            saida += uso.get("output_tokens", 0)
            ferramentas_usadas += [tc["name"] for tc in (msg.tool_calls or [])]

    # Tudo o que o agente recebeu como fonte nesta sessão: o system prompt (que
    # traz limites profissionais, NR-10 etc.) + os retornos da ferramenta RAG.
    # Mesma definição usada na Sprint 2 (system prompt com o contexto embutido),
    # para a métrica de fidelidade da Sprint 04 ser simétrica entre as versões.
    recuperado = "\n\n".join(
        str(msg.content) for msg in resultado["messages"] if isinstance(msg, ToolMessage)
    )
    contexto = f"[SYSTEM PROMPT DO AGENTE]\n{SYSTEM_PROMPT}\n\n[RETORNOS DA FERRAMENTA buscar_manual]\n" + (
        recuperado or "(a ferramenta não foi chamada nesta sessão)"
    )

    metricas = {
        "tokens_entrada": entrada,
        "tokens_saida": saida,
        "tokens_total": entrada + saida,
        "guardrail": (resposta.response_metadata or {}).get("guardrail"),
        "ferramentas": ferramentas_usadas,
        "contexto": contexto,
    }
    return resposta.content, metricas
