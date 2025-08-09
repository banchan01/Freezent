from fastapi import FastAPI
from routers.floating_stock_router import router as floating_stock_router
from routers.biz_perf_tentative_router import router as biz_perf_tentative_router
app = FastAPI(title="Freezent Backend API", description="주식 분석 백엔드 API")

# 라우터 포함
app.include_router(floating_stock_router, tags=["floating_stocks"])
app.include_router(biz_perf_tentative_router, tags=["biz_perf_tentative"])
app.include_router(news_anal_router, tags=["news_anal"])

@app.get("/")
async def root():
    return {"message": "Freezent Backend API 서비스"}
