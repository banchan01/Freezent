from fastmcp import FastMCP
from tools.lockup.lockup_tool import register as register_lockup
from tools.stock_info.stock_info_tool import register as register_stock_info
from tools.news.news_tool import register as register_news
from tools.floating_stock.floating_stock_tool import register as register_floating_stock
from tools.biz_perf.biz_perf_tool import register as register_biz_perf
from tools.corp_info.corp_info_tool import register as register_corp_info
from tools.lstm_model.lstm_model_tool import register as register_lstm_model
from tools.paid_in_capital_increase.paid_in_capital_increase_tool import register as register_paid_in_list

def create_app() -> FastMCP:
    # FastMCP 생성자에는 description 미지원 → name만 사용
    mcp = FastMCP(name="kbai-lockup")
    # 기능별 등록
    register_lockup(mcp)
    register_stock_info(mcp)
    register_news(mcp)
    register_floating_stock(mcp)
    register_biz_perf(mcp)
    register_corp_info(mcp)
    register_lstm_model(mcp)
    register_paid_in_list(mcp)
    return mcp


if __name__ == "__main__":
    app = create_app()
    # LangChain MCP Adapters로 붙일 거라 HTTP 모드로 실행
    app.run(transport="streamable-http", host="0.0.0.0", port=8000)
