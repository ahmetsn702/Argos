import logging
import re
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

class PlaybookParser:
    async def parse(self, nl_text: str) -> dict:
        api_key = settings.GOOGLE_API_KEY
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = (
                    "You are a Playbook Parser for the ARGOS OSINT system.\n"
                    "Convert the following natural language instruction to a structured Playbook JSON.\n"
                    f"Instruction: {nl_text}\n\n"
                    "The output MUST be a valid JSON matching this schema:\n"
                    "{\n"
                    "  \"name\": \"Name of the playbook\",\n"
                    "  \"trigger\": \"one of [darkweb_new_breach, confidence_delta, new_platform, temporal_anomaly, cron]\",\n"
                    "  \"action\": \"one of [confidence_build, pivot_run, archive, alert, notify_webhook]\",\n"
                    "  \"params\": { ... arbitrary key-value pairs representing parameters if any ... },\n"
                    "  \"raw_input\": \"original natural language instruction\"\n"
                    "}\n"
                    "Only return the raw JSON object, no markdown, no backticks. Ensure valid JSON format."
                )
                response = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=[prompt],
                )
                text = response.text.strip()
                # Strip markdown code blocks if present
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                
                parsed = json.loads(text)
                
                # Check for required fields and default if missing
                if "name" not in parsed:
                    parsed["name"] = "Parsed Playbook"
                if "trigger" not in parsed:
                    parsed["trigger"] = "cron"
                if "action" not in parsed:
                    parsed["action"] = "alert"
                if "params" not in parsed:
                    parsed["params"] = {}
                parsed["raw_input"] = nl_text
                
                return parsed
            except Exception as e:
                logger.warning(f"Failed parsing playbook with Gemini: {e}")
                # Fall back to regex parser
        
        return self._fallback_parse(nl_text)

    def _fallback_parse(self, nl_text: str) -> dict:
        text = nl_text.lower()
        
        # Determine Trigger
        trigger = "cron"
        if "darkweb" in text or "breach" in text:
            trigger = "darkweb_new_breach"
        elif "delta" in text or "deviation" in text or "confidence change" in text:
            trigger = "confidence_delta"
        elif "platform" in text or "new source" in text:
            trigger = "new_platform"
        elif "temporal" in text or "anomaly" in text or "time pattern" in text:
            trigger = "temporal_anomaly"
        elif "cron" in text or "schedule" in text or "every" in text or "hourly" in text or "daily" in text:
            trigger = "cron"

        # Determine Action
        action = "alert"
        if "confidence_build" in text or "build confidence" in text or "improve confidence" in text:
            action = "confidence_build"
        elif "pivot" in text or "pivot_run" in text or "execute pivot" in text:
            action = "pivot_run"
        elif "archive" in text or "store" in text:
            action = "archive"
        elif "notify" in text or "webhook" in text:
            action = "notify_webhook"
        elif "alert" in text or "raise alert" in text:
            action = "alert"

        # Determine Name
        name_match = re.search(r'(?:name|title):\s*([^.\n]+)', nl_text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            name = f"NL Playbook: {trigger} to {action}"

        # Parameter extraction
        params = {}
        url_match = re.search(r'(https?://[^\s\)\"]+)', nl_text)
        if url_match:
            params["url"] = url_match.group(1)
            
        threshold_match = re.search(r'(?:threshold|limit)\s*(?:of|is)?\s*([\d\.]+)', nl_text, re.IGNORECASE)
        if threshold_match:
            try:
                params["threshold"] = float(threshold_match.group(1))
            except ValueError:
                pass

        return {
            "name": name,
            "trigger": trigger,
            "action": action,
            "params": params,
            "raw_input": nl_text
        }
