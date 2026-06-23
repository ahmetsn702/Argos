from typing import Dict, Any, List
from app.services.watchlist.thresholds import DEFAULT_THRESHOLDS


class DiffEngine:
    """
    Engine responsible for comparing two target snapshots and identifying key changes.
    """

    def __init__(self, thresholds: Dict[str, Any] = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    def compare(self, old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares two target snapshots.
        Detects: confidence_delta, new_platform, new_breach, temporal_anomaly.
        Returns: {"changes": [...], "severity": "low|medium|high"}
        """
        if old is None:
            old = {}
        if new is None:
            new = {}

        # Safely extract the inner data payloads if the outer snapshot dictionaries are provided
        old_data = old.get("data", old) if isinstance(old, dict) else {}
        new_data = new.get("data", new) if isinstance(new, dict) else {}

        changes = []

        # 1. Confidence Delta
        old_conf = old_data.get("confidence")
        new_conf = new_data.get("confidence")
        if old_conf is not None and new_conf is not None:
            try:
                delta = abs(float(new_conf) - float(old_conf))
                threshold = self.thresholds.get("confidence_delta_threshold", 0.15)
                if delta >= threshold:
                    changes.append({
                        "type": "confidence_delta",
                        "message": f"Confidence delta of {delta:.4f} exceeds threshold {threshold}",
                        "severity": self.thresholds.get("confidence_delta_severity", "low")
                    })
            except (ValueError, TypeError):
                pass

        # 2. New Platform
        old_platforms = old_data.get("platforms", [])
        new_platforms = new_data.get("platforms", [])
        if isinstance(old_platforms, list) and isinstance(new_platforms, list):
            added_platforms = [p for p in new_platforms if p not in old_platforms]
            if added_platforms:
                changes.append({
                    "type": "new_platform",
                    "message": f"New platform(s) detected: {', '.join(map(str, added_platforms))}",
                    "severity": self.thresholds.get("new_platform_severity", "medium")
                })

        # 3. New Breach
        old_breaches = old_data.get("breaches", [])
        new_breaches = new_data.get("breaches", [])
        if isinstance(old_breaches, list) and isinstance(new_breaches, list):
            added_breaches = [b for b in new_breaches if b not in old_breaches]
            if added_breaches:
                changes.append({
                    "type": "new_breach",
                    "message": f"New breach(es) detected: {', '.join(map(str, added_breaches))}",
                    "severity": self.thresholds.get("new_breach_severity", "high")
                })

        # 4. Temporal Anomaly
        old_ta = old_data.get("temporal_anomaly", False)
        new_ta = new_data.get("temporal_anomaly", False)
        old_tas = old_data.get("temporal_anomalies", [])
        new_tas = new_data.get("temporal_anomalies", [])

        has_ta_change = False
        if new_ta and not old_ta:
            has_ta_change = True
        elif isinstance(old_tas, list) and isinstance(new_tas, list):
            added_tas = [ta for ta in new_tas if ta not in old_tas]
            if added_tas:
                has_ta_change = True

        if has_ta_change:
            changes.append({
                "type": "temporal_anomaly",
                "message": "New temporal anomaly detected",
                "severity": self.thresholds.get("temporal_anomaly_severity", "high")
            })

        # Determine overall severity based on the highest rank among detected changes
        severity_rank = {"low": 1, "medium": 2, "high": 3}
        highest_severity = "low"
        for change in changes:
            c_sev = change.get("severity", "low")
            if severity_rank.get(c_sev, 1) > severity_rank.get(highest_severity, 1):
                highest_severity = c_sev

        return {
            "changes": changes,
            "severity": highest_severity
        }
