"""Reviewed clause layouts for historical ETF conversions; no downloaded code is executed."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

from etf_quarterly import compact, decimal_text

D = r"\d{4}年\d{1,2}月\d{1,2}日"
N = r"(?:0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)(?:\.\d{1,2})?"
F = r"(?:0|[1-9]\d*)(?:\.\d+)?"
RATIO = r"(?:本次)?基金份额(?:折算|拆分)比例为(?:1:)?("+F+r")"
SUBJECTS = {
    '510300.SH':'华泰柏瑞沪深300交易型开放式指数证券投资基金',
    '510330.SH':'华夏沪深300交易型开放式指数证券投资基金',
    '510500.SH':'中证500交易型开放式指数证券投资基金',
    '159919.SZ':'嘉实沪深300交易型开放式指数证券投资基金',
    '159922.SZ':'嘉实中证500交易型开放式指数证券投资基金',
    '159845.SZ':'华夏中证1000交易型开放式指数证券投资基金',
}
ROUNDING = {
    'ceil_to_whole_share':r"小数点后基金份额均进位为1份",
    'nearest_whole_share':r"折算后的基金份额采取四舍五入的方法计算保留到整数位",
    'floor_to_whole_share':r"(?:折算|拆分)后的基金份额(?:采用截(?:位|尾)法保留至整数位,不足1份部分归入基金资产|保留到整数位,小数部分舍去,由此产生的误差计入基金财产|(?:持有人持有的基金份额)?计算至整数位\(小数部分舍去,舍去部分计入基金财产\)|采用保留至整数位,小数部分舍去,由此产生的误差计入基金财产)",
}


def layout(event, *, record=None, registration=None, ex_right=None, rounding='not_stated', ratio=RATIO,
           ratio_optional=False, same=(), requires=()):
    return {'dates':{'event_date':event,**({'record_date':record} if record else {}),
                    **({'registration_date':registration} if registration else {}),**({'ex_right_date':ex_right} if ex_right else {})},
            'rounding':rounding,'ratio':ratio,'ratio_optional':ratio_optional,'same_dates':same,'requires':requires}


def case(code, day, kind, result, plans, plan_layout, result_layout, *, allow_post_event_reminder=False):
    return {'id':f'{code[:6]}-{kind}-{day.replace("-", "")}', 'code':code,'kind':kind,'resolution':'implemented',
            'source_scope':'selected_plan_and_result' if plans else 'result_only',
            'allow_post_event_reminder':allow_post_event_reminder,
            'documents':[(key,'plan' if i==0 else 'reminder') for i,key in enumerate(plans)]+[(result,'result')],
            'profile':{'plan':plan_layout,'reminder':plan_layout,'result':result_layout}}


SAME_CONVERSION = (('record_date','event_date'),)
EXTRA_CASES = [
    case('510300.SH','2012-05-11','conversion','8ed72fe19deacf0e1d47605215056d6530b1fa58c1c9b9573b5526b686fdb633',[],None,
         layout(r'确定('+D+r')为华泰柏瑞沪深300交易型开放式指数证券投资基金的基金份额折算日',
                registration=r'于('+D+r')进行了变更登记',rounding='nearest_whole_share')),
    case('510330.SH','2013-01-09','conversion','e75e001304ec14ab5965c463feb900742cc7342b9d8a7fe2779d734570e64f3a',
         ['d84eea255bf41e880141ed650c7df5228e4726f3cb28f1b2a61b4344ffcc4e42'],
         layout(r'并确定('+D+r')为基金份额折算日',registration=r'将于('+D+r')进行本基金基金份额的变更登记',rounding='floor_to_whole_share',ratio_optional=True),
         layout(r'确定('+D+r')为华夏沪深300交易型开放式指数证券投资基金\(以下简称“本基金”\)的基金份额折算日',
                registration=r'本基金登记结算机构已于('+D+r')进行了变更登记')),
    case('159919.SZ','2012-11-30','conversion','54ec4f03c41280e2f1f994f4847373ee38f9c1addbf09ddc9e96d50174b93644',
         ['33a8c1c695b0a87b7a0675342e68d7ee25f42e11bad842c0eb81a1d3672a8799',
          'ae3d8408d7404ffe0f675ef1bf3f9ac37d8fb0a5345cc0452492fe44d379ebf2',
          'c1b7a2cb57c1198cccd976a8ba7459d279713735a547981079ab160a17cd156d'],
         layout(r'\(一\)权益登记日、除权日、折算处理日('+D+r')',rounding='floor_to_whole_share',
                ratio=r'除权日基金份额折算比例为:('+F+r')',ratio_optional=True,same=(('record_date','event_date'),('ex_right_date','event_date'))),
         layout(r'已于('+D+r')\(折算处理日\)进行了基金份额折算',record=r'对('+D+r')\(权益登记日\)',
                registration=r'并于('+D+r')进行了变更登记',rounding='floor_to_whole_share',ratio=r'按折算比例('+F+r')')),
    case('159919.SZ','2019-01-11','conversion','bde4bfa2f2b9451fa85be4e8faffc25acd41940c8171234e8412eda010556ebe',
         ['018d2f5f0b1a8a6b2f7aa9b7dae0c014db79b20a273898cf1217580008670926','f735a8b3328c4553fdc3f91e106891cb2a25a49e9147370c96ba599547299836'],
         layout(r'\(一\)权益登记日、除权日、份额折算日('+D+r')',rounding='ceil_to_whole_share',same=(('record_date','event_date'),('ex_right_date','event_date'))),
         layout(r'已于('+D+r')\(折算处理日\)进行了基金份额折算',record=r'已于('+D+r')\(权益登记日\)',
                rounding='ceil_to_whole_share',ratio=r'按折算比例('+F+r')',same=(('registration_date','record_date'),),requires=('并于同一日进行了变更登记',))),
    case('510500.SH','2015-04-14','conversion','7858dd7801f5a9efd8abb009f4586bf6899bd577bcdbe92af759b1b3d76a948e',
         ['0de82897e59c3b3aa8209cd14affd21e94fe8f093fbd8a00f76d7e879b3ef0c0',
          'cea4e6303b77774c254d63519b61da9309b1cf7a38b1388963d83825c3891ed2',
          '38569be4a813b3c091b742bd6f8da2184dd57ef5becb699775071f9bc2ecb9fd',
          '57ef1a225814305952a1ed6fb78e7dd24cb8e523c9b8517fb1fbff0d5f74ec06',
          'cd1840883a57dc0651a4b511a879eb50b693f22a0f19d2951a8d21d001e67c7c',
          'd2038efa7ff8108e09d6e48ea13eb80225e03352a2e87f6ea86e520bd7e7cc1a'],
         layout(r'份额折算日\(除权日、T\+1日\):('+D+r')',record=r'权益登记日\(T日\):('+D+r')',
                ratio_optional=True,rounding='floor_to_whole_share',same=(('ex_right_date','event_date'),)),
         layout(r'自基金份额折算日\(('+D+r')\)起',record=r'以('+D+r')为权益登记日实施了基金份额折算',
                registration=r'于('+D+r')完成了变更登记',rounding='floor_to_whole_share')),
    case('510500.SH','2022-08-26','split','24637ed0cca67e8fe6f1766942231070f76b8e40fe5e5aaaa7d93b9faaa6c021',
         ['df58cf2a2cb9500b3e4cf0bd989c6ca784ff737e121b2f7234e3108175431c8d'],
         layout(r'1、份额拆分日:('+D+r')。',rounding='ceil_to_whole_share',same=SAME_CONVERSION,requires=('份额拆分日登记在册的本基金基金份额',)),
         layout(r'份额拆分日\(('+D+r')\)日终',rounding='ceil_to_whole_share',same=SAME_CONVERSION,
                requires=('按照上述拆分比例对该日登记在册',))),
    case('159922.SZ','2013-03-05','conversion','c9ae24a35f55aed1d6734a48cf7df6a2d1f8ba69661812c4a44ca1693bc5fd9f',
         ['3a4156b0ebfa69efd397a7b2141e7fb4d9b1434356864a722d298f7aada887a6'],
         layout(r'并确定('+D+r')为基金份额折算日',registration=r'将于('+D+r')进行本基金基金份额的变更登记',rounding='floor_to_whole_share',ratio_optional=True),
         layout(r'确定('+D+r')为嘉实中证500交易型开放式指数证券投资基金\(以下简称“本基金”\)的基金份额折算日',
                registration=r'已于('+D+r')进行了变更登记')),
    case('159922.SZ','2022-02-17','split','cf1a5a4f6c682830df4af81616390ad8f7c17b249b9ff7005275a28672e3b94c',
         ['29121d3c2d30b3eac32514a753e5e2fb875c1a716305e129bc89cc2fd73e1e3a'],
         layout(r'\(一\)权益登记日:('+D+r')',ex_right=r'\(二\)除权日:('+D+r')',rounding='floor_to_whole_share',same=SAME_CONVERSION),
         layout(r'以('+D+r')为嘉实中证500交易型开放式指数证券投资基金[^。]{0,120}的权益登记日',rounding='floor_to_whole_share',
                same=SAME_CONVERSION,requires=('权益登记日(拆分当日)',))),
    case('159922.SZ','2024-11-29','split','def3d92556b4102963c34684d62be8f9a3c5701c772324db5d237d5bd8485561',
         ['b43288c15bdf098e2ef4509a5bc0174dd99052d570b1cc08711d53d76121b12f','3b1f67ec4f8859ee01fcd09aee6e9fce004d8661fbf26f6058b26910a9e02101'],
         layout(r'\(一\)权益登记日:('+D+r')',ex_right=r'\(二\)除权日:('+D+r')',rounding='ceil_to_whole_share',same=SAME_CONVERSION),
         layout(r'份额拆分日\(('+D+r')\),本基金拆分前',rounding='ceil_to_whole_share',same=SAME_CONVERSION),allow_post_event_reminder=True),
    case('159845.SZ','2021-03-22','conversion','c395c76493b7cfd09a9045dc30bf316433251e75903e395028999233604cc0ac',
         ['9bcf06a49f0d8b4e8cf35101f306f4f97064e344efc135badbc649fd1d66ab8b'],
         layout(r'决定以('+D+r')为基金份额折算日对本基金进行基金份额折算',rounding='floor_to_whole_share',ratio_optional=True),
         layout(r'以('+D+r')为基金份额折算日对本基金进行了基金份额折算',rounding='floor_to_whole_share')),
    case('159845.SZ','2022-08-01','conversion','02c9a741edad2851e15a027d6cdb8509f8ae67ff76c48d2cc32aed2fd5015dcb',
         ['ff6f9eaa0a2ab107e64de30a8b001911ab777c30fc2da3393d8bf3a1c495a80d'],
         layout(r'\(一\)权益登记日:('+D+r')',ex_right=r'\(二\)除权日:('+D+r')',rounding='floor_to_whole_share',same=SAME_CONVERSION),
         layout(r'以('+D+r')为权益登记日,对该日在中国证券登记结算有限责任公司',rounding='floor_to_whole_share',same=SAME_CONVERSION,requires=('权益登记日(折算当日)',))),
    case('159845.SZ','2023-02-28','conversion','86057d14d49622d0fe7840f28afdd60e58c024cf3dda7820a0558a25e7e9a17c',
         ['afe6ba1c74aa0301f3c5eb5d9a523af19265cfcb8ae09eb541b45be649afe2ff'],
         layout(r'\(一\)权益登记日:('+D+r')',ex_right=r'\(二\)除权日:('+D+r')',rounding='floor_to_whole_share',same=SAME_CONVERSION),
         layout(r'以('+D+r')为权益登记日,对该日在中国证券登记结算有限责任公司',rounding='floor_to_whole_share',same=SAME_CONVERSION,requires=('权益登记日(折算当日)',))),
]


def parse_profile(pages, code, kind, role, profile):
    """Only the reviewed profile and whole source clauses define these fields."""
    if not profile or not pages or any(not isinstance(page,str) for page in pages): raise ValueError('unsupported event profile')
    normalized=[compact(page) for page in pages];text=''.join(normalized);locations=set()
    codes=set(re.findall(r'(?:基金(?:主)?代码|二级市场交易代码|交易代码):?[“"]?(\d{6})(?!\d)',text))
    if codes and codes!={code[:6]} or not codes and SUBJECTS[code] not in normalized[0]:
        raise ValueError('wrong explicit fund identity or full subject')
    def field(pattern, optional=False):
        matches=list(re.finditer(pattern,text))
        if not matches and optional:return None
        if not matches or len({match[0] for match in matches})!=1:
            raise ValueError(f'missing or ambiguous reviewed clause ({len(matches)}): {pattern}')
        match=matches[0]
        indexes=[i for i,page in enumerate(normalized,1) if match[0] in page]
        if not indexes:raise ValueError('reviewed clause crosses source pages')
        locations.update(indexes);return match
    for clause in profile['requires']:
        if clause not in text:raise ValueError('required business-date relationship missing')
        locations.update(i for i,page in enumerate(normalized,1) if clause in page)
    values={}
    for key,pattern in profile['dates'].items():
        raw=field(pattern)[1];y,m,d=map(int,re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日',raw).groups())
        values[key]=date(y,m,d).isoformat()
    for key,target in profile['same_dates']:values[key]=values[target]
    if (values.get('record_date',values['event_date'])>values['event_date']
        or values.get('registration_date',values['event_date'])<values['event_date']
        or values.get('ex_right_date',values['event_date'])<values['event_date']):raise ValueError('inconsistent business dates')
    ratio=field(profile['ratio'],profile['ratio_optional']);values['ratio']=ratio[1] if ratio else None
    if ratio and (Decimal(ratio[1])<=0 or kind=='split' and Decimal(ratio[1])<=1):raise ValueError('wrong factor direction')
    rounding=[]
    for key,pattern in ROUNDING.items():
        found=list(re.finditer(pattern,text))
        if found:
            rounding.append(key)
            for item in found:
                for i,page in enumerate(normalized,1):
                    if item[0] in page:locations.add(i)
    if len(rounding)>1 or (rounding[0] if rounding else 'not_stated')!=profile['rounding']:
        raise ValueError('whole-share rounding differs from reviewed source clause')
    values['holder_rounding']=rounding[0] if rounding else 'not_stated'
    if role=='result':
        if not re.search(r'(?:折算|拆分)结果',normalized[0][:160]):raise ValueError('source is not an implementation result')
        field(r'(?:已根据上述折算比例|已按照上述(?:折算|拆分)比例|按折算比例'+F+r'|已根据基金管理人的委托|进行拆分,并进行变更登记)')
        before=field(r'(?:折算|拆分)前,?(?:的)?(?:本基金)?基金份额总额为('+N+r')份')
        after=field(r'(?:折算|拆分)后,?(?:的)?(?:本基金)?基金份额总额为('+N+r')份',optional=True)
        if after is None:
            after=field(r'本基金(?:本次)?折算后,('+D+r')基金份额总额为('+N+r')份');end=after[2]
            raw=after[1];y,m,d=map(int,re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日',raw).groups())
            if date(y,m,d).isoformat()!=values['event_date']:raise ValueError('post-conversion total has another date')
        else:end=after[1]
        start,end=Decimal(before[1].replace(',','')),Decimal(end.replace(',',''))
        if not ratio or min(start,end)<=0:raise ValueError('missing result totals or ratio')
        values['reported_totals']=[{'scope':'fund_total','before_shares':decimal_text(start),'after_shares':decimal_text(end),
            'after_minus_simple_ratio_shares':decimal_text(end-start*Decimal(values['ratio']))}]
    values['evidence_pages']=sorted(locations)
    return values
