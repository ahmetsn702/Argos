class PlaybookValidator:
    def validate(self, playbook: dict) -> tuple[bool, str]:
        if not isinstance(playbook, dict):
            return False, "Playbook must be a dictionary"

        # Check required fields
        required_fields = ["name", "trigger", "action"]
        for field in required_fields:
            if field not in playbook:
                return False, f"Missing required field: '{field}'"
            if not playbook[field]:
                return False, f"Field '{field}' cannot be empty"
            if not isinstance(playbook[field], str):
                return False, f"Field '{field}' must be a string"

        allowed_triggers = [
            "darkweb_new_breach",
            "confidence_delta",
            "new_platform",
            "temporal_anomaly",
            "cron"
        ]
        allowed_actions = [
            "confidence_build",
            "pivot_run",
            "archive",
            "alert",
            "notify_webhook"
        ]

        trigger = playbook["trigger"]
        action = playbook["action"]

        if trigger not in allowed_triggers:
            return False, f"Invalid trigger '{trigger}'. Must be one of: {allowed_triggers}"

        if action not in allowed_actions:
            return False, f"Invalid action '{action}'. Must be one of: {allowed_actions}"

        return True, ""
