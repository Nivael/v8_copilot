"""Deterministic coverage-gap sample with contemporaneous facts, not outcome selection."""
from collections import Counter
from decimal import Decimal,ROUND_HALF_UP
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest

CODES=['000056','000488','000609','000610']
IDS={'1225173882','1225140244','1225173668','1225282465','1222975603','1225058546','1225058547'}

def initial_four(inputs,prior,current):
    p=inputs.get('initial_four')
    if p is None:return None
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('initial four packet changed')
    if not prior or not current or p['prior_inventory_digest']!=digest(prior['inventory'])or p['current_extension_digest']!=digest(current):raise ValueError('initial four prior state changed')
    missing=sorted(r['symbol']for r in prior['inventory']if not r['has_timely_reading_facts'])
    if missing[:4]!=CODES or p['selection']!=CODES or len(prior['inventory'])!=150:raise ValueError('initial four selection must match coverage order')
    fresh=inputs['current_extension']['market_inputs']
    if digest(fresh)!=p['market_inputs_digest']or current['through']!='2026-11-19':raise ValueError('initial four market changed')
    sources={s['announcement_id']:s for s in p['sources']}
    if len(p['sources'])!=7 or set(sources)!=IDS or Counter(s['symbol']for s in sources.values())!=Counter({'000056':1,'000488':4,'000609':1,'000610':1}):raise ValueError('initial four source scope changed')
    for aid,s in sources.items():
        meta=s['raw_item'];day=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
        if str(meta['announcementId'])!=aid or meta['secCode']!=s['symbol']or meta['announcementTitle']!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or day!=s['published_on']or day>'2026-07-03'or not s['protected_gate_passed']:raise ValueError('initial four primary identity/date changed')
        if len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('initial four pages incomplete')
        for n,t in s['selected_pages'].items():
            if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('initial four page changed')
        from st_initial_warning_origin import origin_document_date
        if origin_document_date(s)!=s['document_dated_on']:raise ValueError('initial four printed date changed')
    def text(aid,page):return sources[aid]['selected_pages'][str(page)]
    clauses={
        ('1225173882',1):('2026年4月27日','000056、200056'),
        ('1225173882',2):('期末净资产为负值','无法表示意见','持续经营重大不确定性'),
        ('1225140244',1):('20,661.77','-27,473.53','2026年4月23日'),
        ('1225140244',3):('带持续经营相关的重大不确定性段落的无保留意见','继续实施其他风险警示'),
        ('1225173668',1):('可能被实施退市风险','2026年4月27日','-54,535,894.43'),
        ('1225173668',3):('若发行成功','承诺函','财务支持'),
        ('1222975603',1):('2025年2月21日','2025年4月1日','2022年至2024年度','否定意见'),
        ('1225058546',7):('内部控制缺陷已经整改','未识别出新的内部控制重大缺陷','标准无保留意见'),
        ('1225058547',2):('带有强调事项段的无保留意见','2024年度的合并及公司利润表'),
        ('1225058547',3):('2026年3月实现全面复工','已同意降息或展期'),
        ('1225282465',1):('B股股票','200488','五大基地生产经营正常'),
    }
    for (aid,page),tokens in clauses.items():
        if any(t not in text(aid,page)for t in tokens):raise ValueError('initial four risk/remediation clause missing')
    audit=quote_audit(p['cross_sources'],fresh)
    from st_regime_comparison import build
    view=build(fresh);early=next(c for c in view['comparisons']if c['key']=='20');full=current['full_comparison'];rows=[]
    definitions=[
        ('000056','1225173882','负净资产与审计无法表示','2025年末净资产负值、财务报告无法表示意见；另有三年亏损与持续经营重大不确定性的其他风险警示。4月27日实施，不能只按名称把多项约束合成一种。','核后续年度净资产、审计意见与持续经营事项，计划化债或培育业务不当已消除。',[1,2,4]),
        ('000488','1222975603','原多项警示，已有修复披露','2025年原件列停机满三个月、连续亏损与持续经营不确定性、内控否定等警示。2026年3月已有整改和修复专项，5月公司称五基地生产正常；旧原因与已披露修复要同时保留，尚未以本批材料认证正式撤销ST。','分别核原各项警示的消除与正式申请/撤销，不把单项内控整改、复工或B股异动替代A股解除状态。',[1,2,4]),
        ('000609','1225140244','亏损与收入门槛、负净资产','2025年亏损且扣除后营收约2.07亿元，另有净资产负值；继续保留三年亏损及持续经营不确定性警示。带持续经营段的无保留意见，不能误写成财报无法表示意见。','核扣除后营业收入、净资产及持续经营条件；地产去化、债务安排和业务转型计划分别看实际进度。',[1,2,3,6]),
        ('000610','1225173668','负净资产','2025年末归母净资产约负5454万元。标题含“可能”，正文已列4月27日实施；原件当时的拟定增与股东财务支持承诺不等于已经募集或到账。','核后续募集和实际财务支持、年度净资产及正式风险状态；上涨不能替代整改证据。',[1,2,3,5]),
    ]
    public=lambda s:{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','raw_item')}
    for code,aid,risk,known,watch,pages in definitions:
        comparisons={}
        for key,c in [('early20',early),('full',full)]:
            r=next(r for r in c['fixed_after']['rows']if r['symbol']==code);comparisons[key]={'anchor':c['fixed_after']['anchor'],'through':c['fixed_after']['through'],'days':c['after']['days'],'stock_pct':r['return_pct'],'market_pct':c['after']['market_change_pct'],'st_pct':c['after']['reference_change_pct'],'gap':r['gap']}
        primary=sources[aid];support=[]
        if code=='000488':
            for sid,ps,note in [('1225058546',[2,7],'内控专项明确原缺陷整改、2025年末内控为标准无保留；不是正式摘帽决定。'),('1225058547',[2,3,4],'财报为带强调事项段无保留，专项披露复工、债务安排等措施；报表列示段落含2024年度文字，保留原文，不用该段重建2025财务数字。'),('1225282465',[1,2],'异动对象是B股200488；仅取发行人一般经营披露，不作为A股异动、警示原因或反应日。')]:support.append({'source':public(sources[sid]),'pages':ps,'note':note})
        rows.append({'symbol':code,'name':next(r['name']for r in prior['inventory']if r['symbol']==code),'risk_group':risk,'known_at_anchor':known,'watch':watch,'source':public(primary),'pages':pages,'supporting':support,'comparisons':comparisons})
    inventory=[]
    for old in prior['inventory']:
        r={**old,'new_this_round':old['symbol']in CODES}
        if r['new_this_round']:
            docs=[s for s in sources.values()if s['symbol']==r['symbol']];r.update(has_timely_reading_facts=True,latest_fact_on=max(s['published_on']for s in docs),fact_ids=[*r['fact_ids'],*['initial_four_'+s['announcement_id']for s in docs]])
        inventory.append(r)
    before=sum(r['has_timely_reading_facts']for r in prior['inventory']);after=sum(r['has_timely_reading_facts']for r in inventory)
    if (before,after)!=(42,46):raise ValueError('initial four coverage arithmetic changed')
    return {'anchor':'2026-07-03','through':current['through'],'rows':rows,'inventory':inventory,'counts':{'before':before,'after':after,'remaining':150-after,'members':150,'new_companies':4,'new_files':7,'new_pages':sum(s['pages']for s in sources.values())},'quote_audit':audit,'selection_note':'按旧150只缺口名单的代码顺序取前四，不按涨跌挑样；仅补齐原先缺少的期初可知事实。四例不是完整风险分类、随机样本或独立因果验证。','boundary':'新增正文的正式披露均不晚于7月3日，落款和披露日期分别保留；覆盖46/150指已有期初可知正文事实，不表示46家公司全部警示条件或完整官方名单均已认证。旧42家阅读层及原事实不改写，新比较统一以7月3日收盘起算，涨跌不证明整改或制度净影响。','method_promotions':0,'full_membership_certification_added':False}


def quote_audit(sources,fresh):
    cross={s['key']:s for s in sources};codes=['000056','000488','000609','000610'];anchors=['2026-07-03','2026-07-31','2026-11-19']
    if set(cross)!={*['sz'+c for c in codes],'000985','932000'}or len(sources)!=6:raise ValueError('initial four crossquote scope changed')
    for s in sources:
        if sha256(s['text'].encode()).hexdigest()!=s['sha256']:raise ValueError('initial four crossquote bytes changed')
    prices={(r['symbol'],r['trade_date']):r for r in fresh['fixed_prices']};stock_points=0;float_tail=Decimal(0);returns=[]
    for c in codes:
        key='sz'+c;s=cross[key];block=json.loads(s['text'])['data'][key]
        if block['qt'][key][2]!=c or s['url']!=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={key},day,2026-07-03,2026-11-19,320,qfq':raise ValueError('initial four crossquote identity changed')
        rows=block.get('qfqday')or block.get('day');q={r[0]:r for r in rows}
        if len(q)!=len(rows)or any(r[0]>'2026-11-19'for r in rows):raise ValueError('initial four future quote rows')
        for day in anchors:
            provider=prices[(c,day)];expected=Decimal(str(provider['close']));actual=Decimal(q[day][2]);diff=abs(expected-actual);float_tail=max(float_tail,diff)
            if not provider['has_trade']or Decimal(q[day][5])<=0 or diff>Decimal('0.000000001'):raise ValueError('initial four qfq endpoint conflict')
            stock_points+=1
        for end in anchors[1:]:
            a,b=Decimal(q[anchors[0]][2]),Decimal(q[end][2]);returns.append({'symbol':c,'anchor':anchors[0],'through':end,'crossquote_pct':float((b/a-1)*100)})
    differences=[];index_points=0
    for code,label in [('000985','csi_all_share'),('932000','csi_2000')]:
        s=cross[code]
        if s['url']!=f'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={code}&startDate=20260703&endDate=20261119':raise ValueError('initial four index source changed')
        off={r['tradeDate']:r for r in json.loads(s['text'])['data']};provider={r['trade_date']:r for r in fresh['benchmarks']if r['benchmark_id']==label}
        for day in anchors:
            raw=provider[day]['close'];a=Decimal(str(raw));r=off[day.replace('-','')];b=Decimal(str(r['close']))
            if r['indexCode']!=code or a.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=b:raise ValueError('initial four official index precision conflict')
            if a!=b:differences.append({'index':code,'date':day,'provider':str(raw),'official':str(r['close'])})
            index_points+=1
    return {'stock_endpoint_points':stock_points,'stock_return_windows':len(returns),'stock_max_float_tail':str(float_tail),'stock_absolute_tolerance':'0.000000001','index_endpoint_points_at_official_precision':index_points,'unrounded_index_differences':differences,'crossquote_returns':returns,'source_refs':[{k:v for k,v in s.items()if k!='text'}for s in sources]}
