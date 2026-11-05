"""SZSE history definitions and normalization, independent of the market projection."""
from datetime import date
from html import unescape
from html.parser import HTMLParser
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode

SOURCE_URL = 'https://fund.szse.cn/marketdata/etf/'
API_URL = 'https://fund.szse.cn/api/report/ShowReport/data'
HTTP_API_URL = 'http://fund.szse.cn/api/report/ShowReport/data'
SZSE_CODES = ('159919.SZ','159922.SZ','159845.SZ')


def archive_response(path: Path, raw: bytes):
    """Avoid truncating an existing response referenced by a complete snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == raw: return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name, suffix='.tmp', delete=False) as target:
            temporary = Path(target.name); target.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def number(value):
    if isinstance(value,bool):return None
    try:
        value=float(value)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):return None


class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def plain(value):
    parser=PlainText();parser.feed(str(value))
    return unescape(''.join(parser.parts)).strip()


def history_url(api_url,code,calendar,*,nav=False,page=1):
    if api_url not in (API_URL,HTTP_API_URL) or code not in SZSE_CODES or not calendar or type(page) is not int or page<1:
        raise ValueError('undeclared SZSE endpoint or query')
    params={'SHOWTYPE':'JSON','CATALOGID':'fund_jjjz' if nav else 'fund_jjgm','TABKEY':'tab1','txtDm':code[:6],'PAGENO':page}
    if not nav:params.update(txtStart=calendar[0],txtEnd=calendar[-1])
    return api_url+'?'+urlencode(params)


def parse_history(pages,code,calendar,*,nav=False):
    if code not in SZSE_CODES or not pages:raise ValueError('undeclared ETF/empty history')
    catalog='fund_jjjz' if nav else 'fund_jjgm'
    date_key,value_key=('nav_date','nav_per_share') if nav else ('size_date','current_size')
    total=None;records=[]
    for page,payload in enumerate(pages,1):
        if not isinstance(payload,list) or len(payload)!=1:raise ValueError('unexpected history block count')
        block=payload[0];meta=block['metadata'];unit='元' if nav else '万份'
        if any(type(meta[key]) is not int for key in ('pagesize','pageno','pagecount','recordcount')):
            raise ValueError('non-integer history pagination')
        if meta['catalogid']!=catalog or not re.search(r'[（(]'+unit+r'[）)]$',plain(meta['cols'][value_key])):
            raise ValueError('wrong catalog/unit')
        unpaginated=nav and meta['pagesize']==-1 and meta['pageno']==0 and meta['pagecount']==0
        if not unpaginated:
            if meta['pagesize'] <= 0 or meta['recordcount'] <= 0: raise ValueError('invalid history pagination size')
            if int(meta['pageno'])!=page or int(meta['pagecount'])!=len(pages):raise ValueError('incomplete history pagination')
            if total is not None and total!=int(meta['recordcount']):raise ValueError('changing history count')
            total=int(meta['recordcount'])
        elif len(pages)!=1:raise ValueError('unpaginated history has extra pages')
        records.extend(block['data'])
    if total is not None and len(records)!=total:raise ValueError('truncated history')
    result=[];seen=set()
    for record in records:
        day=date.fromisoformat(record[date_key]).isoformat();value=number(plain(record[value_key]).replace(',',''))
        if plain(record['fund_code'])!=code[:6] or day in seen or value is None or value<=0:
            raise ValueError('wrong code, duplicate date or invalid value')
        seen.add(day)
        if day not in calendar:
            if nav:continue
            raise ValueError('share history outside requested sessions')
        result.append({'ts_code':code,'nav_date' if nav else 'trade_date':day,'unit_nav' if nav else 'fd_share':value})
    return sorted(result,key=lambda row:row['nav_date' if nav else 'trade_date'])
