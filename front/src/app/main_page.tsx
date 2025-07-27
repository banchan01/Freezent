"use client"

import { useState } from "react"
import { StockReport as StockReportType } from "@/types/stock"
import { DailyMover } from "@/types/stock"
import { mockDailyMovers } from "@/data/mockData"
import { analyzeStock } from "@/services/stockService"
import { Header } from "@/components/Header"
import { SearchBar } from "@/components/SearchBar"
import { StockReport } from "@/components/StockReport"
import { WelcomeSection } from "@/components/WelcomeSection"
import { DailyMovers } from "@/components/DailyMovers"
import { DailyMoverModal } from "@/components/DailyMoverModal"
import { KBLogo } from "@/components/KBLogo"

export default function FreezentApp() {
  const [stockCode, setStockCode] = useState("")
  const [report, setReport] = useState<StockReportType | null>(null)
  const [selectedMover, setSelectedMover] = useState<DailyMover | null>(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleAnalyze = async () => {
    if (!stockCode.trim()) return

    setIsAnalyzing(true)
    try {
      const mockReport = await analyzeStock(stockCode)
      setReport(mockReport)
    } catch (error) {
      console.error("분석 중 오류가 발생했습니다:", error)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleMoverSelect = (mover: DailyMover) => {
    setSelectedMover(mover)
  }

  const handleModalClose = () => {
    setSelectedMover(null)
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#FFFAF0]">
      <Header />
      
      {report ? (
        <>
          <StockReport report={report} />
          <SearchBar
            stockCode={stockCode}
            setStockCode={setStockCode}
            onAnalyze={handleAnalyze}
            isAnalyzing={isAnalyzing}
            isFixed={false}
          />
          {/* 검색창 아래 충분한 여백 추가 */}
          <div className="w-full h-[200px]" />
          <DailyMovers 
            movers={mockDailyMovers} 
            onMoverSelect={handleMoverSelect} 
          />
        </>
      ) : (
        <>
          <WelcomeSection />
          <SearchBar
            stockCode={stockCode}
            setStockCode={setStockCode}
            onAnalyze={handleAnalyze}
            isAnalyzing={isAnalyzing}
            isFixed={false}
          />
          {/* 검색창 아래 충분한 여백 추가 */}
          <div className="w-full h-[200px]" />
          <DailyMovers 
            movers={mockDailyMovers} 
            onMoverSelect={handleMoverSelect} 
          />
        </>
      )}

      <DailyMoverModal 
        selectedMover={selectedMover} 
        onClose={handleModalClose} 
      />
      <KBLogo />
    </div>
  )
}
