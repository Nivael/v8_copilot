"""Bounded, cached extraction of official CNINFO announcement PDFs."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from dataclasses import asdict, dataclass, replace
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader

from announcement_inventory import OfficialAnnouncement
from settings import ANNOUNCEMENT_BODY_CACHE_DIR


MAX_PDF_BYTES = 12 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT_CHARS = 240_000
_CNINFO_PATH = re.compile(
    r"^/finalpage/(?P<date>20\d{2}-\d{2}-\d{2})/(?P<id>[0-9]+)\.PDF$",
    re.IGNORECASE,
)
_OFFICIAL_ANNOUNCEMENT_NUMBER = re.compile(
    r"公告\s*编号\s*[：:]\s*((?:临\s*)?20\d{2}\s*[-－—–]\s*[A-Za-z0-9]+)"
)


class AnnouncementBodyError(RuntimeError):
    """The official body could not be fetched or validated."""


@dataclass(frozen=True)
class AnnouncementBody:
    announcement_id: str
    announcement_date: str
    source_url: str
    page_count: int
    text: str
    source: str = "downloaded_pdf"


def _validated_url(record: OfficialAnnouncement) -> str:
    if not record.url:
        raise AnnouncementBodyError("公告没有原文链接")
    parsed = urlparse(record.url)
    if parsed.hostname != "static.cninfo.com.cn":
        raise AnnouncementBodyError("公告正文只允许从 CNINFO 静态域名读取")
    match = _CNINFO_PATH.match(parsed.path)
    if not match:
        raise AnnouncementBodyError("公告原文链接格式不符合 CNINFO PDF 规则")
    if match.group("id") != record.announcement_id:
        raise AnnouncementBodyError("巨潮公告 ID 与 PDF 链接不一致")
    return parsed._replace(scheme="https", netloc="static.cninfo.com.cn").geturl()


def _cache_path(record: OfficialAnnouncement, cache_dir: Path) -> Path:
    if not re.fullmatch(r"[0-9]+", record.announcement_id):
        raise AnnouncementBodyError("巨潮公告 ID 非法")
    return cache_dir / record.announcement_id[:4] / f"{record.announcement_id}.json"


def _read_cache(
    path: Path,
    record: OfficialAnnouncement,
    source_url: str,
) -> AnnouncementBody | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        body = AnnouncementBody(**payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AnnouncementBodyError(f"公告正文缓存损坏: {path.name}") from exc
    if body.announcement_id != record.announcement_id:
        raise AnnouncementBodyError("公告正文缓存编号不匹配")
    if body.announcement_date != record.announcement_date:
        raise AnnouncementBodyError("公告正文缓存日期不匹配")
    if body.source_url != source_url:
        raise AnnouncementBodyError("公告正文缓存来源链接不匹配")
    if body.page_count < 0 or body.page_count > MAX_PAGES:
        raise AnnouncementBodyError("公告正文缓存页数非法")
    if not body.text.strip() or len(body.text) > MAX_TEXT_CHARS:
        raise AnnouncementBodyError("公告正文缓存文本非法")
    return replace(body, source="cache")


def _download(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "ST-Research-Copilot/8 local-research"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if urlparse(response.geturl()).hostname != "static.cninfo.com.cn":
                raise AnnouncementBodyError("公告 PDF 重定向离开 CNINFO 静态域名")
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                raise AnnouncementBodyError("公告原文响应不是 PDF")
            data = response.read(MAX_PDF_BYTES + 1)
    except AnnouncementBodyError:
        raise
    except Exception as exc:
        raise AnnouncementBodyError(f"公告 PDF 下载失败: {type(exc).__name__}") from exc
    if len(data) > MAX_PDF_BYTES:
        raise AnnouncementBodyError("公告 PDF 超过本地提取上限")
    if not data.startswith(b"%PDF"):
        raise AnnouncementBodyError("公告原文缺少 PDF 文件头")
    return data


def _extract(record: OfficialAnnouncement, url: str, data: bytes) -> AnnouncementBody:
    try:
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > MAX_PAGES:
            raise AnnouncementBodyError("公告 PDF 页数超过本地提取上限")
        chunks = [(page.extract_text() or "") for page in reader.pages]
    except AnnouncementBodyError:
        raise
    except Exception as exc:
        raise AnnouncementBodyError(f"公告 PDF 文本提取失败: {type(exc).__name__}") from exc
    text = re.sub(r"[ \t]+", " ", "\n".join(chunks))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise AnnouncementBodyError("公告 PDF 没有可提取文本")
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
    return AnnouncementBody(
        announcement_id=record.announcement_id,
        announcement_date=record.announcement_date,
        source_url=url,
        page_count=len(reader.pages),
        text=text,
        source="downloaded_pdf",
    )


def _write_cache(path: Path, body: AnnouncementBody) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(body), ensure_ascii=False, indent=2)
    try:
        fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(payload)
        os.replace(temp_name, path)
    except OSError as exc:
        raise AnnouncementBodyError(f"公告正文缓存写入失败: {path.name}") from exc


def load_announcement_body(
    record: OfficialAnnouncement,
    *,
    cache_dir: Path = ANNOUNCEMENT_BODY_CACHE_DIR,
    source_db: Path | None = None,
    allow_network: bool = True,
    timeout_seconds: float = 15.0,
) -> AnnouncementBody:
    """Return a validated body from embedded text, cache, or CNINFO PDF."""
    if record.body_text:
        return AnnouncementBody(
            announcement_id=record.announcement_id,
            announcement_date=record.announcement_date,
            source_url=record.url or "",
            page_count=0,
            text=record.body_text,
            source="embedded_refresh",
        )
    if source_db is not None:
        try:
            with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as connection:
                row = connection.execute(
                    "select body_text from company_announcements where announcement_id=? limit 1",
                    (record.announcement_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise AnnouncementBodyError("公告正文只读查询失败") from exc
        if row and isinstance(row[0], str) and row[0].strip():
            return AnnouncementBody(
                announcement_id=record.announcement_id,
                announcement_date=record.announcement_date,
                source_url=record.url or "",
                page_count=0,
                text=row[0].strip(),
                source="embedded_sqlite",
            )
    url = _validated_url(record)
    path = _cache_path(record, cache_dir)
    cached = _read_cache(path, record, url)
    if cached is not None:
        return cached
    if not allow_network:
        raise AnnouncementBodyError("公告正文尚未进入本地缓存")
    body = _extract(record, url, _download(url, timeout_seconds))
    _write_cache(path, body)
    return body


def relevant_excerpt(text: str, question: str, *, max_sentences: int = 8) -> list[str]:
    """Select source-order evidence snippets; this is retrieval, not interpretation."""
    # PDF extraction often inserts a newline at every visual line. Join those
    # wraps before sentence selection so the LLM receives complete source facts.
    normalized = re.sub(r"(?<![。！？；：])\n(?!\n)", "", text)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    sentences = [
        item.strip(" \n")
        for item in re.split(r"(?<=[。！？；])|\n+", normalized)
        if len(item.strip()) >= 12
    ]
    question_terms = set(re.findall(r"[\u4e00-\u9fff]{2,8}", question))
    priority_terms = {
        "申请人", "被申请人", "债权人", "法院", "受理", "尚未受理", "预重整",
        "重整", "主要内容", "基本情况", "申请理由", "风险", "影响", "债权", "金额", "期限",
    }
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        score = sum(3 for term in priority_terms if term in sentence)
        score += sum(2 for term in question_terms if term in sentence)
        if len(sentence) > 600:
            score -= 2
        if score > 0:
            scored.append((score, index, sentence[:900]))
    chosen = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda item: item[1])
    return [sentence for _, _, sentence in chosen]


def official_announcement_number(text: str) -> str:
    """Extract the issuer's formal announcement number, not CNINFO's document ID."""
    match = _OFFICIAL_ANNOUNCEMENT_NUMBER.search(text)
    if match is None:
        return ""
    value = re.sub(r"\s+", "", match.group(1))
    return re.sub(r"[－—–]", "-", value)
