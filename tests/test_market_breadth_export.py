"""Synthetic source-format fixtures, never market observations."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from canonical_json import digest
from market_breadth import SOURCES
from market_breadth_export import EXPORT_KIND, EXPORT_URL, FIELDS, HEADERS, NS, export_params, export_rows, parse_export
from market_breadth_history import load_breadth_history, refresh_breadth_history

DAY = "2026-09-04"
NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def records():
    return [{"jyrq": DAY, "zqdm": f"{i:06}", "zqjc": "样本 公司" if i == 1 else "*ST样本",
             "qss": "10.00", "ss": "9.00", "sdf": "-10.00", "cjgs": "1.50", "cjje": "9.50",
             "ks": "10.00", "zg": "10.00", "zd": "9.00", "syl": "0.00"} for i in range(1, 12)]


def controls(rows):
    columns = dict(zip(("jyrq", "zqdm", "zqjc", "qss", "ss", "sdf", "cjgs", "cjje"),
                       ("交易日期", "证券代码", "证券简称", "前收", "今收", "涨跌幅<br>（%）", "成交量<br>(万股)", "成交金额<br>(万元)")))
    meta = {"catalogid": "1815_stock_snapshot", "tabkey": "tab1", "recordcount": 11,
            "pagesize": 10, "pagecount": 2, "pageno": 1, "cols": columns}
    head = [{"metadata": meta, "data": deepcopy(rows[:10])}]
    head[0]["data"][0]["zqjc"] = "样本&nbsp;公司"
    return head, [{"metadata": {**deepcopy(meta), "pageno": 2}, "data": deepcopy(rows[10:])}]


def workbook(rows, headers=None, formula=False, shifted=False):
    root = ET.Element("worksheet", xmlns=NS["m"])
    data = ET.SubElement(root, "sheetData")
    for index, values in enumerate([headers or HEADERS] + [[row[field] for field in FIELDS] for row in rows], 1):
        row = ET.SubElement(data, "row", r=str(index))
        for column, value in enumerate(values):
            cell = ET.SubElement(row, "c", r=f"{chr(65+column)}{index}", t="inlineStr")
            ET.SubElement(ET.SubElement(cell, "is"), "t").text = value
            if formula and index == 5 and column == 7: ET.SubElement(cell, "f").text = "1+1"
            if shifted and index == 5 and column == 7: cell.set("r", "I5")
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{NS["m"]}"><sheets><sheet name="Synthetic"/></sheets></workbook>')
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(root))
    return stream.getvalue()


def test_full_export_retains_identifiers_units_and_matches_https_boundary_rows():
    rows = records(); head, tail = controls(rows)
    rows[5].update(ss="--", cjgs="0.00", cjje="0.00", sdf="0.00")
    head, tail = controls(rows)
    block = parse_export(workbook(rows), head, tail, DAY)
    assert block["reported_total"] == 11 and len(block["rows"]) == 11
    assert block["rows"][0]["ts_code"] == "000001.SZ"
    assert block["rows"][0]["volume"] == 15000 and block["rows"][0]["amount"] == 95000
    assert block["rows"][5]["pct_chg"] is None and block["rows"][5]["is_trading"] is False


@pytest.mark.parametrize("change", ["short", "duplicate", "wrong_day", "bad_return", "units", "formula", "shifted", "head", "tail", "total", "tail_meta"])
def test_partial_or_relabelled_workbook_cannot_become_a_complete_historical_day(change):
    rows = records(); head, tail = controls(rows); options = {}
    if change == "short": rows.pop(5)
    elif change == "duplicate": rows[5]["zqdm"] = rows[4]["zqdm"]
    elif change == "wrong_day": rows[5]["jyrq"] = "2026-09-03"
    elif change == "bad_return": rows[5]["sdf"] = "1.00"
    elif change == "units": options["headers"] = [label.replace("万元", "元") for label in HEADERS]
    elif change in ("formula", "shifted"): options[change] = True
    elif change == "head": head[0]["data"][0]["ss"] = "8.00"
    elif change == "tail": tail[0]["data"][0]["zqdm"] = "000012"
    elif change == "total": head[0]["metadata"]["recordcount"] = 12
    else: tail[0]["metadata"]["catalogid"] = "other"
    with pytest.raises(ValueError): parse_export(workbook(rows, **options), head, tail, DAY)


def test_non_workbook_download_is_rejected():
    with pytest.raises(ValueError): export_rows(b"temporary error page")


class ExportClient:
    def __init__(self, store): self.store, self.calls = store, []
    def get_venue(self, venue, day):
        self.calls.append(day)
        rows = records()
        for row in rows: row['jyrq'] = day
        head, tail = controls(rows); body = workbook(rows)
        params = {'SHOWTYPE':'JSON','CATALOGID':'1815_stock_snapshot','TABKEY':'tab1','txtBeginDate':day,'txtEndDate':day}
        refs = []
        for page, payload in enumerate([head, tail, body], 1):
            raw = payload if page == 3 else json.dumps(payload).encode()
            key = hashlib.sha256(raw).hexdigest(); suffix = 'xlsx' if page == 3 else 'json'
            (self.store/'responses').mkdir(parents=True, exist_ok=True)
            (self.store/'responses'/f'{key}.{suffix}').write_bytes(raw)
            refs.append({'venue':venue,'url':EXPORT_URL if page == 3 else SOURCES['SZSE']['api_url'],
                         'params':export_params(day) if page == 3 else {**params,'PAGENO':page},
                         'response_sha256':key,'observed_at':NOW.isoformat(),**({'kind':EXPORT_KIND} if page == 3 else {})})
        return parse_export(body, head, tail, day), refs


def test_export_history_archives_each_original_control_and_workbook_then_repairs_changed_bytes(tmp_path):
    folder = tmp_path/'history'; client = ExportClient(tmp_path/'public_breadth')
    report = refresh_breadth_history(client,through='2026-11-04',output=folder,now=NOW)
    assert report['status'] == 'complete' and report['completed_days'] == 38
    loaded = load_breadth_history(folder,NOW)
    assert loaded['observed_days'] == 38 and loaded['complete_market_history'] is False
    current = json.loads((folder/'current.json').read_text())
    day = json.loads((folder/'days'/f"{current['daily_snapshots'][DAY]}.json").read_text())
    raw = tmp_path/'public_breadth/responses'/f"{day['responses'][-1]['response_sha256']}.xlsx"
    raw.write_bytes(b'changed')
    repair = ExportClient(tmp_path/'public_breadth')
    fixed = refresh_breadth_history(repair,through='2026-11-04',output=folder,now=NOW,repair=True)
    assert fixed['status'] == 'complete' and fixed['reused_days'] == 37 and repair.calls == [DAY]


@pytest.mark.parametrize('change',['filtered_export','wrong_tail_page','unbound_kind','normalized_disagrees'])
def test_export_repair_rechecks_binding_and_normalization_against_original_bytes(tmp_path,change):
    folder=tmp_path/'history';client=ExportClient(tmp_path/'public_breadth')
    refresh_breadth_history(client,through='2026-11-04',output=folder,now=NOW)
    pointer=folder/'staging'/f'{DAY}.json';key=json.loads(pointer.read_text())['content_digest']
    day=json.loads((folder/'days'/f'{key}.json').read_text())
    if change=='filtered_export':day['responses'][-1]['params']['txtDMorJC']='000001'
    elif change=='wrong_tail_page':day['responses'][1]['params']['PAGENO']=1
    elif change=='unbound_kind':day['responses'][-1]['kind']='other'
    else:day['block']['rows'][5]['amount']=12345
    day.pop('content_digest');key=digest(day);day['content_digest']=key
    (folder/'days'/f'{key}.json').write_text(json.dumps(day));pointer.write_text(json.dumps({'content_digest':key}))
    repair=ExportClient(tmp_path/'public_breadth')
    fixed=refresh_breadth_history(repair,through='2026-11-04',output=folder,now=NOW,repair=True)
    assert fixed['status']=='complete' and fixed['reused_days']==37 and repair.calls==[DAY]
