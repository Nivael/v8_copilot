from __future__ import annotations

import sqlite3

import pytest

from announcement_body import AnnouncementBodyError, load_announcement_body
from announcement_inventory import OfficialAnnouncement


def _record(url: str = "https://static.cninfo.com.cn/finalpage/2026-07-08/1225415810.PDF") -> OfficialAnnouncement:
    return OfficialAnnouncement(
        announcement_id="1225415810",
        announcement_date="2026-07-08",
        title="提示性公告",
        url=url,
        source="fixture",
        body_available=True,
    )


def test_reads_embedded_sqlite_body_without_network(tmp_path) -> None:
    database = tmp_path / "announcements.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "create table company_announcements (announcement_id text primary key, body_text text)"
        )
        connection.execute(
            "insert into company_announcements values (?, ?)",
            ("1225415810", "法院尚未裁定受理预重整申请。"),
        )

    body = load_announcement_body(
        _record(),
        source_db=database,
        cache_dir=tmp_path / "cache",
        allow_network=False,
    )

    assert body.text == "法院尚未裁定受理预重整申请。"
    assert not (tmp_path / "cache").exists()


def test_rejects_non_cninfo_url_before_network(tmp_path) -> None:
    with pytest.raises(AnnouncementBodyError, match="CNINFO"):
        load_announcement_body(
            _record("https://example.invalid/1225415810.PDF"),
            cache_dir=tmp_path,
            allow_network=False,
        )


def test_corrupt_cache_fails_loudly(tmp_path) -> None:
    path = tmp_path / "1225" / "1225415810.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(AnnouncementBodyError, match="缓存损坏"):
        load_announcement_body(_record(), cache_dir=tmp_path, allow_network=False)
