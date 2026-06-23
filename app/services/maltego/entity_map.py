from app.models.confidence import FindingType

ENTITY_MAP = {
    "email": "maltego.EmailAddress",
    "phone": "maltego.PhoneNumber",
    "domain": "maltego.Domain",
    "ip": "maltego.IPv4Address",
    "username": "maltego.Alias",
    "person": "maltego.Person",
    "name": "maltego.Person",
    "location": "maltego.Location",
}

def get_entity_type(finding_type: str) -> str:
    if hasattr(finding_type, "value"):
        finding_type = finding_type.value
    if not isinstance(finding_type, str):
        finding_type = str(finding_type)
    normalized = finding_type.lower().strip()
    return ENTITY_MAP.get(normalized, "maltego.Unknown")
