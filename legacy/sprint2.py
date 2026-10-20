"""Arquitetura da Sprint 2 reempacotada para ser medida pela mesma suíte.

Isto é o código antigo — chamadas manuais ao client, histórico como lista
Python, RAG injetado no system prompt a cada turno, contexto técnico inteiro
dentro do prompt — exposto com a mesma interface de `src.agent`
(`construir_agente` / `conversar`), para que `tests/run_tests.py` consiga rodar
exatamente os mesmos casos nas duas versões e gerar o comparativo do item 6.

Nada aqui deve ser "melhorado": o valor deste arquivo é ser fiel à Sprint 2.
"""

import os
from collections import defaultdict

from openai import OpenAI

from src.rag import obter_store

# System prompt da Sprint 2: contexto técnico inteiro embutido, sem ferramentas,
# sem seção de confidencialidade e sem limites profissionais explícitos.
SYSTEM_PROMPT_SPRINT2 = """
Você é o ChargeGrid AI, assistente técnico-operacional especializado em infraestrutura
de carregamento de veículos elétricos da GoodWe, no contexto do programa ChargeGrid
Intelligence.

## IDENTIDADE E ESCOPO
Seu único domínio de atuação é a gestão operacional de eletropostos GoodWe em
ambientes comerciais. Você atende OPERADOR COMERCIAL e TÉCNICO DE CAMPO.

## FORA DO ESCOPO
- Recomendações de veículos elétricos para compra;
- Assuntos não relacionados a eletropostos GoodWe;
- Questões jurídicas, financeiras ou tributárias;
- Concorrentes da GoodWe.

## ESTILO DE RESPOSTA
- Linguagem técnica porém acessível; listas numeradas para procedimentos;
- Alertas de segurança quando relevantes; ofereça um próximo passo.

## CONTEXTO TÉCNICO — EQUIPAMENTOS GOODWE
### Protocolos: OCPP 1.6 (JSON/WebSocket), OCPP 2.0.1 (Smart Charging, ISO 15118),
MQTT (telemetria), Modbus TCP/RTU.
### Conectores: Tipo 2 (IEC 62196-2, até 22 kW), CCS2 (DC até 150 kW), CHAdeMO.
### Códigos de erro:
E-01 falha de comunicação com o backend OCPP; E-02 temperatura do módulo acima do
limite (>65°C); E-03 falha no medidor de energia interno; E-04 falha na comunicação
com o conector (CP/PP); E-05 sobretensão na entrada (>260V AC); E-06 subtensão na
entrada (<185V AC); E-07 falha no módulo de pagamento/leitor; E-08 atualização de
firmware interrompida; E-09 falha de aterramento detectada; E-10 módulo de
balanceamento de carga não responde.
### Limites de corrente: usar 85-90% da capacidade nominal do disjuntor; mínimo de
6A por ponto em modo balanceado (IEC 61851-1); máximo típico 32A por conector Tipo 2.
### Painel do Operador: Dashboard; Eletropostos; Relatórios; Configurações >
Faturamento; Configurações > Energia; Configurações > Sistema; Suporte.

## HISTÓRICO DE CONVERSA
Você tem acesso ao histórico completo da conversa atual.
""".strip()


class AgenteSprint2:
    """Histórico em memória do processo, indexado por sessão (como era antes)."""

    def __init__(self, modelo="gpt-4o-mini", **parametros):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.modelo = modelo
        self.parametros = {"temperature": 0.2, "top_p": 0.9, "max_tokens": 900}
        self.parametros.update(parametros)
        self.historicos = defaultdict(list)

    def get_state(self, config):  # compatibilidade com a interface nova
        thread = config["configurable"]["thread_id"]
        return type("Estado", (), {"values": {"messages": self.historicos[thread]}})


def construir_agente(nome_modelo=None, checkpointer=None, **parametros):
    return AgenteSprint2(nome_modelo or "gpt-4o-mini", **parametros)


def conversar(agente, mensagem, thread_id):
    historico = agente.historicos[thread_id]

    # Sprint 2: busca semântica executada SEMPRE, e resultado concatenado no
    # system prompt na primeira mensagem da sessão.
    contexto = "".join(
        doc.page_content for doc in obter_store().similarity_search(mensagem, k=5)
    )

    if not historico:
        historico.append(
            {
                "role": "system",
                "content": SYSTEM_PROMPT_SPRINT2
                + f"\nUse o contexto como base para entender as perguntas e respostas: {contexto}",
            }
        )

    historico.append({"role": "user", "content": mensagem})

    completion = agente.client.chat.completions.create(
        model=agente.modelo, messages=historico, **agente.parametros
    )
    resposta = completion.choices[0].message.content
    historico.append({"role": "assistant", "content": resposta})

    uso = completion.usage
    metricas = {
        "tokens_entrada": uso.prompt_tokens,
        "tokens_saida": uso.completion_tokens,
        "tokens_total": uso.total_tokens,
        "guardrail": None,  # não existia camada determinística na Sprint 2
        "ferramentas": [],
        # Instrumentação da Sprint 04 (não muda o comportamento): o que o
        # modelo recebeu como documentação = contexto técnico embutido no
        # system prompt + trechos do RAG injetados na abertura da sessão.
        "contexto": historico[0]["content"],
    }
    return resposta, metricas
