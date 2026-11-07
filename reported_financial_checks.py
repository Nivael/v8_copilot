"""Compare supplied, source-bound financial figures without choosing a true vintage.

This checks reported amounts and arithmetic only. It neither extracts a PDF nor
certifies accounting truth, a point-in-time archive, or a corrected statement.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext
import re
from urllib.parse import urlsplit


def _number(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d+)?', value):
        raise ValueError('financial amounts must retain explicit decimal strings')
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError('financial amount must be finite')
    return number


def compare_reported_figures(rows):
    """Keep entity, period, metric and unit boundaries; do not select a version."""
    if not isinstance(rows, list) or not rows:
        raise ValueError('at least one explicitly sourced financial figure is required')
    groups = defaultdict(list); seen = set()
    fields = {'id', 'symbol', 'entity', 'metric', 'unit', 'period_start', 'period_end', 'value', 'source'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError('financial figure fields differ')
        for key in ('id', 'entity', 'metric', 'unit'):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError('financial figure needs explicit identity, meaning and units')
        if row['id'] in seen or not re.fullmatch(r'(?:[03]\d{5}\.SZ|6\d{5}\.SH)', row['symbol']):
            raise ValueError('duplicate figure or unsupported issuer identity')
        seen.add(row['id']); _number(row['value'])
        end = date.fromisoformat(row['period_end'])
        start = date.fromisoformat(row['period_start']) if row['period_start'] is not None else None
        if (end.isoformat() != row['period_end'] or start and (start > end or start.isoformat() != row['period_start'])):
            raise ValueError('financial period is invalid')
        source = row['source']
        if not isinstance(source, dict) or set(source) != {'url', 'sha256', 'page', 'published_on'}:
            raise ValueError('financial figure needs its exact source and physical page')
        url = urlsplit(source['url']); published = date.fromisoformat(source['published_on'])
        if (url.scheme != 'https' or not url.netloc or url.username or url.password
                or not re.fullmatch(r'[a-f0-9]{64}', source['sha256'])
                or type(source['page']) is not int or source['page'] <= 0
                or published.isoformat() != source['published_on'] or published < end):
            raise ValueError('financial source identity, date or page is invalid')
        identity = tuple(row[key] for key in ('symbol', 'entity', 'metric', 'period_start', 'period_end'))
        groups[identity].append(deepcopy(row))
    output = []
    for identity, entries in groups.items():
        units = sorted({r['unit'] for r in entries})
        values = {_number(r['value']) for r in entries}
        status = ('incomparable_units' if len(units) != 1 else 'different_reported_values' if len(values) > 1
                  else 'agreement_in_supplied_figures' if len(entries) > 1 else 'single_reported_figure')
        output.append({**dict(zip(('symbol', 'entity', 'metric', 'period_start', 'period_end'), identity)),
                       'units': units, 'status': status, 'figures': sorted(entries, key=lambda r: r['id']),
                       'selected_value': None})
    output.sort(key=lambda r: (r['symbol'], r['entity'], r['metric'], r['period_start'] or '', r['period_end']))
    return {'version': 'reported_financial_comparison_v1', 'coverage': 'only_supplied_figures',
            'groups': output, 'financial_truth_verified': False, 'point_in_time_vintage_verified': False,
            'silently_corrected': False}


def check_positive_base_change(current, previous, reported_percent, *, tolerance_pp='0.005'):
    """Check a stated percentage against its supplied positive-base amounts.

    A nonpositive denominator has convention-dependent meaning; leave that case
    unresolved rather than silently choosing a profit/loss growth convention.
    """
    a, b, stated, tolerance = map(_number, (current, previous, reported_percent, tolerance_pp))
    if tolerance < 0:
        raise ValueError('percentage tolerance cannot be negative')
    result = {'current': current, 'previous': previous, 'reported_percent': reported_percent,
              'tolerance_pp': tolerance_pp, 'source_values_rewritten': False}
    if b <= 0:
        return {**result, 'status': 'nonpositive_base_not_checked', 'calculated_percent': None,
                'difference_pp': None}
    with localcontext() as context:
        context.prec = 50
        calculated = (a / b - 1) * 100; difference = stated - calculated
    return {**result, 'status': 'arithmetic_agrees' if abs(difference) <= tolerance else 'arithmetic_differs',
            'calculated_percent': str(calculated), 'difference_pp': str(difference)}
