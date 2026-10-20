"""Renderização das tabelas em Markdown (usadas no resumo e no relatório)."""

from avaliacao.analise import NOMES_METRICAS
from avaliacao.golden_dataset import CATEGORIAS

LINHAS_TABELA_PRINCIPAL = [
    "correcao",
    "aderencia_escopo",
    "fidelidade",
    "recusa_correta",
    "nota_final",
    "recusa_indevida",
    "veredito",
    "pct_adequadas",
    "tokens_por_turno",
    "latencia_s",
]


def _fmt(resumo, chave):
    if not resumo or resumo.get("media") is None:
        return "—"
    media, dp = resumo["media"], resumo.get("dp") or 0
    if chave == "pct_adequadas":
        return f"{media:.0f}% ± {dp:.0f}"
    if chave == "tokens_por_turno":
        return f"{media:.0f} ± {dp:.0f}"
    if chave == "latencia_s":
        return f"{media:.2f} ± {dp:.2f}"
    texto = f"{media:.3f} ± {dp:.3f}"
    return f"**{texto}**" if chave == "nota_final" else texto


def _num(valor, casas=2):
    return "—" if valor is None else f"{valor:.{casas}f}"


def tabela_versoes(agregados):
    """Tabela OBRIGATÓRIA: colunas = versões, linhas = métricas (média ± dp)."""
    versoes = list(agregados)
    cab = "| Métrica | " + " | ".join(versoes) + " |"
    sep = "|---|" + "---|" * len(versoes)
    linhas = [cab, sep]
    for chave in LINHAS_TABELA_PRINCIPAL:
        celulas = [_fmt(agregados[v].get(chave), chave) for v in versoes]
        linhas.append(f"| {NOMES_METRICAS[chave]} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def tabela_categorias(agregados):
    versoes = list(agregados)
    linhas = ["| Categoria | " + " | ".join(versoes) + " |", "|---|" + "---|" * len(versoes)]
    for cat in CATEGORIAS:
        celulas = [_fmt(agregados[v].get(f"categoria:{cat}"), cat) for v in versoes]
        linhas.append(f"| {cat} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def tabela_guardrail(agregados):
    linhas = [
        "| Versão | Bloqueios esperados (casos × execuções) | Ocorridos | Cobertura | Falsos positivos | Casos esperados e não bloqueados |",
        "|---|---|---|---|---|---|",
    ]
    for versao, a in agregados.items():
        g = a["guardrail"]
        if versao.startswith("sprint2"):
            linhas.append(f"| {versao} | {g['esperados']} | — | não existia na Sprint 2 | — | — |")
            continue
        cobertura = "—" if g["cobertura"] is None else f"{100 * g['cobertura']:.0f}%"
        nao = ", ".join(g["casos_esperados_nao_bloqueados"]) or "—"
        linhas.append(
            f"| {versao} | {g['esperados']} | {g['ocorridos']} | {cobertura} | "
            f"{g['falsos_positivos']} | {nao} |"
        )
    return "\n".join(linhas)


def tabela_por_caso(casos_por_versao):
    """Nota do caso (média das 4 métricas) por versão, lado a lado."""
    versoes = list(casos_por_versao)
    ids = list(next(iter(casos_por_versao.values())).keys()) if versoes else []
    cab = "| Caso | Categoria | " + " | ".join(f"{v} (nota / veredito)" for v in versoes) + " |"
    linhas = [cab, "|---|---|" + "---|" * len(versoes)]
    for caso_id in ids:
        base = casos_por_versao[versoes[0]][caso_id]
        celulas = []
        for v in versoes:
            linha = casos_por_versao[v].get(caso_id)
            if not linha:
                celulas.append("—")
                continue
            ver = linha["veredito_majoritario"] or "—"
            instavel = "" if linha["veredito_estavel"] else " ⚠"
            bloqueio = " 🛡" if linha["bloqueado"] else ""
            celulas.append(f"{_num(linha['nota_caso'])} / {ver}{instavel}{bloqueio}")
        linhas.append(f"| {caso_id} | {base['categoria']} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def tabela_metricas_por_caso(casos, versao):
    linhas = [
        f"| Caso | Correção | Escopo | Fidelidade | Recusa correta | Recusa indevida | Vereditos ({versao}) |",
        "|---|---|---|---|---|---|---|",
    ]
    for caso_id, l in casos.items():
        linhas.append(
            f"| {caso_id} | {_num(l['correcao'])} | {_num(l['aderencia_escopo'])} | "
            f"{_num(l['fidelidade'])} | {_num(l['recusa_correta'])} | "
            f"{_num(l['recusa_indevida'])} | {', '.join(l['vereditos']) or '—'} |"
        )
    return "\n".join(linhas)


def tabela_confronto(confronto):
    linhas = [
        "| Caso | Manual (Sprint 3) | Pipeline (veredito) | Pipeline (correção) | Concorda? | Vereditos por execução |",
        "|---|---|---|---|---|---|",
    ]
    for l in confronto["casos"]:
        ok = "✅" if l["concorda"] else "❌"
        linhas.append(
            f"| {l['id']} | {l['manual']} | {l['pipeline_veredito'] or '—'} | "
            f"{l['pipeline_correcao'] or '—'} ({_num(l['correcao'])}) | {ok} | "
            f"{', '.join(l['vereditos'])} |"
        )
    return "\n".join(linhas)
