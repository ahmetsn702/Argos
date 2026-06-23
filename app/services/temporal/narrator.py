"""LLM-based temporal narrative generator (Gemini, async)."""

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.models.temporal import AnomalyFlag, TemporalNarrative, TimelineEvent

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Sen bir OSINT zaman çizelgesi analistisin. "
    "Verilen olay ve anomali verilerini Türkçe olarak raporla. "
    "Sadece verilen verilere dayan. JSON formatında yanıt ver, markdown kullanma."
)

_SCHEMA = '{"summary":"2-3 cümle özet","risk_level":"low|medium|high|critical","key_observations":["..."]}'


class TemporalNarrator:
    MODEL = "gemini-3.5-flash"

    async def generate(
        self,
        events: List[TimelineEvent],
        anomalies: List[AnomalyFlag],
    ) -> Optional[TemporalNarrative]:
        from app.core.config import settings
        api_key = settings.GOOGLE_API_KEY or ""
        if not api_key:
            return None

        try:
            from google import genai

            event_summary = [
                {"type": e.event_type.value, "timestamp": e.timestamp.isoformat(), "source": e.source}
                for e in events[:50]  # cap to avoid huge prompts
            ]
            anomaly_summary = [
                {"type": a.type.value, "severity": a.severity.value, "explanation": a.explanation}
                for a in anomalies
            ]
            prompt = (
                f"{_SYSTEM}\n\n"
                f"Olaylar ({len(events)} toplam, ilk 50 gösteriliyor):\n"
                f"{json.dumps(event_summary, ensure_ascii=False)}\n\n"
                f"Anomaliler:\n{json.dumps(anomaly_summary, ensure_ascii=False)}\n\n"
                f"Yanıtını şu JSON şemasına uygun ver:\n{_SCHEMA}"
            )

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model=self.MODEL, contents=[prompt])
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(text)
            return TemporalNarrative(
                summary=data.get("summary", ""),
                risk_level=data.get("risk_level", "medium"),
                key_observations=data.get("key_observations", []),
                model=self.MODEL,
                generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        except json.JSONDecodeError:
            logger.warning("TemporalNarrator: JSON parse failed")
            return None
        except Exception as e:
            logger.warning(f"TemporalNarrator: {type(e).__name__}: {e}")
            return None
