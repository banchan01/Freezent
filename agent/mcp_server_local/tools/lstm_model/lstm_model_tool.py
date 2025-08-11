from fastmcp import FastMCP

# 동기 predict_anomaly 말고, 비동기 버전 임포트
from .lstm_model_service import predict_anomaly_async


def register(mcp: FastMCP) -> None:
    """
    LSTM AE 앙상블 기반 이상탐지 툴을 MCP 서버 인스턴스에 등록한다.
    server에서 create_app() 후 register(mcp) 호출.
    """

    @mcp.tool(
        name="predict_lstm_anomaly",
        description=(
            "종목명을 입력하면 KRX에서 최근 1개월 시세를 수집하고, "
            "LSTM AutoEncoder 앙상블(10세트)로 이상치 비율을 계산해 반환합니다. "
            "입력 예: {'stock_name': '삼성전자'}  |  "
            "출력 예: {'stock': '삼성전자', 'anomaly_ratio': 0.1234}"
        ),
    )
    async def predict_lstm_anomaly_tool(stock_name: str) -> dict:
        """
        Args:
            stock_name (str): 조회할 종목명(정확한 한글 종목명 권장)
        Returns:
            dict: {'stock': str, 'anomaly_ratio': float}
        """
        if not isinstance(stock_name, str) or not stock_name.strip():
            raise ValueError("stock_name은 비어있지 않은 문자열이어야 합니다.")
        try:
            # ✅ 이벤트 루프 위에서 안전: 비동기 함수 직접 await
            return await predict_anomaly_async(stock_name.strip())
        except Exception as e:
            raise RuntimeError(f"LSTM 이상탐지 수행 실패: {e}")
