"""Interim literal-fact gate; this does not implement general discipline semantics."""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlsplit

TERMS = ("公开谴责", "通报批评", "监管警示", "纪律处分", "处分后", "受罚", "被罚")
OFFICIAL_KINDS = {"official_exchange_or_regulator", "official_announcement"}
PRIMARY_DOMAINS = ("sse.com.cn", "szse.cn", "csrc.gov.cn", "cninfo.com.cn")


def has_discipline_terms(text: str) -> bool:
    return any(term in re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)) for term in TERMS)


def _clauses(text: str) -> list[str]:
    # Keep commas, negations, names and date separators. Substring matching could
    # turn “并未受到公开谴责” into support for “受到公开谴责”.
    return [value for part in re.split(r"[。；;\n]", unicodedata.normalize("NFKC", text))
            if (value := re.sub(r"\s+", "", part).strip("。；;."))]


def _whole(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).strip("。；;.")


def _official_fact(summary: str) -> str | None:
    try:
        raw = json.loads(summary)
        if not isinstance(raw, dict) or not isinstance(raw.get("source_url"), str): return None
        parsed = urlsplit(raw["source_url"])
        host = parsed.hostname or ""
        if (raw["source_kind"] not in OFFICIAL_KINDS or parsed.scheme != "https"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not any(host == domain or host.endswith("." + domain) for domain in PRIMARY_DOMAINS)
            or not isinstance(raw["fact"], str)):
            return None
        return raw["fact"]
    except (ValueError, KeyError, TypeError):
        return None


def unsupported_discipline_clauses(text: str, summaries: list[str], *, title: bool = False) -> list[str]:
    """Require each clause to equal a cited primary fact, rather than pool its words.

    The pack author must still verify the extracted facts against original
    documents. This gate neither extracts decision roles nor infers chronology.
    Method certification intentionally remains unverified.
    """
    facts = [fact for summary in summaries if (fact := _official_fact(summary)) is not None]
    if title and text.strip() in (*TERMS, "处分类型", "处分对象", "事件时点"):
        return []  # A bare heading is a label, not an attribution.
    if not has_discipline_terms(text) and (title or not any(has_discipline_terms(fact) for fact in facts)):
        return []
    if _whole(text) in {_whole(fact) for fact in facts}:
        return []
    # A later sentence may qualify the first (“拟作出…尚未生效”). Retain it.
    allowed = {clauses[0] for fact in facts if len(clauses := _clauses(fact)) == 1}
    return [clause for clause in _clauses(text) if clause not in allowed]
