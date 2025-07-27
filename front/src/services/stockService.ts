import { StockReport } from "@/types/stock"
import { createMockReport } from "@/data/mockData"

export const analyzeStock = async (stockCode: string): Promise<StockReport> => {
  // API 호출 시뮬레이션
  await new Promise((resolve) => setTimeout(resolve, 1500))
  
  // Mock 리포트 데이터 반환
  return createMockReport(stockCode)
} 