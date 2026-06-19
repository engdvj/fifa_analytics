"""Motor de pontuação: spec JSONB -> pontos."""

from api.app.scoring.engine import BUILTIN_RULES, score_prediction


def test_exact_score_vale_o_maior_criterio():
    # Clássico: exato=5, vencedor=3. Acertar o placar não soma os dois (vale o maior).
    spec = BUILTIN_RULES["Clássico"]["spec"]
    assert score_prediction(spec, (2, 0), (2, 0)) == 5
    # acertou só o vencedor (mandante) → 3
    assert score_prediction(spec, (1, 0), (3, 1)) == 3
    # errou tudo → 0
    assert score_prediction(spec, (0, 2), (3, 1)) == 0


def test_modo_sum_acumula_criterios():
    spec = BUILTIN_RULES["Soma de acertos"]["spec"]
    # 1x1 vs 1x1: vencedor(empate)=2 + home=1 + away=1 = 4
    assert score_prediction(spec, (1, 1), (1, 1)) == 4
    # 2x1 vs 3x1: vencedor(mandante)=2 + away=1 = 3 (home errado)
    assert score_prediction(spec, (2, 1), (3, 1)) == 3


def test_saldo_de_gols():
    spec = {"correct_goal_diff": 4}
    assert score_prediction(spec, (2, 0), (3, 1)) == 4  # ambos saldo +2
    assert score_prediction(spec, (2, 0), (1, 0)) == 0  # +2 vs +1


def test_criterio_desconhecido_e_ignorado():
    # robustez p/ regra criada pelo usuário com chave inválida
    spec = {"inexistente": 99, "exact_score": 5}
    assert score_prediction(spec, (1, 1), (1, 1)) == 5
