"""
OpenCode Bridge — async HTTP client for the OpenCode local API server.
Base URL default: http://localhost:4096
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


class OpenCodeBridge:
    """Async bridge to an OpenCode server instance."""

    def __init__(self, base_url: str = "http://localhost:4096") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ok(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, **data}

    def _err(self, message: str) -> dict[str, Any]:
        return {"ok": False, "error": message}

    # ------------------------------------------------------------------
    # Public async methods
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """
        GET /global/health
        Returns: {"ok": True, "healthy": bool, "version": str}
        """
        try:
            response = await self._client.get("/global/health")
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return self._ok(
                {
                    "healthy": bool(data.get("healthy", False)),
                    "version": str(data.get("version", "")),
                }
            )
        except httpx.HTTPStatusError as exc:
            return self._err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:  # noqa: BLE001
            return self._err(str(exc))

    async def create_session(self, directory: str) -> dict[str, Any]:
        """
        POST /session
        Returns: {"ok": True, "session_id": str}
        """
        try:
            response = await self._client.post(
                "/session",
                json={"directory": directory},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            session_id = data.get("id") or data.get("session_id") or data.get("sessionId", "")
            return self._ok({"session_id": str(session_id)})
        except httpx.HTTPStatusError as exc:
            return self._err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:  # noqa: BLE001
            return self._err(str(exc))

    async def send_prompt(
        self,
        session_id: str,
        text: str,
        provider_id: str = "anthropic",
        model_id: str = "deepseek-v4-pro",
    ) -> dict[str, Any]:
        """
        POST /session/{id}/message
        Waits for a complete response.
        Returns: {"ok": True, "response": str}
        """
        try:
            response = await self._client.post(
                f"/session/{session_id}/message",
                json={
                    "parts": [{"type": "text", "text": text}],
                    "model": {"providerID": provider_id, "modelID": model_id},
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            # Extract text from the first part whose type is "text".
            parts = data.get("parts") or []
            text_part = next((p for p in parts if p.get("type") == "text"), None)
            reply = text_part.get("text", "") if text_part else ""
            return self._ok({"response": str(reply)})
        except httpx.HTTPStatusError as exc:
            return self._err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:  # noqa: BLE001
            return self._err(str(exc))

    async def send_prompt_async(
        self,
        session_id: str,
        text: str,
        provider_id: str = "anthropic",
        model_id: str = "deepseek-v4-pro",
    ) -> dict[str, Any]:
        """
        POST /session/{id}/prompt_async
        Fire-and-forget; server returns 204 on success.
        Returns: {"ok": True} on 204, error dict otherwise.
        """
        try:
            response = await self._client.post(
                f"/session/{session_id}/prompt_async",
                json={
                    "parts": [{"type": "text", "text": text}],
                    "model": {"providerID": provider_id, "modelID": model_id},
                },
            )
            if response.status_code == 204:
                return self._ok({})
            response.raise_for_status()
            # Gracefully handle unexpected 2xx with a body.
            return self._ok({})
        except httpx.HTTPStatusError as exc:
            return self._err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:  # noqa: BLE001
            return self._err(str(exc))

    async def session_status(self) -> dict[str, Any]:
        """
        GET /session/status
        Returns: {"ok": True, "sessions": list}
        """
        try:
            response = await self._client.get("/session/status")
            response.raise_for_status()
            data = response.json()
            # The server may return a list or a dict wrapping the list.
            if isinstance(data, list):
                return self._ok({"sessions": data})
            return self._ok({"sessions": data.get("sessions", data)})
        except httpx.HTTPStatusError as exc:
            return self._err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:  # noqa: BLE001
            return self._err(str(exc))

    # ------------------------------------------------------------------
    # Context-manager support so the client can be used with `async with`
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "OpenCodeBridge":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def close(self) -> None:
        """Explicitly close the underlying HTTP client."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Quick smoke-test — run with:  python opencode_bridge.py
# ---------------------------------------------------------------------------

async def _test_bridge() -> None:
    async with OpenCodeBridge() as bridge:
        result = await bridge.health()
        print("health():", result)


def test_bridge() -> None:
    """Entry point for quick manual testing."""
    asyncio.run(_test_bridge())


if __name__ == "__main__":
    test_bridge()
