import { StockReport } from "@/types/stock"
import { createMockReport } from "@/data/mockData"
import { llmReportMarkdown } from "@/data/stockReport"

export const analyzeStock = async (stockCode: string): Promise<StockReport> => {
  await new Promise((resolve) => setTimeout(resolve, 1500))
  
  return {
    name: "삼성바이오로직스",
    code: stockCode,
    currentPrice: 757000,
    change: -1500,
    changePercent: -0.2,
    volume: 1234567,
    analysis: [
      "30일 전망 최종 위험 점수: 0.2326 (LOW)",
      "가격 이상 비율(LSTM): 0.4631",
      "최근 5일 평균 거래량 45.62% 감소",
      "긍정 뉴스와 과거 회계 이슈가 공존하여 불확실성 존재"
    ],
    keyIndicators: [
      { label: "최종 위험 점수", value: "0.2326 (LOW)", status: "positive" },
      { label: "가격 이상 비율", value: "0.4631", status: "neutral" },
      { label: "5일 거래량 변화", value: "-45.62%", status: "negative" },
    ],
    // ⬇️ 여기서 마크다운 원문도 같이 반환
    llmReport: llmReportMarkdown
  }
}