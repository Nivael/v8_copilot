"""Reconcile explicitly reviewed announcement chains; never certify an entire flow window."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from canonical_json import digest
from etf_document_capture import valid_ready
from etf_quarterly import compact, decimal_text
from etf_share_event_profiles import EXTRA_CASES, parse_profile

VERSION = "etf_share_event_review_v2"


def parser_digest():
    root=Path(__file__).parent
    return digest({name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in (Path(__file__).name,'etf_share_event_profiles.py','etf_quarterly.py')})


PARSER_DIGEST = parser_digest()
# Explicitly reviewed source chains, not title-based discovery or a claim that no
# other event exists. New candidates require another evidence-backed review.
CASES = [
    {"id":"510310-merge-20240920", "code":"510310.SH", "kind":"merge", "resolution":"implemented", "documents":[
        ("6877e912406d77933f3f2c5a9b4ef73306db2b9e5783ce3ce589712b8986dc9f","plan"),
        ("4666b21f039f6b8d674cd695e912d55749dd5795cffc3c2578b117e14e485601","result")]},
    {"id":"512100-split-20220803-cancelled", "code":"512100.SH", "kind":"split", "resolution":"cancelled", "documents":[
        ("f76e55336c2f794979f2ab08561de2d30d3a1804172b8cea1e5bd75410ccc2b3","plan"),
        ("653e72e6343b1ac6408c3d4d11dd79df1bce5eb86cce8432487363c0178097ab","reminder"),
        ("320bf1d16e70ca8686125faec123647b8bdeb8895b4f1858fe413a5ca445192a","cancellation")]},
    {"id":"512100-merge-20220902", "code":"512100.SH", "kind":"merge", "resolution":"implemented", "documents":[
        ("a199a23e493bf4e17310ffdaf11301bc9950b5438962912cdd85770e488f2409","plan"),
        ("fbe97e5ce3a3a3b182169b32483322e0a2cc2dc1e8162f64c381de1a7abf23a3","reminder"),
        ("cd77380ee7f669ff6716c158f9641a28958623203798eaf64d340aa787384edf","reminder"),
        ("4137f575124ed8fe50ec5c4c77bb3980f5ceb1ed13b742252d62bfd1238b98c4","result")]},
    {"id":"512100-creation-unit-20240221", "code":"512100.SH", "kind":"creation_unit", "resolution":"announced_effective", "documents":[
        ("f86bac85a324499603fb2c577e86fd088ffd5466c3245d94163bd7d5ae942454","unit_notice")]},
]
CASES += EXTRA_CASES
DATE = r"\d{4}年\d{1,2}月\d{1,2}日"
NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?:\.\d{1,2})?"


def iso(value):
    year, month, day = map(int, re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value).groups())
    return date(year, month, day).isoformat()


def one(pattern, text):
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1: raise ValueError("missing or ambiguous event clause")
    return matches[0]


def evidence_page(fragment, pages):
    found = [number for number, page in enumerate(pages, 1) if fragment in page]
    if len(found) != 1: raise ValueError("event evidence is not on one unambiguous page")
    return found[0]


def parse_document(pages, code, kind, role):
    if not pages or any(not isinstance(page,str) for page in pages): raise ValueError("missing event text")
    pages = [compact(page) for page in pages]
    text = "".join(pages)
    if one(r'基金代码:[“"]?(\d{6})(?!\d)', text)[1] != code[:6]: raise ValueError("wrong event fund identity")
    action = {"merge":"合并", "split":"拆分", "creation_unit":""}[kind]
    if role == "unit_notice":
        match = one(r"从("+DATE+r")起,本基金最小申购、赎回单位自("+NUMBER+r")万份调整为("+NUMBER+r")万份。",text)
        before,after = Decimal(match[2].replace(',',''))*10000,Decimal(match[3].replace(',',''))*10000
        if min(before,after)<=0 or before==after: raise ValueError('invalid creation unit change')
        return {"event_date":iso(match[1]),"unit_before_shares":decimal_text(before),
                "unit_after_shares":decimal_text(after),"evidence_pages":[evidence_page(match[0],pages)]}
    if role in ("plan","reminder"):
        match = one(r"1、权益登记日:("+DATE+r")。2、(?:份额"+action+r"日|除权日):("+DATE+r")。",text)
        same_day = "于份额合并日(权益登记日当日)进行变更登记" in text
        event_date = iso(match[1] if same_day else match[2])
        if iso(match[1])>event_date or same_day and iso(match[2])<event_date: raise ValueError('invalid event date order')
        if "除权日:" in match[0] and not same_day: raise ValueError("ex-right date cannot replace the share event date")
        ratio = one(r"本基金本次基金份额"+action+r"比例为(\d+\.\d+)。",text)
        factor = Decimal(ratio[1])
        if not (factor>1 if kind=='split' else 0<factor<1): raise ValueError('ratio has wrong event direction')
        ratio_page = evidence_page(ratio[0], pages)
        return {"record_date":iso(match[1]),"event_date":event_date,"ratio":ratio[1],
                "ex_right_date":iso(match[2]) if same_day else None,
                "evidence_pages":sorted({evidence_page(match[0],pages),ratio_page})}
    if role == "cancellation":
        match = one(r"本基金原定于("+DATE+r")为权益登记日、("+DATE+r")为份额拆分日实施的基金份额拆分将取消。",text)
        if iso(match[1])>iso(match[2]): raise ValueError('invalid cancelled plan date order')
        return {"record_date":iso(match[1]),"event_date":iso(match[2]),"evidence_pages":[evidence_page(match[0],pages)]}
    if role != "result" or kind != "merge": raise ValueError("unsupported event review grammar")
    if "本基金管理人已按照上述合并比例" not in text and "登记结算机构已分别按照上述合并比例" not in text:
        raise ValueError("a plan is not an implementation result")
    ratio = one(r"本基金本次基金份额合并比例为(\d+\.\d+)。", text)
    rounding = one(r"小数点后基金份额均进位为1份", text)
    if code == "510310.SH":
        before = one(r"份额合并日\(权益登记日当日,即("+DATE+r")\),本基金合并前,场内基金份额总额为("+NUMBER+r")份,场外基金份额总额为("+NUMBER+r")份",text)
        after = one(r"本基金合并后,场内基金份额总额为("+NUMBER+r")份,场外基金份额总额为("+NUMBER+r")份",text)
        event_date = record_date = iso(before[1])
        scopes = [("exchange",before[2],after[1]),("off_exchange",before[3],after[2])]
    elif code == "512100.SH":
        register = one(r"对权益登记日\(("+DATE+r")\)登记在册",text)
        before = one(r"在份额合并日\(("+DATE+r")\)本基金合并前的基金份额总额为("+NUMBER+r")份",text)
        after = one(r"在份额合并日\(("+DATE+r")\)本基金合并后的基金份额总额为("+NUMBER+r")份",text)
        if before[1] != after[1]: raise ValueError("before/after dates differ")
        record_date, event_date = iso(register[1]),iso(before[1])
        scopes = [("fund_total",before[2],after[2])]
    else: raise ValueError("unreviewed result layout")
    totals = []
    for scope, start, end in scopes:
        start,end,factor = Decimal(start.replace(',','')),Decimal(end.replace(',','')),Decimal(ratio[1])
        if not 0 < factor < 1 or min(start,end) <= 0: raise ValueError("invalid merge ratio or share total")
        totals.append({"scope":scope,"before_shares":decimal_text(start),"after_shares":decimal_text(end),
                       "after_minus_simple_ratio_shares":decimal_text(end-start*factor)})
    return {"record_date":record_date,"event_date":event_date,"ratio":ratio[1],"holder_rounding":"ceil_to_whole_share",
            "reported_totals":totals,"evidence_pages":sorted({evidence_page(ratio[0],pages),evidence_page(rounding[0],pages),
                evidence_page(before[0],pages),evidence_page(after[0],pages)})}


def reconcile_case(case, documents):
    """One event per source chain; repeated reminders cannot become extra events."""
    plans = [(doc,parsed) for doc,role,parsed in documents if role in ("plan","reminder")]
    terminal = [(doc,role,parsed) for doc,role,parsed in documents if role not in ("plan","reminder")]
    if len(terminal) != 1 or len({doc['document_id'] for doc,_,_ in documents}) != len(documents):
        raise ValueError("ambiguous event chain")
    doc, role, result = terminal[0]
    expected_role = {'implemented':'result','cancelled':'cancellation','announced_effective':'unit_notice'}[case['resolution']]
    if role != expected_role:
        raise ValueError('terminal source role does not prove this resolution')
    known = {}
    if plans:
        for key in ('record_date','event_date','ratio','ex_right_date','registration_date'):
            values={plan[key] for _,plan in plans if plan.get(key) is not None}
            if len(values)>1:raise ValueError('conflicting plan facts')
            known[key]=next(iter(values)) if values else None
        for source,plan in plans:
            post_event_reminder=(case.get('allow_post_event_reminder') is True
                                and any(item is source and source_role=='reminder' for item,source_role,_ in documents))
            if source['published_on'] > doc['published_on'] or source['published_on'] > plan['event_date'] and not post_event_reminder:
                raise ValueError("conflicting or incorrectly ordered plan")
        if any(result.get(key) is not None and known.get(key) is not None and result[key]!=known[key]
               for key in ('record_date','event_date','registration_date')):
            raise ValueError("terminal notice resolves a different plan")
        if case['resolution']=='implemented' and known.get('ratio') is not None and result.get('ratio')!=known['ratio']:
            raise ValueError("result ratio differs from plan")
        if case['resolution']=='cancelled' and doc['published_on'] >= result['event_date']:
            raise ValueError("cancellation chronology is not the reviewed case")
    elif case['kind'] != 'creation_unit' and case.get('source_scope')!='result_only': raise ValueError("missing plan")
    if case['resolution'] in ('implemented','announced_effective') and doc['published_on'] < result['event_date']:
        raise ValueError("a future proposal cannot prove an implementation")
    return {"event_id":case['id'],"code":case['code'],"kind":case['kind'],"resolution":case['resolution'],
            **{key:value for key,value in result.items() if key not in ('ratio','evidence_pages')},
            "planned_ratio":known.get('ratio'),
            "ex_right_date":result.get('ex_right_date') or known.get('ex_right_date'),
            "plan_holder_rounding":sorted({plan['holder_rounding'] for _,plan in plans if plan.get('holder_rounding') and plan['holder_rounding']!='not_stated'}),
            "source_scope":case.get('source_scope','selected_plan_and_result' if plans else 'unit_notice'),
            "effective_ratio":result.get('ratio') if case['resolution']=='implemented' else None,
            "resolution_published_on":doc['published_on'],"not_a_subscription_flow":True}


def share_event_status(directory: Path, announcements: dict, now: datetime) -> dict:
    base = {"version":VERSION,"availability":"missing","events":[],"reviewed_events":0,"reconciled_documents":0,
            "selected_documents":announcements.get('review_required_count'),"all_selected_documents_reconciled":False,
            "corporate_actions_checked":False,"note":"仅逐条核对已列事项；计划、取消、实施结果及最小申赎单位分开。历史事项不证明当前窗没有其他份额事件，未用于净申赎校正。"}
    if parser_digest() != PARSER_DIGEST: return {**base,"availability":"reload_required"}
    if announcements.get('availability') != 'observed' or announcements.get('fulltext',{}).get('availability') != 'observed': return base
    try:
        capture = json.loads((directory/'document_capture.json').read_text()); key=capture.pop('content_digest')
        completed = datetime.fromisoformat(capture['completed_at'])
        if (digest(capture)!=key or key!=announcements['fulltext']['content_digest'] or capture['catalog_digest']!=announcements['content_digest']
            or completed.tzinfo is None or completed>now): raise ValueError('capture binding mismatch')
        selected = {doc['document_id']:doc for catalog in announcements['catalogs'] for doc in catalog['required_documents']}
    except (OSError,ValueError,KeyError,TypeError): return {**base,'availability':'invalid'}
    events, reviewed, failures = [], set(), []
    for case in CASES:
        try:
            chain, evidence = [], []
            for document_id,role in case['documents']:
                doc=selected[document_id]; result=capture['documents'][document_id]
                title=compact(doc['title'])
                if ((role=='result' and {'merge':'合并','split':'拆分','conversion':'折算'}.get(case['kind'],'')+'结果' not in title) or (role=='cancellation' and '取消基金份额拆分' not in title)
                    or (role=='reminder' and '提示性公告' not in title) or (role=='plan' and any(word in title for word in ('结果','取消','提示性公告')))
                    or (role=='unit_notice' and ('调整最小申购、赎回单位的公告' not in title or any(word in title for word in ('合并','拆分'))))):
                    raise ValueError('source title has a different role')
                observed=datetime.fromisoformat(result['responses'][-1]['observed_at'])
                if (doc['code']!=case['code'] or not valid_ready(result,directory,doc,capture['catalog_digest'])
                    or observed.tzinfo is None or observed>completed or doc['published_on']>announcements['through']
                    or observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()<doc['published_on']):
                    raise ValueError('document binding mismatch')
                body=(directory/'document_text'/f"{result['text_sha256']}.json").read_bytes()
                if hashlib.sha256(body).hexdigest()!=result['text_sha256']: raise ValueError('event text changed')
                pages=json.loads(body)['pages']
                parsed=(parse_profile(pages,case['code'],case['kind'],role,case['profile'][role])
                        if case.get('profile') else parse_document(pages,case['code'],case['kind'],role))
                chain.append((doc,role,parsed))
                evidence.append({'document_id':document_id,'role':role,'published_on':doc['published_on'],'title':doc['title'],
                    'url':doc['url'] if result['format']=='issuer_html' else result['responses'][-1]['url'],
                    'format':result['format'],'pages':[] if result['format']=='issuer_html' else parsed['evidence_pages'],
                    'announced_ratio':parsed.get('ratio') if role in ('plan','reminder') else None,'text_sha256':result['text_sha256'],
                    'observed_at':result['responses'][-1]['observed_at']})
            event=reconcile_case(case,chain)
            event.update(documents=evidence,within_catalog_window=announcements['window_start']<=event['event_date']<=announcements['window_end'])
            events.append(event); reviewed.update(doc['document_id'] for doc,_,_ in chain)
        except (OSError,ValueError,KeyError,TypeError,AttributeError,IndexError):
            failures.append({'event_id':case['id'],'reason':'source_or_semantics_unverified'})
    return {**base,'availability':'partial' if events else 'invalid','events':sorted(events,key=lambda row:(row['event_date'],row['event_id'])),
            'reviewed_events':len(events),'reconciled_documents':len(reviewed),'pending_documents':len(selected)-len(reviewed),'failures':failures,
            'catalog_digest':announcements['content_digest'],'capture_digest':key,'parser_digest':PARSER_DIGEST,'capture_completed_at':capture['completed_at']}
