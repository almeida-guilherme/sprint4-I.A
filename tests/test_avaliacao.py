"""Testes offline do pipeline da Sprint 04 (não chamam nenhuma API).

    python -m tests.test_avaliacao        (ou: pytest tests/test_avaliacao.py)
"""

from avaliacao import analise
from avaliacao.golden_dataset import CASOS, CATEGORIAS
from avaliacao.metricas import derivar_recusa
from src import guardrails
from tests.casos_teste import CASOS as CASOS_SPRINT3


def test_dataset_reaproveita_sprint3_sem_alterar():
    por_id = {c["id"]: c for c in CASOS}
    for original in CASOS_SPRINT3:
        novo = por_id[original["id"]]
        assert novo["turnos"] == original["turnos"]
        assert novo["criterio"] == original["criterio"]


def test_dataset_completo():
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids)), "ids duplicados"
    assert {c["categoria"] for c in CASOS} == set(CATEGORIAS)
    for c in CASOS:
        assert c["gabarito"].strip() and c["criterio"].strip() and c["turnos"], c["id"]


def test_casos_novos_de_bloqueio_batem_no_guardrail():
    # Só os casos NOVOS: S6 (Sprint 3) espera bloqueio mas o regex não o pega —
    # achado documentado no relatório, não corrigido aqui de propósito.
    for c in CASOS:
        if c["origem"] == "sprint4":
            bloqueado, _ = guardrails.verificar_entrada(c["turnos"][-1])
            assert bloqueado == c["espera_bloqueio"], c["id"]


def test_recusa():
    caso = {"comportamento": "recusar"}
    assert derivar_recusa(caso, {"recusou": False, "atendeu_pedido_indevido": False}, True)["recusa_correta"] == 1.0
    assert derivar_recusa(caso, {"recusou": True, "atendeu_pedido_indevido": True}, False)["recusa_correta"] == 0.0
    caso = {"comportamento": "responder"}
    assert derivar_recusa(caso, {"recusou": True, "atendeu_pedido_indevido": False}, False)["recusa_indevida"] == 1.0


def test_majoritario_e_kappa():
    assert analise._majoritario(["Adequada", "Adequada", "Inadequada"]) == "Adequada"
    assert analise._majoritario(["Adequada", "Inadequada"]) == "Inadequada"  # mediana inferior
    pares = [("Adequada", "Adequada"), ("Inadequada", "Inadequada"), ("Adequada", "Inadequada")]
    assert round(analise.kappa_cohen(pares), 2) == 0.40
    assert analise.veredito_por_correcao(0.75) == "Adequada"
    assert analise.veredito_por_correcao(0.5) == "Parcialmente Adequada"


def test_classificacao_empate_tecnico():
    def ag(nota, dp, recusa):
        return {"nota_final": {"media": nota, "dp": dp}, "recusa_correta": {"media": recusa, "dp": 0},
                "fidelidade": {"media": 0.9, "dp": 0}, "correcao": {"media": 0.9, "dp": 0},
                "aderencia_escopo": {"media": 0.9, "dp": 0}}
    r = analise.classificar({"a": ag(0.90, 0.03, 0.8), "b": ag(0.89, 0.03, 1.0)})
    assert r["empate_tecnico"] and r["vencedora"] == "b"
    r = analise.classificar({"a": ag(0.95, 0.01, 0.8), "b": ag(0.80, 0.01, 1.0)})
    assert not r["empate_tecnico"] and r["vencedora"] == "a"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok ", nome)
