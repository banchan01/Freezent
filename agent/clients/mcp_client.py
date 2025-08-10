# clients/mcp_client.py
from __future__ import annotations

import os
import json
import time
from typing import Any, Callable, Dict, Optional, Tuple


class MCPTransportError(RuntimeError):
    """Low-level transport failure (HTTP, network, timeout, etc.)."""


class MCPProtocolError(RuntimeError):
    """Server responded but payload is malformed or not ok."""


class MCPClient:
    """
    Thin client for invoking MCP tools.

    Subclasses must implement `_transport_call(tool_name, payload) -> Dict[str, Any]`
    returning a JSON-like dict. The returned dict SHOULD follow:
      - Success: {"ok": True, "data": <any>, "version": "YYYY-MM-DD" (optional)}
      - Error:   {"ok": False, "error": {"code": str, "message": str, "details": any}}
    """

    def __init__(self, transport_call: Callable[[str, Dict[str, Any]], Dict[str, Any]]):
        self._transport_call = transport_call

    def invoke(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Invoke a remote/local MCP tool by name.
        Returns the entire response dict for maximum flexibility.
        Raises MCPTransportError / MCPProtocolError on failure.
        """
        try:
            resp = self._transport_call(name, kwargs)
        except Exception as e:
            raise MCPTransportError(f"transport failed for tool '{name}': {e}") from e

        # Minimal validation
        if not isinstance(resp, dict) or "ok" not in resp:
            raise MCPProtocolError(f"invalid MCP response format for '{name}': {resp!r}")

        if resp.get("ok") is True:
            return resp

        # Normalize error
        err = resp.get("error") or {}
        code = err.get("code", "UNKNOWN")
        msg = err.get("message", "unknown error")
        details = err.get("details")
        raise MCPProtocolError(
            f"MCP tool '{name}' returned error [{code}]: {msg} | details={details}"
        )


# Mock transport for dev/test
class MockMCPClient(MCPClient):
    """
    Local mock client that returns deterministic payloads matching the contracts.
    Useful when the real MCP server is not yet available.
    """

    def __init__(self) -> None:
        super().__init__(self._mock_call)

    @staticmethod
    def _ok(data: Any) -> Dict[str, Any]:
        return {"ok": True, "data": data, "version": "2025-08-01"}

    @staticmethod
    def _err(code: str, message: str, details: Any = None) -> Dict[str, Any]:
        return {"ok": False, "error": {"code": code, "message": message, "details": details}}

    def _mock_call(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        # You can tweak these to simulate edge cases / errors
        if name == "ListPaidIn":
            return self._ok({"items": [
                {"rcp_no": "20240101000123", "corp_name": "샘플", "rpt_nm": "제3자배정유상증자"}
            ], "total": 1})

        if name == "ListBizReports":
            return self._ok({"items": [
                {"rcp_no": "20240102000456", "corp_name": "샘플", "rpt_nm": "영업(매출)공시"}
            ], "total": 1})

        if name == "PaidInAnalyze":
            return self._ok({
                "summary": "유상증자 영향은 중간 수준으로 평가됨.",
                "events": [],
                "filings_count": 1,
                "model": "mock",
                "prompt_version": payload.get("prompt_version", "v1"),
            })

        if name == "BizChangeAnalyze":
            return self._ok({
                "summary": "최근 영업 실적은 안정적이며 변화는 제한적.",
                "events": [],
                "filings_count": 1,
                "model": "mock",
                "prompt_version": payload.get("prompt_version", "v1"),
            })

        return self._err("UNKNOWN_TOOL", f"unknown tool '{name}'")


# HTTP transport (real MCP)
class HttpMCPClient(MCPClient):
    """
    HTTP-based MCP client.
    Expects a server exposing POST /tools/{tool_name} that accepts a JSON body (kwargs).
    """

    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        timeout_sec: float = 30.0,
        retries: int = 2,
        backoff: float = 0.3,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = api_token
        self._timeout = timeout_sec
        self._retries = max(0, retries)
        self._backoff = max(0.0, backoff)

        # Import here to avoid hard dependency when using Mock
        import requests  # type: ignore
        self._requests = requests
        self._session = requests.Session()

        super().__init__(self._http_call)

    def _request(self, method: str, path: str, json_body: Dict[str, Any]) -> Tuple[int, str]:
        url = f"{self._base}{path}"
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        headers["Content-Type"] = "application/json"

        # Simple retry with backoff
        last_exc: Optional[Exception] = None
        for attempt in range(self._retries + 1):
            try:
                resp = self._session.request(
                    method=method.upper(),
                    url=url,
                    json=json_body,
                    headers=headers,
                    timeout=self._timeout,
                )
                return resp.status_code, resp.text
            except Exception as e:
                last_exc = e
                if attempt < self._retries:
                    time.sleep(self._backoff * (2 ** attempt))
                else:
                    raise MCPTransportError(f"HTTP request failed: {e}") from e
        # Should not reach here
        raise MCPTransportError(f"HTTP request failed: {last_exc}")

    def _http_call(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        status, text = self._request("POST", f"/tools/{name}", payload)
        if status < 200 or status >= 300:
            raise MCPTransportError(f"HTTP {status}: {text}")

        try:
            data = json.loads(text)
        except Exception as e:
            raise MCPProtocolError(f"invalid JSON response: {e} | body={text[:500]}") from e
        return data


# Factory (env-controlled)
def build_mcp_client() -> MCPClient:
    """
    Choose Mock or HTTP client based on environment variables.

    Env:
      USE_MCP=true|false         -> default false (mock)
      MCP_BASE_URL=http://...    -> required when USE_MCP=true
      MCP_API_TOKEN=...          -> optional
      MCP_TIMEOUT_SEC=30         -> optional
      MCP_RETRIES=2              -> optional
      MCP_BACKOFF=0.3            -> optional
    """
    use_mcp = os.getenv("USE_MCP", "false").lower() == "true"
    if not use_mcp:
        return MockMCPClient()

    base = os.getenv("MCP_BASE_URL")
    if not base:
        raise ValueError("MCP_BASE_URL is required when USE_MCP=true")

    token = os.getenv("MCP_API_TOKEN")
    timeout = float(os.getenv("MCP_TIMEOUT_SEC", "30"))
    retries = int(os.getenv("MCP_RETRIES", "2"))
    backoff = float(os.getenv("MCP_BACKOFF", "0.3"))

    return HttpMCPClient(
        base_url=base,
        api_token=token,
        timeout_sec=timeout,
        retries=retries,
        backoff=backoff,
    )
