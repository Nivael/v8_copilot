from answer_engine import card_stock_research_overview
from evals.run_answerability_eval import evaluate


def test_real_question_answerability_gate() -> None:
    assert evaluate() == (20, 20)


def test_stock_overview_binds_only_relevant_control_methodology_lenses() -> None:
    card = card_stock_research_overview(
        "603398",
        "沐邦的股东人数、股权和控制权变化怎么看？",
        ["shareholder_count", "equity", "control_structure"],
    )
    card.validate()
    release_ids = {invocation.release_id for invocation in card.lens_invocations}
    assert release_ids == {"RL-C-002", "RL-C-003"}
    assert "RL-A-003" not in release_ids
