import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { DailyMover } from "@/types/stock"

interface DailyMoverModalProps {
  selectedMover: DailyMover | null
  onClose: () => void
}

export const DailyMoverModal = ({ selectedMover, onClose }: DailyMoverModalProps) => {
  return (
    <Dialog open={!!selectedMover} onOpenChange={onClose}>
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
                <h4 className="font-medium text-amber-800 mb-2">상세 분석</h4>
                <p className="text-gray-700 leading-relaxed">{selectedMover.detailedExplanation}</p>
              </div>

              {selectedMover.newsItems && (
                <div>
                  <h4 className="font-medium text-amber-800 mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    관련 뉴스 & 이벤트
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
                  ⚠️ 본 분석은 정보 제공 목적이며, 투자 조언이 아닙니다.
                </p>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
} 