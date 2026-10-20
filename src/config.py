import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()

MODELOS = {
    "gpt-4o-mini": {
        "model": "gpt-4o-mini",
        "provider": "openai",
        "chave": "OPENAI_API_KEY",
    },
    "gpt-4.1-mini": {
        "model": "gpt-4.1-mini",
        "provider": "openai",
        "chave": "OPENAI_API_KEY",
    },
    "gpt-4.1": {
        "model": "gpt-4.1",
        "provider": "openai",
        "chave": "OPENAI_API_KEY",
    },
    "gpt-4o": {
        "model": "gpt-4o",
        "provider": "openai",
        "chave": "OPENAI_API_KEY",
    },
    "gemini-2.5-flash": {
        "model": "gemini-2.5-flash",
        "provider": "google_genai",
        "chave": "GOOGLE_API_KEY",
    },
    "gemini-2.0-flash": {
        "model": "gemini-2.0-flash",
        "provider": "google_genai",
        "chave": "GOOGLE_API_KEY",
    },
}

PARAMETROS_PADRAO = {
    "temperature": 0.2,
    "top_p": 0.9,
    "max_tokens": 900,
}

MODELO_PADRAO = os.getenv("MODELO_PADRAO", "gpt-4o-mini")
MODELO_AVALIADOR = os.getenv("MODELO_AVALIADOR", "gpt-4o-mini")
# Juiz do pipeline da Sprint 04: modelo diferente (e maior) que o do agente,
# para reduzir o viés de autopreferência do LLM-as-a-judge.
MODELO_JUIZ = os.getenv("MODELO_JUIZ", "gpt-4.1")

CAMINHO_BASE_CONHECIMENTO = os.getenv("CAMINHO_BASE_CONHECIMENTO", "data")


def modelos_disponiveis():
    return [nome for nome, cfg in MODELOS.items() if os.getenv(cfg["chave"])]


def carregar_modelo(nome=None, **parametros):

    nome = nome or MODELO_PADRAO
    if nome not in MODELOS:
        raise ValueError(f"Modelo '{nome}' não está registrado em config.MODELOS")

    cfg = MODELOS[nome]
    if not os.getenv(cfg["chave"]):
        raise RuntimeError(
            f"Variável de ambiente {cfg['chave']} não encontrada. "
            "Copie .env.example para .env e preencha a chave."
        )

    config = {**PARAMETROS_PADRAO, **parametros}

    if cfg["provider"] == "google_genai" and "max_tokens" in config:
        config["max_output_tokens"] = config.pop("max_tokens")

    return init_chat_model(cfg["model"], model_provider=cfg["provider"], **config)


def carregar_embeddings():
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model="text-embedding-3-small")

    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

    raise RuntimeError(
        "Nenhuma chave de embeddings encontrada (OPENAI_API_KEY ou GOOGLE_API_KEY)."
    )
