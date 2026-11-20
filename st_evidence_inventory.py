"""Count retained source identities, not reading completion or independent experiments."""
from hashlib import sha256
from collections import defaultdict
import re,unicodedata
from canonical_json import digest
from copy import deepcopy

def audit_source_inputs(inputs,source_snapshot):
    docs={};references=0;malformed=0
    norm=lambda t:re.sub(r'\s+','',unicodedata.normalize('NFKC',t))
    def walk(o,path):
     nonlocal references,malformed
     if isinstance(o,dict):
      if o.get('announcement_id')and o.get('sha256'):
       aid=str(o['announcement_id']);h=str(o['sha256']);references+=1
       if not re.fullmatch('[a-f0-9]{64}',h):malformed+=1
       else:
        d=docs.setdefault((aid,h),{'announcement_id':aid,'sha256':h,'symbols':set(),'urls':set(),'titles':set(),'published_dates':set(),'reference_paths':set(),'page_counts':set(),'page_variants':defaultdict(set),'body_hashes':set(),'gate_values':set(),'source_metadata_records':0})
        if o.get('symbol'):d['symbols'].add(str(o['symbol']))
        if o.get('url'):d['urls'].add(o['url'])
        if o.get('title'):d['titles'].add(o['title'])
        date=o.get('published_on',o.get('announcement_date'))
        if date:d['published_dates'].add(str(date))
        d['reference_paths'].add(path)
        if isinstance(o.get('pages'),int):d['page_counts'].add(o['pages'])
        if 'protected_gate_passed'in o:d['gate_values'].add(o['protected_gate_passed'])
        if 'observed_at'in o:d['source_metadata_records']+=1
        pages=o.get('selected_pages',o.get('texts',o.get('page_texts')))
        if isinstance(pages,list):pages={str(n+1):t for n,t in enumerate(pages)}
        if isinstance(pages,dict):
         for n,t in pages.items():
          if isinstance(t,str)and t.strip():d['page_variants'][str(n)].add(sha256(norm(t).encode()).hexdigest())
        if isinstance(o.get('body_text'),str)and o['body_text'].strip():d['body_hashes'].add(sha256(norm(o['body_text']).encode()).hexdigest())
      for key,value in o.items():
       if isinstance(value,(dict,list)):walk(value,path+'.'+key)
     elif isinstance(o,list):
      for n,value in enumerate(o):
       if isinstance(value,(dict,list)):walk(value,path+'['+str(n)+']')
    walk(inputs,'inputs')
    rows=[]
    for d in docs.values():
     row={k:sorted(v)if isinstance(v,set)else v for k,v in d.items()if k!='page_variants'};row['page_variants']={k:sorted(v)for k,v in d['page_variants'].items()};row['has_retained_extracted_text']=bool(row['page_variants']or row['body_hashes']);row['retained_nonempty_page_positions']=len(row['page_variants']);row['all_declared_page_positions_nonempty']=len(row['page_counts'])==1 and set(row['page_variants'])=={str(n)for n in range(1,row['page_counts'][0]+1)};rows.append(row)
    rows.sort(key=lambda r:(r['announcement_id'],r['sha256']));ids=defaultdict(set)
    for row in rows:ids[row['announcement_id']].add(row['sha256'])
    body=[r for r in rows if r['has_retained_extracted_text']];metadata=[r for r in rows if not r['has_retained_extracted_text']];multi=[{'announcement_id':a,'sha256_values':sorted(h)}for a,h in ids.items()if len(h)>1];page_conflicts=[{'announcement_id':r['announcement_id'],'sha256':r['sha256'],'pages':[n for n,v in r['page_variants'].items()if len(v)>1]}for r in rows if any(len(v)>1 for v in r['page_variants'].values())]
    counts={'embedded_reference_records':references,'unique_announcement_ids':len(ids),'unique_id_sha_pairs':len(rows),'with_retained_extracted_text':len(body),'metadata_or_reference_only':len(metadata),'retained_nonempty_page_positions':sum(r['retained_nonempty_page_positions']for r in body),'text_carrying_company_symbols':len({s for r in body for s in r['symbols']}),'ids_with_multiple_sha':len(multi),'documents_with_multiple_normalized_page_variants':len(page_conflicts),'with_all_declared_page_positions_nonempty':sum(r['all_declared_page_positions_nonempty']for r in rows),'multiple_declared_page_counts':sum(len(r['page_counts'])>1 for r in rows),'malformed_sha_references':malformed,'explicit_gate_false_pairs':sum(False in r['gate_values']for r in rows),'not_full_read_certifications':True}
    result={'snapshot_digest':source_snapshot,'input_digest':digest(inputs),'scope':'当前正式快照对应的版本化输入内嵌材料；不遍历全部硬盘或归档，不认证全部可用知识库。','counts':counts,'documents':rows,'multiple_file_identities':multi,'page_text_variants':page_conflicts,'boundary':'同一公告ID与同一文件摘要只计一次；含提取文本不等于全文齐全或视觉审阅完成，非空页位置数不是已读页数。多文件摘要或提取差异需要逐项核对，不自动判定为实质冲突。网页政策无公告ID不纳入此公告统计；行情响应和目录行也不冒充公告正文。'}
    return result

def evidence_inventory(inputs):
    packet=inputs.get('evidence_inventory')
    if packet is None:return None
    if packet.get('version')!=1 or packet.get('content_digest')!=digest({k:v for k,v in packet.items()if k!='content_digest'}):raise ValueError('inventory packet changed')
    if any(k not in inputs for k in BASELINE_KEYS):raise ValueError('inventory baseline missing')
    baseline={k:inputs[k] for k in BASELINE_KEYS}
    if digest(baseline)!=BASELINE_DIGEST:raise ValueError('inventory baseline changed')
    calculated=audit_source_inputs(baseline,SOURCE_SNAPSHOT)
    if digest(calculated)!=INVENTORY_DIGEST or calculated!=packet['calculation']or digest(packet['result'])!=VIEW_DIGEST:raise ValueError('inventory evidence changed')
    return deepcopy(packet['result'])

BASELINE_DIGEST='6df253f167598adcb036b3db4c653560537c7e20438ad1ac71b9a6578a648007'
SOURCE_SNAPSHOT='990cfef0a059266494d4b410214957bb1568476676182dbe73c18745a996b673'
INVENTORY_DIGEST='3d2b908a9a57f6711b06dabf76f17e08f16ccc861215e48b996e90843720e2de'
VIEW_DIGEST='05a68ad570e2a48ca5a0019d6ee02aaba143b0d62904c0c56ad746208448cea5'

# Freeze the original accounting scope; later independent packets are not counted.
BASELINE_KEYS=('activities', 'activity_snapshots', 'announcement_study', 'benchmarks', 'calendar', 'case_price_crosscheck', 'dividend_basis', 'fixed_prices', 'fixed_quote_audit', 'gaoke_risk_case', 'halt_price_crosscheck', 'halt_stages', 'index_crosscheck', 'jinglan_followup', 'juewei_adjustment', 'label_changes', 'member_entries', 'member_transitions', 'members', 'official_membership_audit', 'refresh_provenance', 'removal_cohort', 'sample_integrity', 'shenwu_execution', 'source_tables', 'stock_price_crosscheck', 'strong_removal_cases', 'through', 'tianji_conditions', 'version', 'remaining_basis', 'exit_quote_replay', 'dynamic_reference_audit', 'pre_rule_membership', 'removal_era_comparison', 'removal_action_basis', 'price_band_audit', 'experience_case_audit', 'disclosure_chains', 'baoxin_auction_links', 'baoxin_holding_bridge', 'announcement_reading', 'official_pdf_audit', 'huke_date_proof', 'initial_status_coverage', 'warning_basis_followup', 'ruihe_process', 'initial_three_followup', 'initial_three_quoteproof', 'zhongyan_debt_followup', 'initial_day_corroboration', 'initial_warning_origin', 'penalty_clock', 'current_extension', 'weiling_stage_check', 'initial_four', 'xilv_timeline', 'xilv_liability', 'initial_next_four', 'endpoint_reasons', 'initial_third_four', 'yigou_settlement', 'initial_fourth_four', 'initial_fifth_four', 'dongjing_dali_followup', 'initial_sixth_four', 'helitai_yunwang_followup', 'initial_seventh_four', 'seventh_period_followup', 'initial_eighth_four', 'eighth_period_followup', 'initial_ninth_four', 'ninth_period_followup', 'initial_tenth_four', 'tenth_period_followup', 'initial_eleventh_four', 'eleventh_period_followup', 'initial_twelfth_four', 'initial_twelfth_correction', 'twelfth_period_followup', 'initial_thirteenth_four', 'thirteenth_period_followup', 'initial_fourteenth_four', 'fourteenth_period_followup', 'initial_fifteenth_four', 'fifteenth_period_followup', 'initial_sixteenth_four', 'sixteenth_period_followup', 'initial_seventeenth_four', 'seventeenth_period_followup', 'initial_eighteenth_four', 'eighteenth_period_followup', 'initial_nineteenth_four', 'nineteenth_period_followup', 'initial_twentieth_four', 'twentieth_period_followup', 'initial_twentyfirst_four', 'twentyfirst_period_followup', 'initial_twentysecond_four', 'twentysecond_period_followup', 'initial_twentythird_four', 'twentythird_period_followup', 'initial_twentyfourth_four', 'twentyfourth_period_followup', 'initial_twentyfifth_four', 'twentyfifth_period_followup', 'initial_twentysixth_four', 'twentysixth_period_followup', 'initial_twentyseventh_four', 'twentyseventh_period_followup', 'endpoint_selection_audit', 'endpoint_basis_followup', 'lingnan_exit_followup', 'restatement_comparison', 'baili_policy_followup', 'jihua_bridge_followup', 'market_stage_experience', 'exit_outcomes', 'ningke_comparative_followup', 'jingji_dividend_followup')
