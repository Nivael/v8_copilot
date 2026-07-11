from evals.run_answerability_eval import evaluate


def test_real_question_answerability_gate() -> None:
    assert evaluate() == (20, 20)
