"""Source-bound settlement stages, aggregate accounts and common market windows."""
from datetime import datetime
from decimal import Decimal as D, ROUND_HALF_UP
from hashlib import sha256
from zoneinfo import ZoneInfo
import json,re,unicodedata
from canonical_json import digest


def row_numbers(text,label):
    pattern=r'\s*'.join(re.escape(c)for c in label)+r'\s+([^\n]+)'
    match=re.search(pattern,text)
    if not match:raise ValueError('financial row missing: '+label)
    return [D(x.replace(',','').removesuffix('%')) for x in re.findall(r'-?[\d,]+(?:\.\d+)?%?',match[1])]


def yigou_settlement(inputs,prior):
    p=inputs.get('yigou_settlement')
    if p is None:return None
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):raise ValueError('settlement packet changed')
    m=inputs['current_extension']['market_inputs']
    if not prior or p['prior_digest']!=digest(prior)or p['market_digest']!=digest(m):raise ValueError('settlement prior/market changed')
    sources={s['announcement_id']:s for s in p['sources']}
    if len(p['sources'])!=5 or set(sources)!=set(SOURCE_SHA):raise ValueError('settlement source set changed')
    for aid,s in sources.items():
        meta=s['raw_item'];pub=datetime.fromtimestamp(meta['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
        if str(meta['announcementId'])!=aid or meta['secCode']!='002024'or s['symbol']!='002024'or meta['announcementTitle']!=s['title']or s['url']!='https://static.cninfo.com.cn/'+meta['adjunctUrl']or s['published_on']!=pub or pub>'2026-11-19'or s['sha256']!=SOURCE_SHA[aid]or not s['protected_gate_passed']:raise ValueError('settlement source identity/date changed')
        if s['reused']!=(aid in REUSED)or len(s['page_hashes'])!=s['pages']or set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}:raise ValueError('settlement reuse/pages changed')
        for n,text in s['selected_pages'].items():
            if sha256(text.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('settlement page hash changed')
        for n,text in s['text_pages'].items():
            if re.sub(r'\s+','',unicodedata.normalize('NFKC',text))!=s['selected_pages'][n]:raise ValueError('settlement extracted text changed')
    for (aid,n),clauses in CLAUSES.items():
        if any(c not in sources[aid]['selected_pages'][str(n)]for c in clauses):raise ValueError('settlement clause missing')
    catalog=p['catalog'];rows=catalog['rows']
    if catalog['total']!=55 or len(rows)!=55 or len({r['announcement_id']for r in rows})!=55 or any(r['symbol']!='002024'or not '2026-07-01'<=r['announcement_date']<='2026-11-19'for r in rows):raise ValueError('settlement catalog changed')
    for aid in ['1225532237','1225638414']:
        if sources[aid]['raw_item']!=next(r['raw_item']for r in rows if r['announcement_id']==aid):raise ValueError('settlement catalog binding changed')
    h=sources['1225532237']['text_pages'];q=sources['1225638414']['text_pages']
    half={'net':row_numbers(h['6'],'归属于上市公司股东的净利润')[0],'core':row_numbers(h['6'],'归属于上市公司股东的扣除非经常性损益的净利润')[0],'cash':row_numbers(h['6'],'经营活动产生的现金流量净额')[0],'nonrecurring':row_numbers(h['7'],'合计')[0],'debt':row_numbers(h['7'],'债务重组损益')[0]}
    nine={'net':row_numbers(q['1'],'归属于上市公司股东的净利润')[2],'core':row_numbers(q['1'],'归属于上市公司股东的扣除非经常性损益的净利润')[2],'cash':row_numbers(q['1'],'经营活动产生的现金流量净额')[0],'nonrecurring':row_numbers(q['2'],'合计')[1],'debt':row_numbers(q['2'],'债务重组损益')[1]}
    if half['cash']!=row_numbers(h['154'],'经营活动产生的现金流量净额')[0]or nine['cash']!=row_numbers(q['12'],'经营活动产生的现金流量净额')[0]:raise ValueError('settlement cash statement conflict')
    quarter={k:nine[k]-half[k]for k in half}
    if quarter['net']!=row_numbers(q['1'],'归属于上市公司股东的净利润')[0]or quarter['core']!=row_numbers(q['1'],'归属于上市公司股东的扣除非经常性损益的净利润')[0]or quarter['nonrecurring']!=row_numbers(q['2'],'合计')[0]or quarter['debt']!=row_numbers(q['2'],'债务重组损益')[0]:raise ValueError('settlement quarterly bridge conflict')
    if any(r['core']+r['nonrecurring']!=r['net']for r in [half,nine,quarter]):raise ValueError('settlement profit bridge conflict')
    financials=[{'key':key,'label':label,'period':period,'unit':'千元','values':{k:float(v)for k,v in r.items()},'yi_yuan':{k:float(v/D(100000))for k,v in r.items()},'cash_derived':key=='quarter','audited':False}for key,label,period,r in [('half','上半年','2026-01-01—2026-06-30',half),('nine','前三季度','2026-01-01—2026-09-30',nine),('quarter','第三季度单季','2026-07-01—2026-09-30',quarter)]]
    dates=sorted(d for d in m['calendar']if '2026-07-03'<=d<='2026-11-19');prices={r['trade_date']:r for r in m['fixed_prices']if r['symbol']=='002024'and dates[0]<=r['trade_date']<=dates[-1]}
    if len(dates)!=94 or set(prices)!=set(dates)or any(not r['has_trade']or r['raw_volume']<=0 for r in prices.values()):raise ValueError('settlement traded dates changed')
    from st_regime_comparison import build
    daily=build(m)['daily'];st={r['date']:D(str(r['return_pct']))for r in daily};bench={(r['benchmark_id'],r['trade_date']):D(str(r['close']))for r in m['benchmarks']};cross={s['key']:s for s in p['cross_sources']}
    if set(cross)!={'sz002024','000985','932000'}or len(p['cross_sources'])!=3:raise ValueError('settlement quote sources changed')
    for key,s in cross.items():
        url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz002024,day,2026-07-03,2026-11-19,320,qfq'if key=='sz002024'else f'https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode={key}&startDate=20260703&endDate=20261119'
        if s['url']!=url or sha256(s['text'].encode()).hexdigest()!=s['sha256']:raise ValueError('settlement quote identity changed')
    block=json.loads(cross['sz002024']['text'])['data']['sz002024'];quotes={r[0]:r for r in block.get('qfqday',block.get('day',[]))}
    if block['qt']['sz002024'][2]!='002024':raise ValueError('settlement quote symbol changed')
    for day in dates:
        if abs(D(quotes[day][2])-D(str(prices[day]['close'])))>D('1e-9')or D(quotes[day][5])<=0:raise ValueError('settlement daily quote conflict')
    for code,label in [('000985','csi_all_share'),('932000','csi_2000')]:
        official={r['tradeDate']:r for r in json.loads(cross[code]['text'])['data']}
        for day in dates:
            row=official[day.replace('-','')]
            if row['indexCode']!=code or bench[(label,day)].quantize(D('.01'),rounding=ROUND_HALF_UP)!=D(str(row['close'])):raise ValueError('settlement daily index conflict')
    def window(a,z):
        days=[d for d in dates if a<d<=z];s=D(1)
        for day in days:s*=1+st[day]/100
        return {'anchor':a,'through':z,'days':len(days),'stock_pct':float((D(str(prices[z]['close']))/D(str(prices[a]['close']))-1)*100),'st_pct':float((s-1)*100),'market_pct':float((bench[('csi_all_share',z)]/bench[('csi_all_share',a)]-1)*100)}
    ends=['2026-07-03','2026-07-31','2026-08-31','2026-09-30','2026-10-30','2026-11-19'];monthly=[window(a,z)for a,z in zip(ends,ends[1:])];events=[]
    for aid in ['1225532237','1225638414']:
        pub=sources[aid]['published_on'];a=max(d for d in dates if d<pub);future=[d for d in dates if d>=pub]
        events.append({'source_id':aid,'published_on':pub,'windows':[{'requested_days':n,'complete':len(future)>=n,**(window(a,future[n-1])if len(future)>=n else {'anchor':a,'through':None,'days':None,'stock_pct':None,'st_pct':None,'market_pct':None})}for n in [1,5,20]]})
    public=lambda s:{k:v for k,v in s.items()if k not in ['raw_item','selected_pages','page_hashes','text_pages']}
    return {'symbol':'002024','through':'2026-11-19','financials':financials,'monthly':monthly,'full':window(dates[0],dates[-1]),'events':events,'sources':[public(s)for s in sources.values()],'catalog_count':55,'specific_settlement_stage':'公司股东会已通过；另一侧审批、正式签约和分期支付，仍缺可对应的完成证据','lead':'利润为正，不等于经营修复；债务和解收益也不是等额现金到账。前三季度扣非仍亏损，第三季度单季经营现金流转为净流出；公司层面的汇总收益不能证明6月云创门店和解已经履约。','scope_traps':[{'label':'云创门店租赁和解','finding':'6月方案预计豁免68953万元，公司股东会6月25日通过；另一侧审批、正式签约和分期支付仍需对应原件。','source_id':'1225346702','pages':[7,8]},{'label':'云享仓储物流计划','finding':'半年报披露的是另一项流动性支持展期，不能替云创和解证明持有人审批通过。','source_id':'1225532237','pages':[54]},{'label':'苏宁国际境外借款','finding':'半年报称该笔借款在报告期内结清；主体、对手方与事项均不同，不证明云创门店和解结清。','source_id':'1225532237','pages':[21,54,55]}],'counts':{'new_files':2,'new_pages':205,'reused_files':3,'reused_pages':15,'critical_pages_viewed':24,'stock_daily_crosschecks':94,'index_daily_crosschecks':188,'new_quote_requests':0},'boundaries':['半年报和三季报均未经审计；季度现金流由前三季累计减半年累计推导，保留原千元值和换算。','非经常性损益合计已含税和少数股东影响，不能与其中债务重组损益再次相加；扣非亏损也不直接等于现金流出。','报告期、披露日和期后事项分开：半年报披露的7月至目前初步统计，不倒填为上半年收益。','55条完整目录及两份选样财报未定位这笔和解的后续完整履约链，不证明相关文件不存在；汇总收益和同名事项不能代替逐笔核验。','价格窗口以前一交易日收盘为锚，准确发布时间未核；周末公告从下一交易日观察，不当可执行收益或净因果。','报价复用既有响应并核全期，渠道一致不证明底层供应链完全独立；旧期初54/150覆盖与全部旧主题不改。'],'method_promotions':0,'tracked_list_changed':False}

SOURCE_SHA={'1225346702': '5af3861ed04004c014aa7385558dcb36f8d52db110aba1262e2749799ec2653b', '1225064494': '04187c63cd9bb2117d0e9982d83755a85ec9369134e0f37f8355e933f67c25c9', '1225388521': '35f57a44f5ea72c6fc042ff4bfda212a245bcccc4823acdb8c964baf6bcb2fb9', '1225638414': '388b34eacd832ad190728c39822e2b8085781a83a5df088e7c248519c49cee89', '1225532237': '55dc88a16634dc7de7de7d6e857e61b6725cb796d3d2639a9549e38008ac0fb1'}
REUSED={'1225346702', '1225064494', '1225388521'}
CLAUSES={('1225346702', 7): ['68,953', '40%', '60%', '持有人大会审议通过后'], ('1225346702', 8): ['1.2亿元', '逐步确认'], ('1225388521', 4): ['关于债务和解的议案', '99.28%'], ('1225064494', 2): ['继续被实施其他风险警示'], ('1225532237', 63): ['未经审计'], ('1225532237', 54): ['苏宁云享', '2026年12月26日'], ('1225532237', 21): ['BCCSUNINGINVESTMENTS,LIMITED', '已经在报告期内结清'], ('1225532237', 55): ['2026年7月至目前', '2,654.88'], ('1225532237', 148): ['债务重组产生的投资收益526,118', '债务重组收益2,407'], ('1225638414', 13): ['未经审计']}

CLAUSES[('1225532237',6)]=['单位:千元']
CLAUSES[('1225638414',1)]=['单位:千元']
