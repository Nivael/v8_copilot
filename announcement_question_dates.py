"""Calendar-safe date filters; an unqualified month/day never supplies its own year."""
from dataclasses import dataclass
from datetime import date
import re
import unicodedata


@dataclass(frozen=True)
class AnnouncementDateScope:
    full_dates: tuple[str, ...]
    month_days: tuple[str, ...]
    invalid_dates: tuple[str, ...]

    @property
    def constrained(self):
        return bool(self.full_dates or self.month_days or self.invalid_dates)

    @property
    def unresolved(self):
        return bool(self.month_days or self.invalid_dates)

    @property
    def label(self):
        if self.invalid_dates:
            return '日期无效'
        if self.month_days:
            return '缺少年份'
        return '完整日期' if self.full_dates else '未限定'

    @property
    def display(self):
        return ', '.join((*self.full_dates, *(f'{int(m[1:3])}月{int(m[4:6])}日（年份待确认）' for m in self.month_days), *self.invalid_dates)) or '未限定'


def announcement_date_scope(question: str) -> AnnouncementDateScope:
    text=''.join(unicodedata.normalize('NFKC', question).split())
    full=set();partial=set();invalid=set();spans=[]
    for match in re.finditer(r'(?<!\d)(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})(?:日|号)?(?!\d)', text):
        spans.append(match.span())
        try:
            full.add(date(*(int(v) for v in match.groups())).isoformat())
        except ValueError:
            invalid.add(match.group())
    for match in re.finditer(r'(?<!\d)(\d{1,2})月(\d{1,2})(?:日|号)?(?!\d)', text):
        if any(start<=match.start()<end for start,end in spans):
            continue
        month,day=(int(v) for v in match.groups())
        try:
            # Leap-day validity cannot resolve an unknown year.
            date(2000,month,day)
            partial.add(f'-{month:02d}-{day:02d}')
        except ValueError:
            invalid.add(match.group())
    return AnnouncementDateScope(tuple(sorted(full)),tuple(sorted(partial)),tuple(sorted(invalid)))
