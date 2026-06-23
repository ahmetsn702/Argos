"""LLM-based OSINT analyst: takes raw module outputs and produces a Turkish analysis report."""

import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sen bir OSINT analisti ve siber güvenlik uzmanısın. "
    "Aşağıdaki OSINT verilerini analiz et ve Türkçe olarak raporla. "
    "Sadece verilen verilere dayan, tahmin yapma. "
    "JSON formatında yanıt ver, markdown kullanma."
)

RESPONSE_SCHEMA = """{
  "summary": "2-3 cümle genel özet",
  "risk_level": "low|medium|high|critical",
  "key_findings": ["bulgu1", "bulgu2", ...],
  "recommendations": ["öneri1", "öneri2", ...]
}"""

CONFIDENCE_DIRECTIVE = """
Güven Skoru Direktifi:
- Yüksek güvenli bulgulara (score > 0.8) öncelik ver
- Çelişen bulguları (contradicted) açıkça raporla
- Tek kaynaklı bulguları 'doğrulama gerekiyor' olarak işaretle
- Güven skoru düşük bilgileri şüpheyle değerlendir
"""


class OsintAnalyst:
    MODEL = "gemini-3.5-flash"

    async def analyze(self, osint_data: dict, context: str = None,
                      confidence_summary: dict = None,
                      confidence_verbose: dict = None) -> dict:
        api_key = settings.GOOGLE_API_KEY or ""
        if not api_key:
            return {"error": "api_key_missing"}

        try:
            from google import genai

            client = genai.Client(api_key=api_key)

            user_prompt = f"OSINT Verileri:\n{json.dumps(osint_data, ensure_ascii=False, default=str)[:12000]}"
            if context:
                user_prompt += f"\n\nEk Bağlam: {context}"
            if confidence_verbose is not None:
                user_prompt += "\n\nGüven Grafiği (Detaylı):\n" + json.dumps(confidence_verbose, ensure_ascii=False, default=str)[:5000]
            elif confidence_summary is not None:
                user_prompt += "\n\nGüven Özeti:\n" + json.dumps(confidence_summary, ensure_ascii=False, default=str)[:500]
            user_prompt += f"\n\nYanıtını şu JSON şemasına uygun ver:\n{RESPONSE_SCHEMA}"

            has_confidence = confidence_summary is not None or confidence_verbose is not None
            system = SYSTEM_PROMPT
            if has_confidence:
                system += CONFIDENCE_DIRECTIVE

            response = client.models.generate_content(
                model=self.MODEL,
                contents=[f"{system}\n\n{user_prompt}"],
            )

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result = json.loads(text)
            result["raw_prompt_tokens"] = len(user_prompt)
            result["model"] = self.MODEL
            return result

        except json.JSONDecodeError:
            return {
                "summary": text[:500] if "text" in dir() else "Parse error",
                "risk_level": "medium",
                "key_findings": [],
                "recommendations": [],
                "raw_prompt_tokens": 0,
                "model": self.MODEL,
            }
        except Exception as e:
            logger.warning(f"LLM analysis failed: {type(e).__name__}: {e}")
            return {"error": f"{type(e).__name__}: {e}", "model": self.MODEL}
