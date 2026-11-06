from dataclasses import replace

import pytest

from announcement_body import AnnouncementBody
from announcement_inventory import AnnouncementInventory, OfficialAnnouncement
from api_contract import ResearchObject, ResearchRequest
from evidence_gateway import build_evidence_pack
from answer_engine import AnswerCard, FIXED_CAVEATS
from lens_binding import LensGap
from recruitment_precedent import RecruitmentDeadlineCase
from snapshot_metadata import PriceSnapshot


@pytest.fixture
def sources(monkeypatch):
    def record(identity, day):
        return OfficialAnnouncement(identity, day, '关于预重整进展的公告',
                                    'https://example.invalid/'+identity+'.pdf', 'synthetic_test', True)
    rows = (record('latest', '2026-09-08'), record('target', '2026-07-09'),
            record('old-year', '2024-07-09'))
    inventory = AnnouncementInventory(rows, '2026-09-08', '2026-09-08', None, 0)
    monkeypatch.setattr('answer_engine.load_announcement_inventory', lambda **_: inventory)
    def status(symbol):
        return AnswerCard(question='测试状态', object_ref='stock:'+symbol, view='query',
            as_of='2026-06-01', data_snapshot_as_of='2026-06-01', sample_scope='合成测试',
            evidence_grade='descriptive_query', source_freshness={'st_status_fetched_at':'2026-06-01'},
            body_rows=[{'row_id':'status', '记录类型':'状态区间', '状态':'ST', '开始日':'2026-06-01', '结束日':None}],
            lens_gap=[LensGap(gap_id='synthetic_coverage', missing_for='测试边界', sediment_as='question_card:synthetic')],
            caveats=list(FIXED_CAVEATS), provenance=['synthetic:test'])
    monkeypatch.setattr('answer_engine.card_st_status_timeline', status)
    calls = []
    def body(record, **kwargs):
        assert kwargs['allow_network'] is False
        calls.append(record.announcement_id)
        return AnnouncementBody(announcement_id=record.announcement_id, announcement_date=record.announcement_date,
            source_url=record.url, page_count=1, text='该主体仍在预重整阶段，尚未确认正式受理。', source='synthetic_test')
    monkeypatch.setattr('answer_engine.load_announcement_body', body)
    return inventory, calls


def ask(text):
    return build_evidence_pack(ResearchRequest(question=text,
        object=ResearchObject(kind='stock', ref='603398'), llm_mode='off'))


def summary(pack):
    return next(row for row in pack.rows if row.get('记录类型')=='题面公告检索')


@pytest.mark.parametrize('date_text', ['7月9日', '7月9号', '７ 月 ９ 日'])
def test_yearless_dates_do_not_identify_an_announcement_or_borrow_its_year(sources, date_text):
    _, calls = sources
    pack = ask('沐邦'+date_text+'预重整公告说了什么？')
    assert not calls
    assert not any(row.get('记录类型')=='公告正文证据' for row in pack.rows)
    assert summary(pack)['日期确认']=='缺少年份'
    assert {item['日期'] for item in summary(pack)['待确认候选']}=={'2024-07-09','2026-07-09'}
    assert any(gap.get('gap_id')=='announcement_date_unresolved' for gap in pack.coverage_gaps)
    direct=pack.deterministic_response['narrative']['direct_answer']['text']
    assert '年份' in direct and '尚未确认正式受理' not in direct


def test_one_old_candidate_does_not_resolve_a_missing_year(sources, monkeypatch):
    inventory, calls=sources
    monkeypatch.setattr('answer_engine.load_announcement_inventory', lambda **_: replace(inventory, records=(inventory.records[-1],)))
    pack=ask('沐邦今天7月9日预重整公告说了什么？')
    assert not calls and summary(pack)['日期确认']=='缺少年份'
    assert pack.question_scope['as_of']!='2024-07-09'


@pytest.mark.parametrize('date_text',['2026年7月9日','2026-07-09','2026/7/9','2026.7.9','２０２６年７月９号'])
def test_full_calendar_dates_select_exact_year_and_do_not_append_latest_announcements(sources,date_text):
    _, calls=sources
    pack=ask('沐邦'+date_text+'预重整公告说了什么？')
    assert calls==['target']
    official=[r for r in pack.rows if r.get('记录类型')=='近期官方公告']
    assert [r['巨潮公告ID'] for r in official]==['target']
    assert summary(pack)['检索日期']=='2026-07-09'
    assert summary(pack)['日期确认']=='完整日期'


@pytest.mark.parametrize('date_text',['2026年2月30日','2026-13-01','2026/02/29','7月32日'])
def test_invalid_dates_never_fall_back_to_latest_body(sources,date_text):
    _, calls=sources
    pack=ask('沐邦最新公告'+date_text+'说了什么？')
    assert not calls
    assert summary(pack)['日期确认']=='日期无效'
    assert '日期' in pack.deterministic_response['narrative']['direct_answer']['text']


def test_unmatched_full_date_does_not_explain_a_different_announcement(sources):
    _, calls=sources
    pack=ask('沐邦2026年7月10日公告内容是什么？')
    assert not calls and summary(pack)['标题与日期命中数']==0
    assert not any(r.get('记录类型')=='近期官方公告' for r in pack.rows)


def test_mixed_full_and_partial_dates_do_not_silently_drop_the_partial_date(sources):
    _, calls=sources
    pack=ask('沐邦2026年7月9日和7月20日公告说了什么？')
    assert not calls and summary(pack)['日期确认']=='缺少年份'
    assert '7月20日' in summary(pack)['检索日期']


def test_several_dated_announcements_require_identity_before_reading_one_as_the_answer(sources,monkeypatch):
    inventory, calls=sources
    extra=replace(inventory.records[1],announcement_id='another-target')
    monkeypatch.setattr('answer_engine.load_announcement_inventory',lambda **_:replace(inventory,records=(*inventory.records,extra)))
    pack=ask('沐邦2026年7月9日公告说了什么？')
    assert not calls and summary(pack)['标题与日期命中数']==2
    assert summary(pack)['待确认事项']
    assert '多份' in pack.deterministic_response['narrative']['direct_answer']['text']


def test_a_historical_search_date_cannot_relabel_current_status_as_historically_known(sources):
    pack=ask('沐邦2024年7月9日预重整公告说了什么？')
    assert summary(pack)['检索日期']=='2024-07-09'
    assert pack.question_scope['as_of']>='2026-06-01'
    assert any('不构成' in text and '当时' in text for text in pack.definitions)
    assert '2024-07-09' in pack.deterministic_response['narrative']['direct_answer']['text']


def test_latest_included_status_still_controls_when_the_entire_announcement_inventory_is_old(sources,monkeypatch):
    inventory,_=sources
    old=replace(inventory,records=(inventory.records[-1],),base_as_of='2024-07-09',announcement_as_of='2024-07-09')
    monkeypatch.setattr('answer_engine.load_announcement_inventory',lambda **_:old)
    pack=ask('沐邦2024年7月9日预重整公告说了什么？')
    assert pack.question_scope['as_of']>='2026-06-01'


def test_rechecking_an_inventory_is_not_a_new_information_date(sources,monkeypatch):
    inventory,_=sources
    monkeypatch.setattr('answer_engine.load_announcement_inventory',lambda **_:replace(inventory,refresh_checked_at='2035-01-01'))
    pack=ask('沐邦2024年7月9日预重整公告说了什么？')
    assert pack.question_scope['as_of']=='2026-09-08'


def test_latest_without_a_date_keeps_the_existing_latest_body_flow(sources):
    _, calls=sources
    ask('沐邦最新公告说了什么？')
    assert calls==['latest']


@pytest.fixture
def recruitment_sources(monkeypatch):
    prices=PriceSnapshot('daily_prices','2026-07-01','2026-07-20',20,1,19)
    monkeypatch.setattr('answer_engine.load_price_snapshot',lambda *_,**__:prices)
    cases=[RecruitmentDeadlineCase('window','603398','2026-07-08','公开招募','2026-07-15','https://example.invalid/window'),
           RecruitmentDeadlineCase('other-stock','000001','2026-07-01','公开招募','2026-07-20','https://example.invalid/other'),
           RecruitmentDeadlineCase('grandchild','603398','2026-07-01','孙公司招募','2026-07-20','https://example.invalid/grandchild',subject_scope='grandchild')]
    monkeypatch.setattr('answer_engine.load_recruitment_deadlines',lambda _: (cases,{}))
    counts={'listed_company_cases':2,'st_eligible_cases':1,'price_covered_cases':1,'precedent_cases':0,'future_deadline_cases':0,'incomplete_price_cases':0}
    monkeypatch.setattr('answer_engine.analyze_recruitment_precedents',lambda *_,**__: ([],counts))


def precedent(text):
    pack=ask('沐邦'+text+'跌停，有在公开招募截止前连续跌停的先例吗？')
    row=next(r for r in pack.rows if r.get('记录类型')=='题面当日价格前提')
    summary_row=next(r for r in pack.rows if r.get('记录类型')=='招募截止前连续跌停先例汇总')
    assert summary_row['截止日与价格完整覆盖']==1
    return pack,row


@pytest.mark.parametrize('text',['今天7月9号','2026年2月30日','2025年7月9日和2026年7月9日'])
def test_precedent_query_does_not_invent_the_year_or_which_day_is_today(recruitment_sources,text):
    pack,row=precedent(text)
    assert row['题面日期'] is None and row['本地是否覆盖'] is None
    assert row['本地是否验证处于招募截止前']=='未验证'
    assert any(gap.get('gap_id')=='question_price_date_unresolved' for gap in pack.coverage_gaps)


def test_known_day_only_matches_a_recruitment_window_that_has_already_started(recruitment_sources):
    _,before=precedent('2026年7月7日')
    _,during=precedent('2026年7月9日')
    _,after=precedent('2026年7月16日')
    assert before['本地是否验证处于招募截止前']=='未验证'
    assert during['本地是否验证处于招募截止前'] is True
    assert [w['巨潮公告ID'] for w in during['匹配招募窗口']]==['window']
    assert after['本地是否验证处于招募截止前']=='未验证'


def test_a_date_before_the_price_snapshot_is_not_covered_or_described_as_too_late(recruitment_sources):
    pack,row=precedent('2026年6月29日')
    assert row['本地是否覆盖'] is False
    uncertainties=' '.join(v['text'] for v in pack.deterministic_response['narrative']['uncertainties'])
    assert '晚于' not in uncertainties and '未覆盖' in uncertainties
