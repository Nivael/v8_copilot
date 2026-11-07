from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from urllib.parse import urlencode

import pytest

from canonical_json import digest
from data_refresh import atomic_write_json
from market_calendar import sessions_2026
import research_history_subjects as subject


def dividend():
    return ['2026-06-11','64.090','67.020','68.180','63.340','1190760.000',
            {'nd':'2025','fh_sh':'4','djr':'2026-06-10','cqr':'2026-06-11','FHcontent':'10派4元'}]


def test_cash_event_metadata_is_kept_separate_from_unchanged_price_columns():
    row=dividend();before=deepcopy(row)
    assert subject.cash_dividend(row)==row[6]
    assert subject.cash_dividend(row[:6]) is None and row==before


@pytest.mark.parametrize('change',['unknown_field','stock_split','cash_mismatch','event_day','registration_day','year_type','negative_cash','extra_column'])
def test_unrecognized_or_mismatched_corporate_action_cannot_be_silently_discarded(change):
    row=dividend();meta=row[6]
    if change=='unknown_field':meta['unknown']='4'
    elif change=='stock_split':meta['FHcontent']='10转4股'
    elif change=='cash_mismatch':meta['fh_sh']='4.2'
    elif change=='event_day':meta['cqr']='2026-06-12'
    elif change=='registration_day':meta['djr']='2026-06-11'
    elif change=='year_type':meta['nd']=2025
    elif change=='negative_cash':meta['fh_sh']='-4'
    else:row.append('extra')
    with pytest.raises(ValueError):subject.cash_dividend(row)


def materialization(root, change=None):
    calendar=sessions_2026(date(2026,9,3),date(2026,10,16))
    rows=[[day,f'{10+i/10:.3f}',f'{10+i/10:.3f}',f'{11+i/10:.3f}',f'{9+i/10:.3f}','100.000'] for i,day in enumerate(calendar)]
    day=calendar[4]
    rows[4].append({'nd':'2025','fh_sh':'4','djr':calendar[3],'cqr':day,'FHcontent':'10派4元'})
    value={'code':0,'data':{'sh600549':{'qt':{'sh600549':['','Sample','600549']},'qfqday':rows}}}
    official={r[0]:{'close':float(r[2]),'previous_close':float(rows[i-1][2]) if i else 10,'is_trading':True} for i,r in enumerate(rows)}
    if change=='identity':value['data']['sh600549']['qt']['sh600549'][2]='600702'
    elif change=='source_number':rows[-1][2]='100.000';rows[-1][3]='101.000'
    elif change=='missing_handoff':rows.pop(0)
    elif change=='duplicate_date':rows[3][0]=rows[2][0]
    elif change=='price_type':rows[2][2]=10.2
    elif change=='invalid_price':rows[2][4]='999.000'
    elif change=='official_return':official[calendar[10]]['previous_close']=1
    elif change=='too_few_checks':official={k:v for k,v in official.items() if k in calendar[-5:]}
    url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'sh600549,day,{calendar[0]},{calendar[-1]},640,qfq'})
    raw=json.dumps(value).encode();key=sha256(raw).hexdigest();folder=root/'inputs/subject_qfq_v1';folder.mkdir(parents=True);(folder/(key+'.json')).write_bytes(raw)
    ref={'version':subject.SOURCE_VERSION,'url':url,'response_url':url,'sha256':key,'bytes':len(raw),
         'through':calendar[-1],'observed_at':datetime.now(timezone.utc).isoformat(),'historical_basis_replaced':True,'basis_review_note':'Reviewed full replacement.'}
    if change=='source_url':ref['url']=url+'&other=1'
    if change=='unreviewed':ref['historical_basis_replaced']=False
    if change=='wrong_bytes':ref['sha256']='0'*64;(folder/(ref['sha256']+'.json')).write_bytes(raw)
    ref['content_digest']=digest(ref);atomic_write_json(folder/'600549.json',ref)
    return calendar,official,raw,folder/(key+'.json')


def test_complete_new_subject_is_reconciled_with_official_returns_and_original_bytes(tmp_path):
    calendar,official,raw,path=materialization(tmp_path)
    result,ref,proof=subject.supplemental_subject_history(tmp_path,'600549.SH',calendar,{},official)
    assert len(proof['cash_events'])==1 and proof['official_return_checks']>=20
    assert result[calendar[0]]=={'close':10.0,'volume':100.0}
    assert path.read_bytes()==raw and ref['sha256']==sha256(raw).hexdigest()


@pytest.mark.parametrize('change',['identity','source_number','missing_handoff','duplicate_date','price_type','invalid_price','official_return','too_few_checks','source_url','unreviewed','wrong_bytes'])
def test_new_subject_rejects_identity_timing_price_source_or_verification_changes(tmp_path,change):
    calendar,official,_,_=materialization(tmp_path,change)
    with pytest.raises(ValueError):subject.supplemental_subject_history(tmp_path,'600549.SH',calendar,{},official)


def base_packet():
    data={'calendar':['2026-05-06'],'stocks':{'603398.SH':{'name':'Original','as_of':'2026-05-06','points':[{'date':'2026-05-06','value':1.,'level':100.,'basis':'historical_qfq'}]}},
          'market':[{'date':'2026-05-06','value':1.}],'st':[{'date':'2026-05-06','value':1.}],'source_digests':{'old':'a'*64}}
    base={'version':'research_history_paths_v1','processor_digest':'b'*64,'data':data};base['content_digest']=digest(base)
    added=deepcopy(data);added['stocks']['600549.SH']={'name':'Added','as_of':'2026-05-06','points':[{'date':'2026-05-06','value':2.,'level':100.,'basis':'historical_qfq'}]};added['source_digests']['new']='c'*64
    return base,added


def test_extension_preserves_old_paths_and_benchmarks_and_can_be_verified_from_retained_base(tmp_path):
    base,data=base_packet();old=deepcopy(base);packet=subject.extension_packet(base,data)
    atomic_write_json(tmp_path/'price_paths/history'/(base['content_digest']+'.json'),base)
    subject.validate_extension(packet,root=tmp_path)
    assert base==old and packet['data']['stocks']['603398.SH']==base['data']['stocks']['603398.SH']
    assert packet['subject_extension']['added_symbols']==['600549.SH']


@pytest.mark.parametrize('change',['old_path','market','legacy_source','calendar','new_path','unavailable_value','wrong_venue','code','missing_base'])
def test_extension_rejects_altered_old_data_unbound_new_paths_or_missing_base(tmp_path,monkeypatch,change):
    base,data=base_packet();packet=subject.extension_packet(base,data)
    if change!='missing_base':atomic_write_json(tmp_path/'price_paths/history'/(base['content_digest']+'.json'),base)
    if change=='old_path':packet['data']['stocks']['603398.SH']['points'][0]['value']=3
    elif change=='market':packet['data']['market'][0]['value']=3
    elif change=='legacy_source':packet['data']['source_digests']['old']='d'*64
    elif change=='calendar':packet['data']['calendar'].append('2026-05-07')
    elif change=='new_path':packet['data']['stocks']['600549.SH']['points'][0]['value']=9
    elif change=='unavailable_value':packet['data']['stocks']['600549.SH']['points'][0]['value']=None
    elif change=='wrong_venue':packet['subject_extension']['added_symbols']=['600549.SZ']
    elif change=='code':monkeypatch.setattr(subject,'processor_digest',lambda:'d'*64)
    with pytest.raises((ValueError,FileNotFoundError)):subject.validate_extension(packet,root=tmp_path)


def test_old_unextended_price_packet_remains_compatible():
    subject.validate_extension(base_packet()[0])


def test_later_subject_extensions_retain_and_validate_the_entire_base_chain(tmp_path):
    base,data=base_packet()
    atomic_write_json(tmp_path/'price_paths/history'/(base['content_digest']+'.json'),base)
    first=subject.extension_packet(base,data,root=tmp_path)
    atomic_write_json(tmp_path/'price_paths/history'/(first['content_digest']+'.json'),first)
    added=deepcopy(first['data']);added['stocks']['600702.SH']=deepcopy(added['stocks']['600549.SH'])
    added['source_digests']['next']='d'*64
    second=subject.extension_packet(first,added,root=tmp_path)
    subject.validate_extension(second,root=tmp_path)
    assert second['data']['stocks']['603398.SH']==base['data']['stocks']['603398.SH']
    assert second['subject_extension']['added_symbols']==['600702.SH']


@pytest.mark.parametrize('change',['code','old_path'])
def test_publisher_rejects_stale_extension_before_writing_history_or_import(tmp_path,monkeypatch,change):
    from pathlib import Path
    import research_history_prices
    from research_history import publish
    base,data=base_packet()
    base['processor_digest']=sha256(Path(research_history_prices.__file__).read_bytes()).hexdigest()
    base['content_digest']=digest({k:v for k,v in base.items() if k!='content_digest'})
    atomic_write_json(tmp_path/'price_paths/history'/(base['content_digest']+'.json'),base)
    packet=subject.extension_packet(base,data)
    if change=='code':monkeypatch.setattr(subject,'processor_digest',lambda:'d'*64)
    else:packet['data']['stocks']['603398.SH']['points'][0]['value']=99
    packet['content_digest']=digest({k:v for k,v in packet.items() if k!='content_digest'})
    atomic_write_json(tmp_path/'price_paths/current.json',packet)
    with pytest.raises(ValueError,match='historical-price extension'):
        publish({'records':[],'sources':[]},root=tmp_path)
    assert not (tmp_path/'current.json').exists() and not (tmp_path/'imports').exists()
