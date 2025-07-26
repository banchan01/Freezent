"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Search, TrendingUp, TrendingDown, AlertTriangle, FileText } from "lucide-react"

interface StockReport {
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

interface DailyMover {
  code: string
  name: string
  changePercent: number
  reason: string
  detailedExplanation: string
  newsItems?: string[]
}

const mockDailyMovers: DailyMover[] = [
  {
    code: "005930",
    name: "Samsung Electronics",
    changePercent: 8.5,
    reason: "Strong Q4 earnings report",
    detailedExplanation:
      "Samsung Electronics surged 8.5% following the release of better-than-expected Q4 earnings. The company reported record semiconductor profits driven by AI chip demand and memory price recovery.",
    newsItems: [
      "Q4 earnings beat analyst expectations by 15%",
      "AI chip division shows 40% growth",
      "Memory prices stabilizing after 2-year decline",
    ],
  },
  {
    code: "000660",
    name: "SK Hynix",
    changePercent: -6.2,
    reason: "Suspicious volume spike",
    detailedExplanation:
      "SK Hynix dropped 6.2% on unusually high trading volume (3x average). No specific news catalyst identified, but technical indicators suggest institutional selling pressure.",
    newsItems: [
      "Trading volume 300% above average",
      "No company announcements today",
      "Technical support level broken at 95,000 KRW",
    ],
  },
  {
    code: "035420",
    name: "NAVER",
    changePercent: 12.3,
    reason: "AI partnership announcement",
    detailedExplanation:
      "NAVER soared 12.3% after announcing a strategic AI partnership with Microsoft. The collaboration will integrate advanced AI capabilities into NAVER's search and cloud services.",
    newsItems: [
      "Microsoft partnership for AI integration",
      "New AI search features launching Q2",
      "Cloud business expansion in Southeast Asia",
    ],
  },
  {
    code: "051910",
    name: "LG Chem",
    changePercent: -4.8,
    reason: "Regulatory concerns",
    detailedExplanation:
      "LG Chem fell 4.8% amid concerns over new environmental regulations affecting battery manufacturing. The government announced stricter guidelines for lithium processing facilities.",
    newsItems: [
      "New environmental regulations announced",
      "Battery facility compliance costs rising",
      "Analyst downgrades from 3 firms",
    ],
  },
]

export default function FreezentApp() {
  const [stockCode, setStockCode] = useState("")
  const [report, setReport] = useState<StockReport | null>(null)
  const [selectedMover, setSelectedMover] = useState<DailyMover | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleAnalyze = async () => {
    if (!stockCode.trim()) return

    setIsAnalyzing(true)

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500))

    // Mock report data
    const mockReport: StockReport = {
      code: stockCode.toUpperCase(),
      name: stockCode === "005930" ? "Samsung Electronics" : `Stock ${stockCode}`,
      currentPrice: 71500,
      change: 2500,
      changePercent: 3.6,
      volume: 15420000,
      analysis: [
        "The stock shows strong bullish momentum with increased institutional buying activity over the past 5 trading days.",
        "Technical indicators suggest the stock is approaching a key resistance level at 75,000 KRW.",
        "Recent earnings report exceeded expectations, driving positive sentiment among analysts.",
        "However, market volatility remains high due to global economic uncertainties.",
      ],
      keyIndicators: [
        { label: "Price Change", value: "+3.6%", status: "positive" },
        { label: "Volume vs Avg", value: "+45%", status: "positive" },
        { label: "RSI", value: "68.5", status: "neutral" },
        { label: "P/E Ratio", value: "12.4", status: "positive" },
        { label: "Anomaly Score", value: "Low", status: "positive" },
      ],
    }

    setReport(mockReport)
    setIsAnalyzing(false)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-yellow-50 to-amber-50">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-amber-800 mb-2">Freezent</h1>
          <p className="text-amber-600">Smart Stock Analysis Platform</p>
        </div>

        {/* Report Section - Appears above input when available */}
        {report && (
          <Card className="mb-8 border-amber-200 bg-gradient-to-r from-yellow-50 to-amber-50 shadow-lg">
            <CardHeader className="bg-amber-100 border-b border-amber-200">
              <CardTitle className="flex items-center gap-2 text-amber-800">
                <FileText className="w-5 h-5" />
                Analysis Report: {report.name} ({report.code})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <div className="grid md:grid-cols-2 gap-6">
                {/* Analysis Summary */}
                <div>
                  <h3 className="font-semibold text-amber-800 mb-3">Analysis Summary</h3>
                  <div className="space-y-2">
                    {report.analysis.map((point, index) => (
                      <p key={index} className="text-sm text-gray-700 leading-relaxed">
                        • {point}
                      </p>
                    ))}
                  </div>
                </div>

                {/* Key Indicators */}
                <div>
                  <h3 className="font-semibold text-amber-800 mb-3">Key Indicators</h3>
                  <div className="space-y-2">
                    {report.keyIndicators.map((indicator, index) => (
                      <div key={index} className="flex justify-between items-center py-1">
                        <span className="text-sm text-gray-600">{indicator.label}</span>
                        <Badge
                          variant={
                            indicator.status === "positive"
                              ? "default"
                              : indicator.status === "negative"
                                ? "destructive"
                                : "secondary"
                          }
                          className={indicator.status === "positive" ? "bg-green-100 text-green-800" : ""}
                        >
                          {indicator.value}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-amber-200">
                <p className="text-xs text-gray-500 italic">
                  ⚠️ This is not investment advice. Please conduct your own research before making investment decisions.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stock Input Section */}
        <Card className="mb-8 border-amber-200 bg-white/80 backdrop-blur-sm shadow-lg">
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-amber-500 w-4 h-4" />
                <Input
                  placeholder="Enter stock code (e.g., 005930)"
                  value={stockCode}
                  onChange={(e) => setStockCode(e.target.value)}
                  className="pl-10 border-amber-200 focus:border-amber-400 focus:ring-amber-200"
                  onKeyPress={(e) => e.key === "Enter" && handleAnalyze()}
                />
              </div>
              <Button
                onClick={handleAnalyze}
                disabled={isAnalyzing || !stockCode.trim()}
                className="bg-amber-400 hover:bg-amber-500 text-amber-900 font-medium px-8"
              >
                {isAnalyzing ? "Analyzing..." : "Analyze"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Daily Movers Section */}
        <Card className="border-amber-200 bg-white/80 backdrop-blur-sm shadow-lg">
          <CardHeader className="bg-gradient-to-r from-amber-50 to-yellow-50 border-b border-amber-200">
            <CardTitle className="flex items-center gap-2 text-amber-800">
              <TrendingUp className="w-5 h-5" />
              Daily Movers
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <ScrollArea className="w-full">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {mockDailyMovers.map((mover, index) => (
                  <Card
                    key={index}
                    className="cursor-pointer hover:shadow-md transition-all duration-200 border-amber-100 hover:border-amber-300"
                    onClick={() => setSelectedMover(mover)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <h4 className="font-medium text-sm text-gray-800 truncate">{mover.name}</h4>
                          <p className="text-xs text-gray-500">{mover.code}</p>
                        </div>
                        <div className="flex items-center gap-1">
                          {mover.changePercent > 0 ? (
                            <TrendingUp className="w-4 h-4 text-green-500" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-red-500" />
                          )}
                          <span
                            className={`text-sm font-medium ${
                              mover.changePercent > 0 ? "text-green-600" : "text-red-600"
                            }`}
                          >
                            {mover.changePercent > 0 ? "+" : ""}
                            {mover.changePercent}%
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-gray-600 mb-3 line-clamp-2">{mover.reason}</p>

                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full text-xs border-amber-200 hover:bg-amber-50 hover:border-amber-300 bg-transparent"
                      >
                        See Details
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Modal for Daily Mover Details */}
        <Dialog open={!!selectedMover} onOpenChange={() => setSelectedMover(null)}>
          <DialogContent className="max-w-2xl bg-gradient-to-br from-yellow-50 to-amber-50 border-amber-200">
            {selectedMover && (
              <>
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-3 text-amber-800">
                    <div className="flex items-center gap-2">
                      {selectedMover.changePercent > 0 ? (
                        <TrendingUp className="w-5 h-5 text-green-500" />
                      ) : (
                        <TrendingDown className="w-5 h-5 text-red-500" />
                      )}
                      <span>
                        {selectedMover.name} ({selectedMover.code})
                      </span>
                    </div>
                    <Badge
                      variant={selectedMover.changePercent > 0 ? "default" : "destructive"}
                      className={selectedMover.changePercent > 0 ? "bg-green-100 text-green-800" : ""}
                    >
                      {selectedMover.changePercent > 0 ? "+" : ""}
                      {selectedMover.changePercent}%
                    </Badge>
                  </DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium text-amber-800 mb-2">Detailed Analysis</h4>
                    <p className="text-gray-700 leading-relaxed">{selectedMover.detailedExplanation}</p>
                  </div>

                  {selectedMover.newsItems && (
                    <div>
                      <h4 className="font-medium text-amber-800 mb-2 flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Related News & Events
                      </h4>
                      <ul className="space-y-1">
                        {selectedMover.newsItems.map((news, index) => (
                          <li key={index} className="text-sm text-gray-600 flex items-start gap-2">
                            <span className="text-amber-500 mt-1">•</span>
                            <span>{news}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="pt-4 border-t border-amber-200">
                    <p className="text-xs text-gray-500 italic">
                      ⚠️ This analysis is for informational purposes only and should not be considered as investment
                      advice.
                    </p>
                  </div>
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
