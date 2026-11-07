"""Read the exchange's complete XLSX export, controlled by its HTTPS JSON boundary pages."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from html import unescape
from io import BytesIO
import json
import math
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from canonical_json import digest
from data_refresh import atomic_write_json
from market_breadth import SOURCES
from market_breadth_refresh import PublicBreadthClient, parse_szse

# The exchange export currently answers on this official HTTP endpoint; the two
# independent JSON controls use the existing HTTPS report endpoint. Retain both.
EXPORT_URL = "http://www.szse.cn/api/report/ShowReport"
EXPORT_KIND = "szse_complete_xlsx"
HEADERS = ["交易日期", "证券代码", "证券简称", "前收", "开盘", "最高", "最低", "今收", "涨跌幅（%）", "成交量(万股)", "成交金额(万元)", "市盈率"]
FIELDS = ["jyrq", "zqdm", "zqjc", "qss", "ks", "zg", "zd", "ss", "sdf", "cjgs", "cjje", "syl"]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def export_params(day):
    return {"SHOWTYPE": "xlsx", "CATALOGID": SOURCES["SZSE"]["catalog"], "txtBeginDate": day, "txtEndDate": day}


def _xml(body):
    if b"<!DOCTYPE" in body or b"<!ENTITY" in body: raise ValueError("unsupported workbook XML")
    return ET.fromstring(body)


def export_rows(body: bytes) -> list[dict]:
    """Strict read-only extraction; dates and six-digit identifiers remain text."""
    try:
        with ZipFile(BytesIO(body)) as archive:
            entries = archive.infolist()
            if (len(entries) > 30 or len({item.filename for item in entries}) != len(entries)
                or sum(item.file_size for item in entries) > 12_000_000
                or any(item.flag_bits & 1 for item in entries)):
                raise ValueError("unsupported workbook size or contents")
            book = _xml(archive.read("xl/workbook.xml"))
            if len(book.findall("m:sheets/m:sheet", NS)) != 1: raise ValueError("expected one export sheet")
            strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                strings = ["".join(cell.itertext()) for cell in _xml(archive.read("xl/sharedStrings.xml")).findall("m:si", NS)]
            rows = _xml(archive.read("xl/worksheets/sheet1.xml")).findall("m:sheetData/m:row", NS)
            if not 2 <= len(rows) <= 10_001: raise ValueError("unexpected export row count")
            values = []
            for index, row in enumerate(rows, 1):
                if row.get("r") != str(index) or len(row) != len(HEADERS): raise ValueError("nonrectangular export")
                data = []
                for column, cell in enumerate(row):
                    if (cell.get("r") != f"{chr(65 + column)}{index}" or cell.find("m:f", NS) is not None
                        or cell.get("t", "n") not in ("inlineStr", "s", "n")):
                        raise ValueError("unexpected export cell or formula")
                    if cell.get("t") == "inlineStr": value = "".join(cell.find("m:is", NS).itertext())
                    elif cell.get("t") == "s": value = strings[int(cell.findtext("m:v", namespaces=NS))]
                    else: value = cell.findtext("m:v", default="", namespaces=NS)
                    data.append(value)
                values.append(data)
            if values[0] != HEADERS: raise ValueError("export columns or units changed")
            return [dict(zip(FIELDS, row, strict=True)) for row in values[1:]]
    except (BadZipFile, KeyError, IndexError, AttributeError, ET.ParseError, RuntimeError) as exc:
        raise ValueError("unreadable exchange workbook") from exc


def parse_export(body, head, tail, day):
    rows = export_rows(body)
    if not isinstance(head, list) or len(head) != 1 or not isinstance(tail, list) or len(tail) != 1:
        raise ValueError("unexpected boundary report blocks")
    meta = head[0]["metadata"]
    count, size, pages = meta["recordcount"], meta["pagesize"], meta["pagecount"]
    if (type(count) is not int or not 0 < count < 10_000 or size != 10 or pages != math.ceil(count / size)
        or len(rows) != count or meta["pageno"] != 1 or tail[0]["metadata"] != {**meta, "pageno": pages}):
        raise ValueError("export total or boundary metadata mismatch")
    # Compare all columns used by the breadth calculation, preserving source text
    # and published decimal precision; unrelated OHLC/P-E fields are not metrics.
    used = ("jyrq", "zqdm", "zqjc", "qss", "ss", "sdf", "cjgs", "cjje")
    def projected(items): return [{key: unescape(str(row[key])).replace("\u00a0", " ").strip() for key in used} for row in items]
    if (projected(rows[:size]) != projected(head[0]["data"])
        or projected(rows[(pages - 1) * size:]) != projected(tail[0]["data"])):
        raise ValueError("XLSX disagrees with HTTPS JSON boundary rows")
    # Reuse the existing date, identity, units, preferred-share, duplicates and
    # return/price checks. These are adapter-created pages, never archived JSON.
    adapted = [[{"metadata": {**deepcopy(meta), "pageno": page}, "data": rows[(page - 1) * size:page * size]}]
               for page in range(1, pages + 1)]
    return parse_szse(adapted, day)


class HistoricalExportClient(PublicBreadthClient):
    def _export(self, day):
        params = export_params(day)
        cache_path = self.output / "cache" / f"{digest({'url': EXPORT_URL, 'params': params})}.json"
        if self.repair:
            try:
                ref = json.loads(cache_path.read_text())
                stamp = datetime.fromisoformat(ref["observed_at"])
                key = ref["response_sha256"]
                if (ref["url"] != EXPORT_URL or ref["params"] != params or ref["kind"] != EXPORT_KIND
                    or stamp.tzinfo is None or stamp > datetime.now(timezone.utc) or not re.fullmatch(r"[a-f0-9]{64}", key)):
                    raise ValueError("export cache mismatch")
                body = (self.output / "responses" / f"{key}.xlsx").read_bytes()
                if hashlib.sha256(body).hexdigest() != key: raise ValueError("export bytes changed")
                return body, ref
            except (OSError, ValueError, KeyError, TypeError): pass
        request = Request(EXPORT_URL + "?" + urlencode(params), headers={"User-Agent": "Mozilla/5.0", "Referer": SOURCES["SZSE"]["url"]})
        for attempt in range(3):
            try:
                with urlopen(request, timeout=25) as response:
                    body = response.read(2_000_001)
                    length = response.headers.get("Content-Length")
                    if response.url != request.full_url: raise ValueError("unexpected export redirect")
                if not body.startswith(b"PK") or len(body) > 2_000_000 or length is not None and len(body) != int(length):
                    raise ValueError("incomplete or oversized workbook")
                break
            except (OSError, TimeoutError):
                if attempt == 2: raise
                time.sleep(2 * (attempt + 1))
        key = hashlib.sha256(body).hexdigest()
        target = self.output / "responses" / f"{key}.xlsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        ref = {"kind": EXPORT_KIND, "venue": "SZSE", "url": EXPORT_URL, "params": params,
               "response_sha256": key, "observed_at": datetime.now(timezone.utc).isoformat(), "bytes": len(body)}
        atomic_write_json(cache_path, ref)
        return body, ref

    def get_venue(self, venue, through):
        if venue != "SZSE": raise ValueError("history export supports SZSE only")
        params = {"SHOWTYPE": "JSON", "CATALOGID": SOURCES["SZSE"]["catalog"], "TABKEY": "tab1",
                  "txtBeginDate": through, "txtEndDate": through}
        head, first = self.request("SZSE", {**params, "PAGENO": 1}, cache=True)
        count = head[0]["metadata"]["pagecount"]
        if type(count) is not int or not 1 <= count <= 700: raise ValueError("unexpected history scope")
        tail, last = self.request("SZSE", {**params, "PAGENO": count}, cache=True)
        body, export = self._export(through)
        return parse_export(body, head, tail, through), [first, last, export]
