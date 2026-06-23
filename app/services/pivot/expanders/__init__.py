# app/services/pivot/expanders/__init__.py
"""Per-FindingType pivot expanders.

Each expander module exposes async functions with the signature
``async def expand_via_X(value: str) -> List[ConfidenceFinding]``
suitable for registration in ``strategy_map.STRATEGY_MAP``.
"""
