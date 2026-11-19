"""Source-bound control/meeting stages; never equate a notice with performance."""
from datetime import datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from canonical_json import digest

IDS={'1225599834','1225626812','1225660313','1225662349','1225675068','1225666404'}

def weiling_stage_check(inputs,current):
    p=inputs.get('weiling_stage_check')
    if p is None:return None
    if p['version']!=1 or p['content_digest']!=digest({k:v for k,v in p.items()if k!='content_digest'}):
        raise ValueError('Weiling stage packet changed')
    if current is None or p['current_extension_digest']!=digest(current)or p['through']!=current['through']or p['through']!='2026-11-19':
        raise ValueError('Weiling stage market binding changed')
    sources={s['announcement_id']:s for s in p['sources']}
    if len(p['sources'])!=6 or set(sources)!=IDS:raise ValueError('Weiling source scope changed')
    for aid,s in sources.items():
        raw=s['raw_item']
        if 'announcementTime'in raw:
            day=datetime.fromtimestamp(raw['announcementTime']/1000,ZoneInfo('Asia/Shanghai')).date().isoformat()
            valid=str(raw['announcementId'])==aid and raw['secCode']=='002667'and s['url']=='https://static.cninfo.com.cn/'+raw['adjunctUrl']
        else:
            day=raw['publishTime'][:10]
            valid=str(raw['annId'])==aid and raw['secCode']==['002667']and s['url']=='https://disc.static.szse.cn/download'+raw['attachPath']
        if not valid or s['title']!=raw.get('announcementTitle',raw.get('title'))or day!=s['published_on']or day>p['through']or not s['protected_gate_passed']:
            raise ValueError('Weiling source identity/date changed')
        if set(s['selected_pages'])!={str(n)for n in range(1,s['pages']+1)}or len(s['page_hashes'])!=s['pages']:
            raise ValueError('Weiling source pages incomplete')
        for n,t in s['selected_pages'].items():
            if sha256(t.encode()).hexdigest()!=s['page_hashes'][int(n)-1]:raise ValueError('Weiling page changed')
    def text(aid,page):return sources[aid]['selected_pages'][str(page)]
    clauses={
        ('1225599834',1):('15,936,390','286,855,020.00','6.12%','资金结算及股份过户登记手续已办理完毕','未导致公司控制权发生变更'),
        ('1225626812',2):('31,897,390','12.24%','2,850,000','正在办理中','34,747,390','13.33%'),
        ('1225626812',3):('上述议案尚需提交公司股东会审议','如上述董事候选人','将取得公司控制权'),
        ('1225660313',1):('2026年10月29日','完成过户登记'),
        ('1225660313',3):('自2026年11月4日起','成为公司的控股股东'),
        ('1225660313',4):('自2026年11月4日起','成为公司实际控制人'),
        ('1225666404',5):('2026年8月28日至2026年9月30日','未导致公司控制权发生变更'),
        ('1225666404',13):('18,811,000','7.22%','控制董事会过半数董事席位'),
    }
    for aid in ['1225662349','1225675068']:
        clauses[(aid,1)]=('2026年11月23日14:00',)
        clauses[(aid,2)]=('3.00关于接受控股股东现金捐赠暨关联交易的议案','4.00关于接受关联方提供担保暨关联交易的议案')
        clauses[(aid,3)]=('关联股东须回避表决',)
    for (aid,page),tokens in clauses.items():
        if any(t not in text(aid,page)for t in tokens):raise ValueError('Weiling stage clause missing')
    dates={'1225599834':(2,'2026年10月12日'),'1225626812':(4,'2026年10月26日'),'1225660313':(5,'2026年11月5日'),'1225662349':(4,'2026年11月6日'),'1225675068':(4,'2026年11月17日')}
    for aid,(page,token)in dates.items():
        if token not in text(aid,page):raise ValueError('Weiling printed date missing')
    if '年 月 日'.replace(' ','')not in text('1225666404',14):raise ValueError('adviser signature date boundary changed')
    from st_regime_comparison import build
    from st_regime_themes import event_context
    fresh=inputs['current_extension']['market_inputs']
    if digest(fresh)!=p['market_inputs_digest']:raise ValueError('Weiling event market inputs changed')
    daily=build(fresh)['daily']
    definitions=[
        ('1225599834','要约已结算过户，当时控制权未变','公司披露1593.639万股要约股份、约2.87亿元收购价款已完成结算及过户，持股6.12%；当时明确控制权未变。这笔股东间收购价款不能当上市公司收到捐赠。',[1,2],'2026-10-12',None),
        ('1225626812','第一大股东与控制权，仍隔着后续程序','已登记3189.739万股、12.24%；285万股登记仍在办理。3474.739万股、13.33%为全部登记后的口径；控制权仍以股东会选举和董事会改组为条件。',[1,2,3],'2026-10-26',None),
        ('1225660313','后续披露已自11月4日起变更控制权','公司披露截至10月29日相关股份已登记，山南锑金持股13.33%；11月4日董事补选后可决定过半数董事选任，公告引述法律意见认定控股股东和实际控制人自该日起变更。不能倒填成10月要约过户时已取得控制权。',[1,3,4,5],'2026-11-05','2026-11-04'),
        ('1225662349','赠款与担保：11月23日拟审议，尚无本批结果','原通知及11月18日提示均安排11月23日14时审议赠款和关联担保，议案3、4关联股东回避。提示性公告不是表决通过，更不是赠款到账、贷款放款或经营利润。',[1,2,3,4],'2026-11-06','2026-11-23'),
    ]
    rows=[]
    for aid,title,change,pages,printed,effective in definitions:
        s=sources[aid];e={'id':'weiling_'+aid,'symbol':'002667','published_on':s['published_on'],'document_dated_on':printed,'title':title,'change':change,'pages':pages,'effective_or_scheduled_on':effective,'source':{k:v for k,v in s.items()if k not in ('selected_pages','page_hashes','raw_item')}}
        e['observation']=event_context(e,'002667',fresh,daily);rows.append(e)
    public=lambda aid:{k:v for k,v in sources[aid].items()if k not in ('selected_pages','page_hashes','raw_item')}
    return {'through':p['through'],'symbol':'002667.SZ','rows':rows,'meeting':{'scheduled_on':'2026-11-23','time':'14:00','state_at_cutoff':'scheduled_not_passed','reminder':public('1225675068'),'reminder_pages':[1,2,3,4],'reminder_printed_on':'2026-11-17','original_published_on':sources['1225662349']['published_on']},'adviser':{'source':public('1225666404'),'pages':[5,13,14],'report_start':'2026-08-28','report_end':'2026-09-30','document_dated_on':None,'scope':'三季持续督导另在其他事项转述后续控制权变化；不把9月覆盖冒充11月全部业务核查，签署页未填写确切年月日。'},'counts':{'pdf_files':6,'pdf_pages':sum(s['pages']for s in sources.values()),'timeline_stages':4,'meeting_matters':1},'boundary':'六份文件不等于六次独立验证。股东间收购价款、现金捐赠、融资额度、控制权与经营改善分别核对；通知与提醒归同一待审议事项。原通知正文回指11月6日登载而正式目录为11月7日，保留差异，不认证最早分钟。旧行情和原事实不改写，事件行情从披露日收盘起算，不代表最早反应或公告净影响。'}
