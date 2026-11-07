from copy import deepcopy

import pytest

from research_history import assemble,deduplicate,mentioned,question_day,question_digest,question_order
from research_history_captures import collect_outputs,import_capture_files,merge_records
from research_history_reviews import freeze_review
from test_research_history import sample
from test_research_history_captures import capture,log_capture,Q2


def ranged_original(tmp_path,*,lower='2026-06-01T14:00:00Z',upper='2026-06-04T10:00:00Z'):
    packet=capture();packet['title']='宝馨原聊天';row=packet['turns'][1]
    row.update(date_marker=None,date_marker_owner=None,has_own_time=False,
               date_bounds={'not_before':lower,'not_after':upper},answers=[{'text':'原回答：更像洗盘。'}])
    collect_outputs(log_capture(tmp_path,packet),tmp_path/'captures')
    rows,_=import_capture_files(tmp_path/'captures',{'002514.SZ':'*ST宝馨'})
    return next(r for r in rows if r['id']=='QUESTION-'+Q2)


def test_cross_day_bounds_preserve_the_original_without_selecting_a_profitable_anchor(tmp_path):
    row=ranged_original(tmp_path);paths,_=sample()
    assert question_day(row) is None and row['asked_on'] is None and row['asked_at'] is None
    assert row['time_precision']=='range' and (row['asked_from'],row['asked_through'])==('2026-06-01','2026-06-04')
    result=assemble([row],paths)['details']['002514.SZ']['questions'][0]
    assert result['anchor_date'] is None and result['outcomes']=={}
    assert result['anchor_basis']=='unresolved_question_day'
    assert '未指定某一天' in result['basis_note']


def test_shanghai_midnight_matters_even_when_two_bounds_share_the_same_utc_day(tmp_path):
    row=ranged_original(tmp_path,lower='2026-06-01T15:50:00Z',upper='2026-06-01T16:10:00Z')
    assert row['time_precision']=='range'
    assert (row['asked_from'],row['asked_through'])==('2026-06-01','2026-06-02')


def test_same_shanghai_day_bounds_support_a_date_but_never_supply_a_clock(tmp_path):
    row=ranged_original(tmp_path,lower='2026-06-01T02:00:00Z',upper='2026-06-01T10:00:00Z')
    assert row['asked_at'] is None and question_day(row)=='2026-06-01' and row['time_precision']=='day'
    assert question_order(row)[0].isoformat()=='2026-06-01T02:00:00+00:00'


@pytest.mark.parametrize('lower,upper',[('2026-06-04T10:00:00Z','2026-06-01T10:00:00Z'),('2099-01-01T00:00:00Z','2099-01-02T00:00:00Z')])
def test_reversed_or_future_bounds_are_not_imported(tmp_path,lower,upper):
    with pytest.raises(ValueError):ranged_original(tmp_path,lower=lower,upper=upper)


def test_identical_words_inside_uncertain_ranges_do_not_merge_separate_questions(tmp_path):
    row=ranged_original(tmp_path);other=deepcopy(row);other['id']='another-original-message'
    assert len(deduplicate([row,other]))==2


def test_corrected_date_precision_withdraws_a_review_instead_of_reusing_its_returns(tmp_path):
    row=ranged_original(tmp_path);paths,_=sample();dated=deepcopy(row)
    dated.update(asked_at=None,asked_on='2026-06-02',time_precision='day',source_date_marker='2026-06-02T00:00:00Z')
    review=freeze_review({'question_digest':question_digest(dated),'then_quote':row['answers'][0]['text'],'headline':'旧日期评估'},dated,paths,'2026-06-02')
    result=assemble([row],paths,reviews={row['id']:review})['details']['002514.SZ']['questions'][0]
    assert result['review'] is None and result['previous_review']==review and result['review_status']=='original_changed'
    changed=deepcopy(row);changed['asked_through']='2026-06-05'
    assert question_digest(changed)!=question_digest(row)


@pytest.mark.parametrize('exact',[False,True])
def test_new_independent_date_or_clock_can_resolve_a_previously_bounded_question(tmp_path,exact):
    row=ranged_original(tmp_path);resolved=deepcopy(row)
    resolved.update(asked_at='2026-06-02T10:00:00Z' if exact else None,asked_on='2026-06-02',
                    time_precision='instant' if exact else 'day',date_source='new_independent_original',
                    source_date_marker='2026-06-02T10:00:00Z',source_date_owner_id=Q2,source_group_offset=0)
    result=merge_records([row],[resolved])[0]
    assert question_day(result)=='2026-06-02' and result['time_precision']==('instant' if exact else 'day')
    assert result['source_date_marker']=='2026-06-02T10:00:00Z'
    assert 'asked_from' not in result and 'asked_through' not in result


def test_late_attachment_controls_enrich_availability_without_overwriting_answers():
    _,row=sample();row['unavailable_attachments']=0;later=deepcopy(row);later['unavailable_attachments']=6
    later['answers']=[{'text':'不是用来覆盖旧答的另一份渲染'}]
    result=merge_records([row],[later])[0]
    assert result['unavailable_attachments']==6 and result['answers']==row['answers']
    replay=deepcopy(later);replay['unavailable_attachments']=0
    assert merge_records([result],[replay])[0]['unavailable_attachments']==6


def test_replaying_a_clock_does_not_undo_a_canonical_day_only_correction():
    _,row=sample();exact=deepcopy(row)
    row.update(asked_at=None,asked_on='2026-06-02',time_precision='day',source_date_owner_id=None)
    assert merge_records([row],[exact])[0]['asked_at'] is None


def test_date_outside_original_bounds_requires_explicit_reconciliation(tmp_path):
    row=ranged_original(tmp_path);resolved=deepcopy(row)
    resolved.update(asked_at='2026-06-05T10:00:00Z',asked_on='2026-06-05',time_precision='instant')
    with pytest.raises(ValueError,match='conflicts'):merge_records([row],[resolved])


def test_range_and_exact_clock_cannot_be_claimed_at_the_same_time(tmp_path):
    row=ranged_original(tmp_path);row['asked_at']='2026-06-02T10:00:00Z'
    with pytest.raises(ValueError,match='exact question time'):question_day(row)


def test_zhengping_is_not_zhengbang_or_an_automatically_tracked_holding():
    known={'603843.SH':'*ST正平','002157.SZ':'正邦科技'}
    assert mentioned('正平的债务与沐邦相比呢？',known)==['603843.SH']
    assert mentioned('正邦的重整',known)==['002157.SZ']
