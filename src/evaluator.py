from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src import config
from src.prompts import AVALIADOR_PROMPT

NOTAS = {"Adequada": 1.0, "Parcialmente Adequada": 0.5, "Inadequada": 0.0}


class Avaliacao(BaseModel):
    avaliacao: Literal["Adequada", "Parcialmente Adequada", "Inadequada"] = Field(
        description="Classificação da resposta frente ao critério esperado."
    )
    justificativa: str = Field(
        description="Uma ou duas frases explicando a classificação."
    )


_avaliador = None


def obter_avaliador():
    global _avaliador
    if _avaliador is None:
        modelo = config.carregar_modelo(config.MODELO_AVALIADOR, temperature=0)
        _avaliador = modelo.with_structured_output(Avaliacao)
    return _avaliador


def avaliar(pergunta, resposta, criterio):
    entrada = (
        f"CRITÉRIO ESPERADO:\n{criterio}\n\n"
        f"PERGUNTA DO USUÁRIO:\n{pergunta}\n\n"
        f"RESPOSTA DO AGENTE:\n{resposta}"
    )
    resultado = obter_avaliador().invoke(
        [SystemMessage(content=AVALIADOR_PROMPT), HumanMessage(content=entrada)]
    )
    return resultado, NOTAS[resultado.avaliacao]
