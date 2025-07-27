import { Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface SearchBarProps {
  stockCode: string
  setStockCode: (value: string) => void
  onAnalyze: () => void
  isAnalyzing: boolean
  isFixed?: boolean
}

export const SearchBar = ({ 
  stockCode, 
  setStockCode, 
  onAnalyze, 
  isAnalyzing, 
  isFixed = false 
}: SearchBarProps) => {
  const containerClasses = isFixed 
    ? "w-full max-w-4xl mx-auto px-4 py-6 fixed bottom-0 left-1/2 -translate-x-1/2 z-50 bg-[#FFFAF0]/95 backdrop-blur-sm"
    : "w-full max-w-4xl mx-auto px-4 py-6"

  return (
    <div className={containerClasses} style={isFixed ? { position: 'fixed' } : undefined}>
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-center w-full max-w-full px-4">
        <div className="relative w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-amber-500 w-4 h-4" />
          <Input
            placeholder="종목명 / 종목코드 입력"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onAnalyze()}
            className="pl-10 border-amber-300 focus:ring-amber-300 h-14 text-base font-semisemibold"
          />
        </div>
        <Button
          onClick={onAnalyze}
          disabled={isAnalyzing || !stockCode.trim()}
          className="bg-amber-400 hover:bg-amber-500 text-amber-900 font-semibold px-8 h-14 text-base"
        >
          {isAnalyzing ? "분석 중..." : "분석"}
        </Button>
      </div>
    </div>
  )
} 