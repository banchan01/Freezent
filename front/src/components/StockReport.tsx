"use client"

import { FileText } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { StockReport as StockReportType } from "@/types/stock"
import { motion } from "framer-motion"
import MarkdownViewer from "@/components/MarkdownViewer"

interface StockReportProps {
  report: StockReportType
}

export const StockReport = ({ report }: StockReportProps) => {
  const analysis = report.analysis ?? []
  const keyIndicators = report.keyIndicators ?? []

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pt-32 pb-8">
      {/* 제목 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="text-center mb-8"
      >
        <h2 className="text-3xl md:text-4xl font-bold text-amber-700 leading-snug">
          {report.name} 분석결과
        </h2>
        {/* (선택) 가격 정보가 타입에 있다면 간단 배지 표기 */}
        {"currentPrice" in report && (
          <p className="mt-2 text-sm text-gray-600">
            현재가: {(report as any).currentPrice?.toLocaleString?.()}원&nbsp;|&nbsp;
            변화: {(report as any).change} ({(report as any).changePercent}%)
          </p>
        )}
      </motion.div>

      {/* 1) 원문 Markdown 리포트 (있을 때만) */}
      {("llmReport" in report && (report as any).llmReport) && (
        <Card className="mb-8 border-amber-200 bg-white shadow-lg">
          <CardHeader className="bg-amber-50 border-b border-amber-200">
            <CardTitle className="flex items-center gap-2 text-amber-800">
              <FileText className="w-5 h-5" />
              원문 리포트 (Markdown)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <MarkdownViewer content={(report as any).llmReport} />
          </CardContent>
        </Card>
      )}

      {/* 2) 카드형 요약 */}
      <Card className="mb-8 border-amber-200 bg-gradient-to-r from-yellow-50 to-amber-50 shadow-lg">
        <CardHeader className="bg-amber-100 border-b border-amber-200">
          <CardTitle className="flex items-center gap-2 text-amber-800">
            <FileText className="w-5 h-5" />
            분석 리포트: {report.name} ({report.code})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* 분석 요약 */}
            <div>
              <h3 className="font-semibold text-amber-800 mb-3">분석 요약</h3>
              {analysis.length > 0 ? (
                <div className="space-y-2">
                  {analysis.map((point, index) => (
                    <p key={index} className="text-sm text-gray-700 leading-relaxed">
                      • {point}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">요약 정보가 없습니다.</p>
              )}
            </div>

            {/* 핵심 지표 */}
            <div>
              <h3 className="font-semibold text-amber-800 mb-3">핵심 지표</h3>
              {keyIndicators.length > 0 ? (
                <div className="space-y-2">
                  {keyIndicators.map((indicator, index) => (
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
              ) : (
                <p className="text-sm text-gray-500">지표 정보가 없습니다.</p>
              )}
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-amber-200">
            <p className="text-xs text-gray-500 italic">
              ⚠️ 본 분석은 투자 권유가 아니며, 투자 결정의 책임은 본인에게 있습니다.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
