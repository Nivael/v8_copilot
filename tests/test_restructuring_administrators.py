import json
import sqlite3
from datetime import date

import pytest

from restructuring_administrators import (
    AdministratorEntityType,
    AdministratorRepository,
    AnnouncementSourceRow,
    AppointmentKind,
    ParticipationRole,
    RestructuringEventType,
    classify_restructuring_milestone,
    extract_administrator_appointment,
    materialize_administrator_facts,
)


def _row(
    *,
    announcement_id: str = "A-1",
    symbol: str = "603398",
    announcement_date: str = "2025-11-20",
    title: str = "关于法院启动预重整并指定临时管理人的公告",
    statement: str = (
        "2025年11月19日，公司收到法院决定书，"
        "法院指定北京市金杜（深圳）律师事务所担任公司预重整临时管理人。"
    ),
) -> AnnouncementSourceRow:
    body = (
        "江西沐邦高科股份有限公司关于预重整事项的公告。"
        + statement
        + "公司能否进入正式重整程序存在重大不确定性，敬请投资者注意风险。"
        + "本公司董事会保证信息披露内容真实、准确、完整。"
    ) * 3
    return AnnouncementSourceRow(
        announcement_id=announcement_id,
        symbol=symbol,
        announcement_date=date.fromisoformat(announcement_date),
        title=title,
        url=f"https://example.test/{announcement_id}",
        body_text=body,
        source="cninfo",
    )


def test_extracts_law_firm_with_exact_source_and_effective_date() -> None:
    result = extract_administrator_appointment(_row())

    assert result.accepted is True
    assert result.source_document is not None
    assert "指定北京市金杜（深圳）律师事务所担任" in result.source_document.evidence_quote
    assert result.organizations[0].canonical_name == "北京市金杜（深圳）律师事务所"
    assert result.organizations[0].entity_type == AdministratorEntityType.LAW_FIRM
    assignment = result.assignments[0]
    assert assignment.appointment_kind == AppointmentKind.TEMPORARY_ADMINISTRATOR
    assert assignment.participation_role == ParticipationRole.SOLE
    assert assignment.effective_date == date(2025, 11, 19)
    assert result.events[0].information_available_date == date(2025, 11, 20)


def test_restructuring_milestone_title_classifier_is_subject_safe() -> None:
    assert classify_restructuring_milestone(
        "关于公开招募和遴选重整投资人的公告"
    ) == RestructuringEventType.INVESTOR_RECRUITMENT_STARTED
    assert classify_restructuring_milestone(
        "关于法院裁定批准重整计划的公告"
    ) == RestructuringEventType.RESTRUCTURING_PLAN_APPROVED
    assert classify_restructuring_milestone(
        "关于控股子公司重整计划执行完毕的公告"
    ) is None


def test_extracts_joint_administrators_without_merging_entities() -> None:
    result = extract_administrator_appointment(_row(
        statement=(
            "2025年11月24日，法院指定深圳诚信会计师事务所（特殊普通合伙）"
            "和君合律师事务所共同担任公司管理人。"
        ),
        title="关于法院裁定受理重整并指定管理人的公告",
    ))

    assert [item.canonical_name for item in result.organizations] == [
        "深圳诚信会计师事务所（特殊普通合伙）",
        "君合律师事务所",
    ]
    assert [item.participation_role for item in result.assignments] == [
        ParticipationRole.JOINT,
        ParticipationRole.JOINT,
    ]
    assert all(
        item.appointment_kind == AppointmentKind.ADMINISTRATOR
        for item in result.assignments
    )


def test_expands_generic_company_liquidation_group_name() -> None:
    result = extract_administrator_appointment(_row(
        symbol="603007",
        statement=(
            "2022年5月25日，法院指定公司清算组担任公司预重整期间的临时管理人。"
        ),
    ))

    assert result.organizations[0].canonical_name == "江西沐邦高科股份有限公司清算组"
    assert result.organizations[0].entity_type == AdministratorEntityType.LIQUIDATION_GROUP
    assert result.aliases[0].alias == "公司清算组"
    assert result.aliases[0].organization_id == result.organizations[0].organization_id


def test_related_entity_title_fails_closed() -> None:
    result = extract_administrator_appointment(_row(
        title="关于控股子公司被指定管理人的公告",
    ))

    assert result.accepted is False
    assert result.rejection is not None
    assert result.rejection.reason == "related_entity_title"


def test_current_issuer_appointment_outranks_subsidiary_history() -> None:
    result = extract_administrator_appointment(_row(
        symbol="600165",
        statement=(
            "2024年4月，法院指定惠农区人民政府成立的清算组"
            "担任宁夏中科生物新材料有限公司临时管理人。"
            "2024年5月30日，法院指定惠农区人民政府成立的清算组"
            "担任江西沐邦高科股份有限公司临时管理人。"
        ),
    ))

    assert result.accepted is True
    assert result.assignments[0].effective_date == date(2024, 5, 30)
    assert result.organizations[0].canonical_name == "惠农区人民政府成立的清算组"
    assert "江西沐邦高科股份有限公司临时管理人" in (
        result.source_document.evidence_quote
    )


def test_repository_is_idempotent_and_conflicts_fail(tmp_path) -> None:
    database = tmp_path / "administrators.sqlite3"
    repository = AdministratorRepository(database)
    result = extract_administrator_appointment(_row())

    repository.persist(result)
    repository.persist(result)
    assert repository.status()["counts"]["administrator_assignments"] == 1

    changed = result.model_copy(update={
        "source_document": result.source_document.model_copy(
            update={"evidence_quote": "changed"}
        )
    })
    with pytest.raises(ValueError, match="已冻结"):
        repository.persist(changed)


def test_status_is_read_only_and_reports_invalid_store(tmp_path) -> None:
    database = tmp_path / "invalid.sqlite3"
    database.write_bytes(b"")

    status = AdministratorRepository(database).status()

    assert status["status"] == "invalid"
    assert database.stat().st_size == 0


def test_materializer_links_later_formal_notice_to_same_case(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "administrators.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute(
            "create table company_announcements ("
            "announcement_id text,symbol text,announcement_date text,published_at text,"
            "title text,url text,body_text text,source text)"
        )
        pre = _row(
            announcement_id="PRE",
            symbol="603007",
            announcement_date="2022-05-25",
            statement=(
                "2022年5月25日，法院作出（2022）苏11破申3号之一决定书，"
                "指定花王生态工程股份有限公司清算组担任临时管理人。"
            ),
        )
        formal = _row(
            announcement_id="FORMAL",
            symbol="603007",
            announcement_date="2024-09-12",
            title="关于法院裁定受理重整并指定管理人的公告",
            statement=(
                "2024年9月12日，法院指定花王生态工程股份有限公司清算组"
                "担任公司管理人。"
            ),
        )
        for item in (pre, formal):
            connection.execute(
                "insert into company_announcements values (?,?,?,?,?,?,?,?)",
                (
                    item.announcement_id,
                    item.symbol,
                    item.announcement_date.isoformat(),
                    item.published_at,
                    item.title,
                    item.url,
                    item.body_text,
                    item.source,
                ),
            )

    summary = materialize_administrator_facts(
        source_database=source,
        database=destination,
    )

    assert summary.documents_accepted == 2
    status = AdministratorRepository(destination).status()
    assert status["counts"]["restructuring_cases"] == 1
    assert status["counts"]["administrator_assignments"] == 2


def test_materializer_can_consume_validated_cninfo_body_cache(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "administrators.sqlite3"
    cache_dir = tmp_path / "body_cache"
    row = _row(announcement_id="1234567890")
    with sqlite3.connect(source) as connection:
        connection.execute(
            "create table company_announcements ("
            "announcement_id text,symbol text,announcement_date text,published_at text,"
            "title text,url text,body_text text,source text)"
        )
        connection.execute(
            "insert into company_announcements values (?,?,?,?,?,?,?,?)",
            (
                row.announcement_id,
                row.symbol,
                row.announcement_date.isoformat(),
                "",
                row.title,
                row.url,
                None,
                row.source,
            ),
        )
    path = cache_dir / row.announcement_id[:4] / f"{row.announcement_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "announcement_id": row.announcement_id,
        "announcement_date": row.announcement_date.isoformat(),
        "source_url": row.url,
        "page_count": 3,
        "text": row.body_text,
        "source": "downloaded_pdf",
    }), encoding="utf-8")

    summary = materialize_administrator_facts(
        source_database=source,
        database=destination,
        body_cache_dir=cache_dir,
    )

    assert summary.candidates_scanned == 1
    assert summary.documents_accepted == 1


def test_materializer_merges_legal_form_suffix_as_sourced_alias(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "administrators.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute(
            "create table company_announcements ("
            "announcement_id text,symbol text,announcement_date text,published_at text,"
            "title text,url text,body_text text,source text)"
        )
        for announcement_id, name in (
            ("A1", "深圳诚信会计师事务所"),
            ("A2", "深圳诚信会计师事务所（特殊普通合伙）"),
        ):
            row = _row(
                announcement_id=announcement_id,
                symbol="600589",
                statement=(
                    "2023年9月6日，法院作出（2023）粤52破申6号决定书，"
                    f"指定{name}担任公司预重整期间管理人。"
                ),
            )
            connection.execute(
                "insert into company_announcements values (?,?,?,?,?,?,?,?)",
                (
                    row.announcement_id,
                    row.symbol,
                    row.announcement_date.isoformat(),
                    "",
                    row.title,
                    row.url,
                    row.body_text,
                    row.source,
                ),
            )

    materialize_administrator_facts(
        source_database=source,
        database=destination,
    )
    status = AdministratorRepository(destination).status()

    assert status["counts"]["administrator_organizations"] == 1
    assert status["counts"]["administrator_aliases"] == 1


def test_materializer_attaches_later_key_node_to_active_manager(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "administrators.sqlite3"
    appointment = _row(
        announcement_id="APPOINT",
        announcement_date="2024-07-01",
        statement=(
            "2024年7月1日，法院作出（2024）赣01破申19号决定书，"
            "指定北京市金杜（深圳）律师事务所担任公司预重整临时管理人。"
        ),
    )
    with sqlite3.connect(source) as connection:
        connection.execute(
            "create table company_announcements ("
            "announcement_id text,symbol text,announcement_date text,published_at text,"
            "title text,url text,body_text text,source text)"
        )
        connection.execute(
            "insert into company_announcements values (?,?,?,?,?,?,?,?)",
            (
                appointment.announcement_id,
                appointment.symbol,
                appointment.announcement_date.isoformat(),
                "",
                appointment.title,
                appointment.url,
                appointment.body_text,
                appointment.source,
            ),
        )
        connection.execute(
            "insert into company_announcements values (?,?,?,?,?,?,?,?)",
            (
                "RECRUIT",
                appointment.symbol,
                "2024-08-01",
                "",
                "关于公开招募和遴选重整投资人的公告",
                "https://example.test/RECRUIT",
                "",
                "cninfo",
            ),
        )

    materialize_administrator_facts(
        source_database=source,
        database=destination,
    )
    repository = AdministratorRepository(destination)
    assignments = repository.assignments_for_symbol("603398")
    assert len(assignments) == 1
    organization_id = assignments[0]["organization_id"]
    event_types = {
        row["event_type"]
        for row in repository.events_for_organization(organization_id)
    }

    assert "administrator_appointed" in event_types
    assert "investor_recruitment_started" in event_types
