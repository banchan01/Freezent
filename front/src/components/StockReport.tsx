import { FileText } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { StockReport as StockReportType } from "@/types/stock"
import { motion } from "framer-motion"

interface StockReportProps {
  report: StockReportType
}

export const StockReport = ({ report }: StockReportProps) => {
  return (
    <div className="w-full max-w-4xl mx-auto px-4 pt-32 pb-8">
      {/* 분석 결과 제목 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="text-center mb-8"
      >
        <h2 className="text-3xl md:text-4xl font-bold text-amber-700 leading-snug">
          {report.name} 분석결과
        </h2>
      </motion.div>
      
      <Card className="mb-8 border-amber-200 bg-gradient-to-r from-yellow-50 to-amber-50 shadow-lg">
        <CardHeader className="bg-amber-100 border-b border-amber-200">
          <CardTitle className="flex items-center gap-2 text-amber-800">
            <FileText className="w-5 h-5" />
            분석 리포트: {report.name} ({report.code})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Analysis Summary */}
            <div>
              <h3 className="font-semibold text-amber-800 mb-3">분석 요약</h3>
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
              <h3 className="font-semibold text-amber-800 mb-3">핵심 지표</h3>
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
              ⚠️ 본 분석은 투자 권유가 아니며, 투자 결정의 책임은 본인에게 있습니다.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 