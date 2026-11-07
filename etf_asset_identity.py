"""A single published asset-value identity is not independent daily share evidence."""
from datetime import date,datetime
from decimal import Decimal,localcontext
import html
from html.parser import HTMLParser
import re
import unicodedata
from zoneinfo import ZoneInfo

from canonical_json import digest

VERSION='etf_published_asset_identity_v1'
CODE='510310.SH'
NUMBER=r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?'


class AssetField(HTMLParser):
    def __init__(self,page):
        super().__init__();self.cells=[];self.active=None;self.bad=False;self.feed(page);self.close()

    def handle_starttag(self,tag,attrs):
        if tag=='td' and any(k=='id' and v=='baseinfoAsset' for k,v in attrs):
            if self.active is not None or sum(k=='id' for k,_ in attrs)!=1:self.bad=True
            self.active=[]

    def handle_data(self,text):
        if self.active is not None:self.active.append(text)

    def handle_endtag(self,tag):
        if tag=='td' and self.active is not None:self.cells.append(''.join(self.active));self.active=None


def decimal(value):
    if isinstance(value,bool) or not re.fullmatch(NUMBER,str(value)):raise ValueError('invalid published number')
    result=Decimal(str(value).replace(',',''))
    if result<=0:raise ValueError('nonpositive published number')
    return result


def parse_asset_disclosure(page,ref,now):
    """Called only after the issuer NAV reader has verified these original bytes."""
    base={'availability':'missing','code':CODE}
    parsed=AssetField(page);cells=parsed.cells
    if parsed.bad or parsed.active is not None:return {**base,'availability':'invalid'}
    if not cells:return base
    try:
        text=re.sub(r'\s+','',unicodedata.normalize('NFKC',html.unescape(page)))
        if (len(cells)!=1 or re.findall(r'varfundCode="(\d+)"',text)!=[CODE[:6]]
            or '三个要素均为整个基金(不区分份额)层面数据' not in text):raise ValueError('asset identity or scope clause missing')
        cell=re.sub(r'\s+','',unicodedata.normalize('NFKC',html.unescape(cells[0])))
        match=re.fullmatch(r'数据截至(\d{4}-\d{2}-\d{2}):('+NUMBER+r')元',cell)
        if not match:raise ValueError('asset amount unit or as-of missing')
        day=date.fromisoformat(match[1]).isoformat();value=decimal(match[2]);observed=datetime.fromisoformat(ref['observed_at'])
        if observed.tzinfo is None or observed>now or day>observed.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat():raise ValueError('invalid asset observation')
        return {**base,'availability':'observed','asset_asof':day,'asset_yuan':format(value,'f'),'raw_amount_text':match[2],
                'scope':'site_states_whole_fund_net_assets','asset_field':'baseinfoAsset','asset_rounding_rule_verified':False,
                'source_url':ref['url'],'response_sha256':ref['response_sha256'],'observed_at':ref['observed_at']}
    except (ValueError,TypeError,KeyError):return {**base,'availability':'invalid'}


def identity_status(issuer,sse,target=None):
    base={'version':VERSION,'availability':'missing','disclosed_points':None,'compared_points':None,'declared_points':1,'reviewed_code':CODE,
          'matches_market_target':False,'source_independence_verified':False,'whole_fund_daily_scope_verified':False,
          'off_exchange_shares':None,'full_fund_daily_shares':None,'estimated_net_subscription_yuan':None,'historical_PIT':False,
          'note':'只核对一个基金的一个归档披露时点。公布值相等不证明来源独立、场外份额为零、逐日全基金范围、精度或最终修订；差额也不是申赎，不反推实际份额，不校正任何日序列。'}
    try:
        audit=issuer['raw_reconciliation']
        if issuer['availability']!='observed' or audit['availability']!='source_reconciled' or audit['exact_source_projection_verified'] is not True:return base
        if issuer['content_digest']!=audit['snapshot_digest']:raise ValueError('unbound issuer projection')
        funds=[f for f in audit['funds'] if f['code']==CODE]
        if len(funds)!=1:raise ValueError('ambiguous issuer fund')
        fund=funds[0];asset=fund.get('asset_disclosure',{})
        if asset.get('availability')!='observed':return {**base,'availability':asset.get('availability','missing')}
        if asset['code']!=CODE or asset['scope']!='site_states_whole_fund_net_assets':raise ValueError('foreign asset scope')
        result={**base,'availability':'asset_only','disclosed_points':1,'compared_points':0,'asset':asset,
                'matches_market_target':asset['asset_asof']==target,'issuer_snapshot_digest':audit['snapshot_digest']}
        share_audit=sse.get('raw_reconciliation',{})
        if sse.get('availability')!='observed' or share_audit.get('availability')!='source_reconciled' or share_audit.get('exact_source_projection_verified') is not True:return result
        if sse['content_digest']!=share_audit['snapshot_digest']:raise ValueError('unbound share projection')
        share_funds=[f for f in share_audit['funds'] if f['code']==CODE]
        if len(share_funds)!=1 or share_funds[0]['share_unit']!='ten_thousand_shares' or fund['unit']!='CNY_per_share':raise ValueError('incompatible comparison units')
        day=asset['asset_asof'];navs=[p for p in fund['records'] if p['date']==day];shares=[p for p in share_funds[0]['records'] if p['date']==day]
        if not navs or not shares:return result
        if len(navs)!=1 or len(shares)!=1:raise ValueError('duplicate comparison date')
        nav,share=navs[0],shares[0]
        with localcontext() as context:
            context.prec=sum(len(str(v)) for v in (share['source_value'],nav['source_value'],asset['asset_yuan']))+10
            units=decimal(share['source_value'])*10000;unit_nav=decimal(nav['source_value'])
            if units!=decimal(share['shares']):raise ValueError('share conversion mismatch')
            nominal=units*unit_nav;difference=decimal(asset['asset_yuan'])-nominal
        result.update(availability='arithmetic_compared',compared_points=1,date=day,published_shares=format(units,'f'),unit_nav=format(unit_nav,'f'),
                      shares_times_unit_nav_yuan=format(nominal,'f'),difference_yuan=format(difference,'f'),
                      relation='equal_as_published' if difference==0 else 'different_as_published',NAV_source=nav,share_source=share,
                      share_snapshot_digest=share_audit['snapshot_digest'])
        result['comparison_digest']=digest(result)
        return result
    except (ValueError,TypeError,KeyError,IndexError):return {**base,'availability':'invalid'}
