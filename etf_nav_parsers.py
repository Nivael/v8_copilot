"""Shared primary NAV parsers; optionally retain exact published decimal text."""
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
import math
import re

class NAVTable(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.tables, self.inputs, self.selected = [], {}, []
        self.table = self.row = self.cell = None
        if not re.search(r"</html>\s*$", text, re.I):
            raise ValueError("incomplete HTML document")
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name"):
            self.inputs[attrs["name"]] = attrs.get("value")
        elif tag == "option" and "selected" in attrs:
            self.selected.append(attrs.get("value"))
        elif tag == "table":
            if self.table is not None:
                raise ValueError("nested NAV tables are unsupported")
            self.table = {"attrs": attrs, "rows": []}
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

    def table_rows(self, *, identifier=None, css_class=None):
        matches = [table["rows"] for table in self.tables
                   if (identifier is None or table["attrs"].get("id") == identifier)
                   and (css_class is None or css_class in table["attrs"].get("class", "").split())]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous NAV table")
        return matches[0]


def normalized(rows: list[tuple[str, object]], code: str, calendar: list[str], *, bounded: bool, exact=False) -> list[dict]:
    result, seen = [], set()
    for day, value in rows:
        if re.fullmatch(r"\d{8}", day):
            day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        day = date.fromisoformat(day).isoformat()
        raw_text = str(value).strip()
        if not re.fullmatch(r"(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?", raw_text):
            raise ValueError("invalid source NAV decimal")
        number = Decimal(raw_text.replace(",", ""))
        if day in seen or isinstance(value, bool) or not number.is_finite() or number <= 0:
            raise ValueError("duplicate date or invalid NAV")
        seen.add(day)
        if day not in calendar:
            if bounded or calendar[0] <= day <= calendar[-1]:
                raise ValueError("NAV date outside requested trading calendar")
            continue
        result.append({"ts_code": code, "nav_date": day, **({"raw_text":raw_text,"source_value":format(number,"f"),
            "fractional_digits":len(raw_text.split(".")[1]) if "." in raw_text else 0} if exact else {"unit_nav":float(number)})})
    return sorted(result, key=lambda row: row["nav_date"])


def parse_chinaamc(text: str, code: str, calendar: list[str], page: int, *, exact=False) -> tuple[list[dict], int]:
    parsed = NAVTable(text)
    if (parsed.inputs.get("fundcode") != code[:6] or parsed.inputs.get("beginDate") != calendar[0]
        or parsed.inputs.get("endDate") != calendar[-1]
        or parsed.table_rows(identifier="hoverBox1") != [["净值日期", "单位净值", "累计净值", "资产净值"]]):
        raise ValueError("wrong ChinaAMC code, dates or NAV columns")
    current = re.findall(r"let\s+currentPage\s*=\s*'(\d+)'", text)
    total = re.findall(r"let\s+totalPage\s*=\s*'(\d+)'", text)
    if set(current) != {str(page)} or len(set(total)) != 1:
        raise ValueError("wrong ChinaAMC page")
    rows = parsed.table_rows(identifier="hoverBox1_1")
    if not rows or any(len(row) != 4 for row in rows):
        raise ValueError("invalid ChinaAMC NAV rows")
    return normalized([(row[0], row[1]) for row in rows], code, calendar, bounded=True, exact=exact), int(total[0])


def parse_jsfund(text: str, code: str, calendar: list[str], *, exact=False) -> list[dict]:
    parsed = NAVTable(text)
    if parsed.inputs.get("FundCode") != code[:6] or code[:6] not in parsed.selected:
        raise ValueError("wrong JSFund instrument")
    rows = parsed.table_rows(css_class="mm_r_table7")
    if not rows or rows[0] != ["日期", "份额净值", "累计净值"] or any(len(row) != 3 for row in rows[1:]):
        raise ValueError("wrong JSFund NAV columns")
    return normalized([(row[0], row[1]) for row in rows[1:]], code, calendar, bounded=False, exact=exact)


def parse_huatai(payload: dict, code: str, calendar: list[str], page: int, *, exact=False) -> tuple[list[dict], int]:
    rows = payload["dataList"]
    if int(payload["currentPage"]) != page or not rows or any(row["fundcode"] != code[:6] for row in rows):
        raise ValueError("wrong Huatai instrument/page")
    return normalized([(row["date"], row["netvalue"]) for row in rows], code, calendar, bounded=True, exact=exact), int(payload["totalPage"])


def parse_nffund(payload: dict, code: str, calendar: list[str], page: int, *, exact=False) -> tuple[list[dict], int, str]:
    if payload["code"] != "ETS-5BP00000":
        raise ValueError("NFFund request failed")
    block = payload["data"]["jjjzList"]
    rows = block["list"]
    # This endpoint ignores date ranges. Walk its dated pages until the lower boundary.
    if (block["pageNum"] != page or block["pageSize"] != 10 or len(rows) != block["size"] or not rows
        or block["pages"] != math.ceil(block["total"] / 10)
        or len(rows) != min(10, block["total"] - (page - 1) * 10)
        or any(row.get("fundCode") not in (None, code[:6]) for row in rows)):
        raise ValueError("invalid NFFund pagination/instrument")
    dates = [date.fromisoformat(row["fdate_ex"]).isoformat() for row in rows]
    if dates != sorted(set(dates), reverse=True) or any(row["fdate"] != day.replace("-", "") for row, day in zip(rows, dates)):
        raise ValueError("invalid NFFund dates/order")
    return normalized([(row["fdate_ex"], row["fundNav"]) for row in rows], code, calendar, bounded=False, exact=exact), block["total"], dates[-1]


def parse_efunds(text: str, code: str, calendar: list[str], *, exact=False) -> list[dict]:
    # Parse the official literal as data; never evaluate downloaded JavaScript.
    match = re.fullmatch(r'\s*mk_' + code[:6] + r'_1y="([\d_;.\-]+)";\s*', text)
    if not match:
        raise ValueError("invalid EFunds literal/instrument")
    records = match[1].split(";")
    if records[0] != "0_1_2_3_4" or records[-1] != "":
        raise ValueError("unexpected EFunds column schema")
    rows = [record.split("_") for record in records[1:-1]]
    if any(len(row) != 5 for row in rows):
        raise ValueError("truncated EFunds records")
    return normalized([(row[0], row[2]) for row in rows], code, calendar, bounded=False, exact=exact)
