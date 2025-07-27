export interface StockReport {
  code: string
  name: string
  currentPrice: number
  change: number
  changePercent: number
  volume: number
  analysis: string[]
  keyIndicators: {
    label: string
    value: string
    status: "positive" | "negative" | "neutral"
  }[]
}

export interface DailyMover {
  code: string
  name: string
  changePercent: number
  reason: string
  detailedExplanation: string
  newsItems?: string[]
} 