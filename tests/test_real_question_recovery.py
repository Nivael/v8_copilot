import json

import answer_engine
from api import orchestrate
from api_contract import ResearchRequest
from evals.run_real_question_eval_v1 import evaluate


def ask(question: str):
    return orchestrate(ResearchRequest(question=question, llm_mode="off"))


def test_real_question_answerability_v1() -> None:
    assert evaluate() == (14, 14)


def test_answer_inventory_uses_validated_refresh_without_reading_body(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(answer_engine, "ANNOUNCEMENT_REFRESH_DIR", tmp_path)
    (tmp_path / "300068.json").write_text(json.dumps({
        "symbol": "300068",
        "source": "cninfo",
        "records": [{
            "announcement_id": "TEST-ANSWER-1",
            "announcement_date": "2026-07-08",
            "title": "关于被债权人申请预重整及重整的提示性公告",
            "url": "https://example.invalid/announcement.pdf",
            "body_text": None,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    response = ask("ST南都7月8日为什么被申请预重整和重整？")

    row = next(
        row for row in response.answer_card["body_rows"]
        if row.get("巨潮公告ID") == "TEST-ANSWER-1"
    )
    assert row["正文状态"] == "未采集，仅可核对标题与日期"
    assert "必须阅读公告正文" in response.narrative.uncertainties[0].text


def test_multi_stock_query_executes_a_two_stock_comparison() -> None:
    response = ask("比较ST亚光和ST南都最近一个月的公告密度。")

    assert response.route.route == "answer_query"
    assert response.answer_card is not None
    assert response.interpretation.object.kind == "cohort"
    assert response.route.matched_rules == ["stock_comparison_query"]
    rows = response.answer_card["body_rows"]
    assert {row["股票"] for row in rows} == {"300123", "300068"}
    assert all("近30日公告数量(共同截止)" in row for row in rows)


def test_answer_card_as_of_tracks_the_dimensions_used_by_the_question() -> None:
    announcement = ask("ST亚光7月8日公开招募重整投资人的公告说了什么？")
    announcement_and_price = ask("ST亚光7月8日公告后股价怎么走？")

    assert announcement.answer_card["as_of"] == "2026-07-08"
    assert announcement_and_price.answer_card["as_of"] == "2026-07-08"
