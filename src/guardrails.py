import re

PADROES_INJECAO = [
    r"ignore?\s+(todas\s+)?(as\s+)?(suas\s+)?instru[çc][õo]es",
    r"ignore\s+(all\s+)?(your\s+)?(previous\s+)?instructions",
    r"esque[çc]a\s+(tudo|todas\s+as\s+instru[çc][õo]es|o\s+que\s+foi\s+dito)",
    r"(revele|mostre|exiba|imprima|repita|me\s+d[êe])\s+(o\s+seu|seu|o)\s+(system\s+)?prompt",
    r"system\s+prompt\s+(completo|na\s+[íi]ntegra|acima)",
    r"quais\s+s[ãa]o\s+(as\s+)?suas\s+instru[çc][õo]es",
    r"(voc[êe]|agora\s+voc[êe])\s+n[ãa]o\s+trabalha\s+mais\s+para",
    r"a\s+partir\s+de\s+agora\s+voc[êe]\s+[ée]\s+",
    r"(modo|no)\s+(desenvolvedor|developer\s+mode|dan)\b",
    r"finja\s+que\s+voc[êe]\s+(n[ãa]o\s+tem|n[ãa]o\s+possui)\s+(regras|restri[çc][õo]es)",
    r"sem\s+(nenhuma\s+)?restri[çc][ãa]o",
    r"responda\s+qualquer\s+(pergunta|coisa)\s+que\s+eu\s+(fizer|perguntar)",
]

PADROES_SEGURANCA_ELETRICA = [
    r"(desativar|desabilitar|burlar|contornar|pular|by-?pass\w*)\s+(o\s+|a\s+|as\s+|os\s+)?"
    r"(disjuntor|dr\b|prote[çc][ãa]o|prote[çc][õo]es|aterramento|trava|limite\s+de\s+corrente)",
    r"(sem|dispensar)\s+(o\s+)?aterramento",
    r"(abrir|mexer|trocar|intervir)\s+\w{0,12}\s*(com\s+)?(o\s+)?(equipamento|carregador|painel)\s+energizado",
    r"(ligar|religar)\s+.{0,30}(mesmo\s+com|ignorando)\s+.{0,20}(e-?09|falha\s+de\s+aterramento)",
    r"aumentar\s+a\s+corrente\s+acima\s+d(o|a)\s+(limite|nominal|disjuntor)",
]

# Trechos que nunca devem aparecer numa resposta: indicam vazamento do prompt.
MARCADORES_VAZAMENTO = [
    "## identidade e escopo",
    "## confidencialidade",
    "## limites profissionais",
    "## ferramenta disponível",
    "você é o chargegrid ai, assistente técnico-operacional",
]


def _bate(texto, padroes):
    texto = texto.lower()
    return any(re.search(p, texto) for p in padroes)


def verificar_entrada(texto):
    """Retorna (bloqueado: bool, motivo: str | None)."""
    if _bate(texto, PADROES_INJECAO):
        return True, "prompt_injection"
    if _bate(texto, PADROES_SEGURANCA_ELETRICA):
        return True, "seguranca_eletrica"
    return False, None


def verificar_saida(texto):
    """Detecta vazamento do system prompt na resposta gerada."""
    minusculo = texto.lower()
    if any(marcador in minusculo for marcador in MARCADORES_VAZAMENTO):
        return True, "vazamento_prompt"
    return False, None


AVISO_PROFISSIONAL = {
    "juridico": r"\b(jur[íi]dic|legal|contrato|processo|lgpd|tribut|imposto|icms|nota\s+fiscal)",
    "financeiro": r"\b(investi|retorno\s+financeiro|payback|roi\b|financiamento|empr[ée]stimo)",
}


def exige_aviso_profissional(texto):
    """Categorias que exigem encaminhamento a profissional habilitado.

    Usado pelos testes para verificar se o agente incluiu o disclaimer devido.
    """
    return [
        categoria
        for categoria, padrao in AVISO_PROFISSIONAL.items()
        if re.search(padrao, texto.lower())
    ]
