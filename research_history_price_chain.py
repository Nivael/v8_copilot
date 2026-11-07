"""Validate mixed immutable price extensions without changing legacy processors."""
from canonical_json import digest
from research_history_bse import EXTENSION_KEY,SHA,validate_extension as validate_bse

KINDS={'calendar_extension','subject_extension',EXTENSION_KEY}


def validate_price_packet(packet,*,root=None,base=None,seen=None):
    from research_history_prefix import validate_price_packet as legacy
    from research_history_prices import bound
    if digest({k:v for k,v in packet.items() if k!='content_digest'})!=packet['content_digest']:raise ValueError('price packet content changed')
    if any(k.endswith('_extension') and k not in KINDS for k in packet):raise ValueError('unregistered price extension')
    kinds=[k for k in KINDS if packet.get(k) is not None]
    if not kinds:return legacy(packet,root=root,base=base)
    if len(kinds)!=1:raise ValueError('one extension per price packet is required')
    kind=kinds[0];entry=packet[kind];key=entry['base_price_digest'];seen=set() if seen is None else set(seen)
    if not SHA.fullmatch(key) or key in seen or len(seen)>=32:raise ValueError('invalid mixed price ancestry')
    seen.add(key)
    if base is None:
        if root is None:raise ValueError('mixed price ancestry requires its retained root')
        base=bound(root/'price_paths/history'/(key+'.json'))
    if base['content_digest']!=key:raise ValueError('price parent identity changed')
    validate_price_packet(base,root=root,seen=seen)
    if kind==EXTENSION_KEY:
        if root is None:raise ValueError('BSE source reconstruction needs its retained root')
        validate_bse(packet,base=base,root=root)
    else:legacy(packet,root=root,base=base)
