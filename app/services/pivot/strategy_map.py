# app/services/pivot/strategy_map.py
"""Registry: FindingType → list of async expander callables.

Each callable has the signature
    async def fn(value: str) -> List[ConfidenceFinding]
and is treated as a single strategy step; the orchestrator runs all
strategies for a given finding in parallel under a Semaphore.
"""

from typing import Callable, Dict, List

from app.models.confidence import FindingType
from app.services.pivot.expanders import (
    domain_expander,
    email_expander,
    face_expander,
    ip_expander,
    name_expander,
    phone_expander,
    username_expander,
)

STRATEGY_MAP: Dict[FindingType, List[Callable]] = {
    FindingType.EMAIL: [
        email_expander.expand_via_mosint,
        email_expander.expand_via_darkweb,
        email_expander.expand_via_hibp,
        email_expander.expand_to_domain_from_email,
        email_expander.expand_to_username_candidates,
    ],
    FindingType.USERNAME: [
        username_expander.expand_via_bios,
        username_expander.expand_via_variants,
        username_expander.expand_via_social_scan,
    ],
    FindingType.PHONE: [
        phone_expander.expand_via_phone_lookup,
        phone_expander.expand_via_carrier_lookup,
        phone_expander.expand_via_reverse_lookup,
    ],
    FindingType.DOMAIN: [
        domain_expander.expand_via_whois,
        domain_expander.expand_via_dns,
        domain_expander.expand_via_shodan,
    ],
    FindingType.IP: [
        ip_expander.expand_via_ip_geo,
        ip_expander.expand_via_reverse_dns,
        ip_expander.expand_via_asn,
    ],
    FindingType.NAME: [
        name_expander.expand_via_person_aggregator,
        name_expander.expand_via_cse_search,
    ],
    FindingType.LOCATION: [],  # No autonomous expansion strategies yet.
}

# Face expansion is media-bytes oriented and not exposed via a string-arg
# strategy. Tracked separately so coverage tests can ignore it.
FACE_EXPANDERS = [face_expander.expand_via_reverse_image]


def strategies_for(ftype: FindingType) -> List[Callable]:
    return list(STRATEGY_MAP.get(ftype, []))
