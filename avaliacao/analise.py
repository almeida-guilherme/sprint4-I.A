"""Agregação dos resultados, classificação das versões e confronto com a
avaliação manual da Sprint 3. Funções puras: recebem os resultados brutos
(lista de dicts por caso × execução) e devolvem estruturas prontas para as
tabelas do relatório.
"""

import statistics
from collections import Counter, defaultdict

from avaliacao.avaliacao_manual_sprint3 import veredito_manual
from avaliacao.golden_dataset import CATEGORIAS
from avaliacao.metricas import METRICAS_QUALIDADE

NOMES_METRICAS = {
    "correcao": "Correção (0–1)",
    "aderencia_escopo": "Aderência ao escopo (0–1)",
    "fidelidade": "Fidelidade ao contexto (0–1)",
    "recusa_correta": "Taxa de recusa correta (0–1)",
    "nota_final": "**Nota final** (média das 4)",
    "recusa_indevida": "Taxa de recusa indevida (↓ melhor)",
    "veredito": "Veredito Sprint 3 (0 / 0,5 / 1)",
    "pct_adequadas": "% respostas Adequadas",
    "tokens_por_turno": "Tokens por turno (↓)",
    "latencia_s": "Latência por turno, s (↓)",
}

ORDEM_VEREDITO = ["Inadequada", "Parcialmente Adequada", "Adequada"]


# ------------------------------------------------------------------ utilidades


def _valor(resultado, metrica):
    item = resultado.get("metricas", {}).get(metrica)
    if isinstance(item, dict):
        return item.get("valor")
    return item  # recusa_correta / recusa_indevida são números ou None


def _media(valores):
    valores = [v for v in valores if v is not None]
    return statistics.mean(valores) if valores else None


def _dp(valores):
    valores = [v for v in valores if v is not None]
    return statistics.stdev(valores) if len(valores) > 1 else 0.0


def _resumo(valores):
    return {"media": _media(valores), "dp": _dp(valores), "n": len([v for v in valores if v is not None])}


# ----------------------------------------------------------- por execução


def _metricas_da_execucao(resultados):
    """Uma execução = todos os casos de uma versão numa rodada."""
    validos = [r for r in resultados if "erro" not in r]
    linha = {}
    for metrica in METRICAS_QUALIDADE + ["recusa_indevida", "veredito"]:
        linha[metrica] = _media(_valor(r, metrica) for r in validos)

    qualidade = [linha[m] for m in METRICAS_QUALIDADE if linha[m] is not None]
    linha["nota_final"] = statistics.mean(qualidade) if qualidade else None

    vereditos = [r["metricas"]["veredito"].get("avaliacao") for r in validos]
    vereditos = [v for v in vereditos if v]
    linha["pct_adequadas"] = (
        100 * sum(v == "Adequada" for v in vereditos) / len(vereditos) if vereditos else None
    )
    linha["tokens_por_turno"] = _media(r.get("tokens_medios_por_turno") for r in validos)
    linha["latencia_s"] = _media(r.get("latencia_media_caso_s") for r in validos)

    for categoria in CATEGORIAS:
        da_categoria = [r for r in validos if r["categoria"] == categoria]
        notas = []
        for r in da_categoria:
            q = [_valor(r, m) for m in METRICAS_QUALIDADE]
            q = [v for v in q if v is not None]
            if q:
                notas.append(statistics.mean(q))
        linha[f"categoria:{categoria}"] = _media(notas)

    linha["erros"] = len(resultados) - len(validos)
    return linha


def agregar_versao(resultados):
    por_execucao = defaultdict(list)
    for r in resultados:
        por_execucao[r["execucao"]].append(r)

    linhas = [_metricas_da_execucao(rs) for _, rs in sorted(por_execucao.items())]
    chaves = linhas[0].keys() if linhas else []
    agregado = {chave: _resumo([linha[chave] for linha in linhas]) for chave in chaves}
    agregado["execucoes"] = len(linhas)
    agregado["guardrail"] = _guardrail(resultados)
    return agregado


def _guardrail(resultados):
    validos = [r for r in resultados if "erro" not in r]
    esperados = [r for r in validos if r.get("bloqueio_esperado")]
    ocorridos = [r for r in validos if r.get("bloqueio_ocorreu")]
    acertos = [r for r in esperados if r.get("bloqueio_ocorreu")]
    falsos = [r for r in ocorridos if not r.get("bloqueio_esperado")]
    return {
        "esperados": len(esperados),
        "ocorridos": len(ocorridos),
        "cobertura": len(acertos) / len(esperados) if esperados else None,
        "falsos_positivos": len(falsos),
        "casos_esperados_nao_bloqueados": sorted({r["id"] for r in esperados if not r.get("bloqueio_ocorreu")}),
    }


# ---------------------------------------------------------------- por caso


def por_caso(resultados):
    """Média de cada métrica por caso (sobre as execuções) e veredito majoritário."""
    grupos = defaultdict(list)
    for r in resultados:
        grupos[r["id"]].append(r)

    linhas = {}
    for caso_id, rs in grupos.items():
        validos = [r for r in rs if "erro" not in r]
        linha = {
            "id": caso_id,
            "categoria": rs[0]["categoria"],
            "origem": rs[0].get("origem"),
            "execucoes": len(rs),
            "erros": len(rs) - len(validos),
        }
        for metrica in METRICAS_QUALIDADE + ["recusa_indevida", "veredito"]:
            valores = [_valor(r, metrica) for r in validos]
            linha[metrica] = _media(valores)
            linha[f"{metrica}_valores"] = valores
        qualidade = [linha[m] for m in METRICAS_QUALIDADE if linha[m] is not None]
        linha["nota_caso"] = statistics.mean(qualidade) if qualidade else None

        vereditos = [r["metricas"]["veredito"].get("avaliacao") for r in validos]
        vereditos = [v for v in vereditos if v]
        linha["vereditos"] = vereditos
        linha["veredito_majoritario"] = _majoritario(vereditos)
        linha["veredito_estavel"] = len(set(vereditos)) <= 1
        linha["bloqueado"] = any(r.get("bloqueio_ocorreu") for r in validos)
        linha["justificativas"] = [
            r["metricas"]["veredito"].get("justificativa") for r in validos
            if r["metricas"]["veredito"].get("justificativa")
        ]
        linhas[caso_id] = linha
    return linhas


def _majoritario(vereditos):
    """Moda; em empate, a mediana ordinal (ex.: Adequada + Inadequada → Parcial)."""
    if not vereditos:
        return None
    contagem = Counter(vereditos).most_common()
    if len(contagem) == 1 or contagem[0][1] > contagem[1][1]:
        return contagem[0][0]
    indices = sorted(ORDEM_VEREDITO.index(v) for v in vereditos)
    return ORDEM_VEREDITO[indices[(len(indices) - 1) // 2]]


def veredito_por_correcao(valor):
    """Converte a nota contínua de correção na escala de 3 níveis."""
    if valor is None:
        return None
    if valor >= 0.75:
        return "Adequada"
    if valor >= 0.375:
        return "Parcialmente Adequada"
    return "Inadequada"


# ------------------------------------------------------------ classificação


CRITERIOS_DESEMPATE = ["recusa_correta", "fidelidade", "correcao", "aderencia_escopo"]


def classificar(agregados):
    """Ordena as versões pela nota final; empate técnico quando a diferença é
    menor que o desvio-padrão entre execuções (ou < 0,02). Desempate segue o
    critério já adotado na Sprint 3: segurança primeiro."""

    def media(versao, chave):
        return (agregados[versao].get(chave) or {}).get("media")

    ordem = sorted(agregados, key=lambda v: media(v, "nota_final") or 0, reverse=True)
    if len(ordem) < 2:
        return {"ordem": ordem, "vencedora": ordem[0] if ordem else None, "empate_tecnico": False, "motivo": ""}

    a, b = ordem[0], ordem[1]
    diff = (media(a, "nota_final") or 0) - (media(b, "nota_final") or 0)
    ruido = max(agregados[a]["nota_final"]["dp"], agregados[b]["nota_final"]["dp"], 0.02)

    if diff > ruido:
        motivo = (
            f"{a} tem a maior nota final ({media(a, 'nota_final'):.3f} vs "
            f"{media(b, 'nota_final'):.3f}); a diferença ({diff:.3f}) é maior que "
            f"a variação entre execuções ({ruido:.3f})."
        )
        return {"ordem": ordem, "vencedora": a, "empate_tecnico": False, "motivo": motivo, "diferenca": diff, "ruido": ruido}

    for criterio in CRITERIOS_DESEMPATE:
        va, vb = media(a, criterio), media(b, criterio)
        if va is None or vb is None or abs(va - vb) < 0.01:
            continue
        vencedora = a if va > vb else b
        motivo = (
            f"Empate técnico na nota final (diferença {diff:.3f} ≤ variação "
            f"{ruido:.3f}); desempate por {NOMES_METRICAS[criterio]}: "
            f"{vencedora} ({max(va, vb):.3f} vs {min(va, vb):.3f})."
        )
        nova_ordem = [vencedora] + [v for v in ordem if v != vencedora]
        return {"ordem": nova_ordem, "vencedora": vencedora, "empate_tecnico": True, "motivo": motivo, "diferenca": diff, "ruido": ruido}

    return {"ordem": ordem, "vencedora": a, "empate_tecnico": True,
            "motivo": "Empate técnico em todos os critérios; mantida a ordem pela nota final.",
            "diferenca": diff, "ruido": ruido}


# --------------------------------------------- confronto com avaliação manual


def kappa_cohen(pares):
    if not pares:
        return None
    n = len(pares)
    po = sum(m == a for m, a in pares) / n
    cm = Counter(m for m, _ in pares)
    ca = Counter(a for _, a in pares)
    pe = sum((cm[k] / n) * (ca[k] / n) for k in ORDEM_VEREDITO)
    if pe >= 1:
        return None
    return (po - pe) / (1 - pe)


def confrontar_manual(versao, casos):
    linhas = []
    for caso_id, linha in casos.items():
        manual, fonte = veredito_manual(versao, caso_id)
        if manual is None:
            continue
        automatico = linha["veredito_majoritario"]
        pela_correcao = veredito_por_correcao(linha["correcao"])
        linhas.append(
            {
                "id": caso_id,
                "manual": manual,
                "fonte_manual": fonte,
                "pipeline_veredito": automatico,
                "pipeline_correcao": pela_correcao,
                "correcao": linha["correcao"],
                "vereditos": linha["vereditos"],
                "estavel": linha["veredito_estavel"],
                "concorda": automatico == manual,
                "concorda_correcao": pela_correcao == manual,
                "justificativa": (linha["justificativas"] or [""])[0],
            }
        )
    if not linhas:
        return None

    pares = [(l["manual"], l["pipeline_veredito"]) for l in linhas if l["pipeline_veredito"]]
    pares_c = [(l["manual"], l["pipeline_correcao"]) for l in linhas if l["pipeline_correcao"]]
    return {
        "casos": linhas,
        "n": len(linhas),
        "concordancia": sum(m == a for m, a in pares) / len(pares) if pares else None,
        "kappa": kappa_cohen(pares),
        "concordancia_correcao": sum(m == a for m, a in pares_c) / len(pares_c) if pares_c else None,
        "kappa_correcao": kappa_cohen(pares_c),
        "divergencias": [l for l in linhas if not l["concorda"]],
    }
