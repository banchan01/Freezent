# tools/floating_stock/floating_stock_tool.py

from typing import Any, Dict, Optional
from fastmcp import FastMCP

# 서비스 함수/모델만 가져와서 그대로 호출
from .floating_stock_service import (
    StockIdentifier,
    calculate_floating_stock_ratio,
)


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Pydantic(v2/v1)·일반 객체를 dict로 안전 변환."""
    if obj is None:
        return {}
    for attr in ("model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    return obj.__dict__ if hasattr(obj, "__dict__") else {"value": obj}


def register(mcp: FastMCP) -> None:
    """
    유동주식 관련 MCP 도구 등록.
    (툴은 서비스 레이어의 calculate_floating_stock_ratio만 호출)
    """

    @mcp.tool(
        name="calculate_floating_stock_ratio",
        description=(
            "종목명 또는 종목코드를 입력하면 서비스의 calculate_floating_stock_ratio를 호출해 "
            "DART 최대주주 현황(최근 2년 평균)을 바탕으로 유동주식 비율을 계산해 반환합니다. "
            "예: {'stock_name': '삼성전자'} 또는 {'stock_code': '005930'}"
        ),
    )
    async def calculate_floating_stock_ratio_tool(
        stock_name: Optional[str] = None,
        stock_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 최소 검증 후 서비스로 위임
        sname = (stock_name or "").strip() or None
        scode = (stock_code or "").strip() or None
        if not sname and not scode:
            raise ValueError("stock_name 또는 stock_code 중 하나는 필수입니다.")

        req = StockIdentifier(stock_name=sname, stock_code=scode)
        res = await calculate_floating_stock_ratio(req)
        return _to_dict(res)
