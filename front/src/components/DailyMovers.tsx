import { motion } from "framer-motion"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { DailyMover } from "@/types/stock"
import { useSliderAnimation } from "@/hooks/useSliderAnimation"

interface DailyMoversProps {
  movers: DailyMover[]
  onMoverSelect: (mover: DailyMover) => void
}

export const DailyMovers = ({ movers, onMoverSelect }: DailyMoversProps) => {
  const { sliderRef, slideX, isPaused, setIsPaused } = useSliderAnimation()

  return (
    <div className="w-full px-8 md:px-24 relative pb-16">
      {/* 양쪽 gradient 마스킹 */}
      <div 
        className="pointer-events-none absolute left-0 top-0 h-full w-10 md:w-24 z-10" 
        style={{background: 'linear-gradient(to right, #FFFAF0 80%, transparent)'}} 
      />
      <div 
        className="pointer-events-none absolute right-0 top-0 h-full w-10 md:w-24 z-10" 
        style={{background: 'linear-gradient(to left, #FFFAF0 80%, transparent)'}} 
      />
      <motion.section
        className="relative mt-24 w-full max-w-none"
        role="region"
        aria-label="오늘 급등락 종목"
      >
        <h2 className="text-2xl font-bold text-amber-800 mb-4 pl-2">오늘 급등락 종목</h2>
        <div className="relative w-full overflow-x-hidden overflow-y-hidden flex items-center h-36 scrollbar-none" style={{ WebkitOverflowScrolling: "touch" }}>
          <div
            ref={sliderRef}
            className="flex gap-4 min-w-max items-center select-none px-0"
            style={{
              transform: `translateX(${slideX}px)`,
              transition: isPaused ? "none" : "transform 0.03s linear",
              willChange: "transform",
            }}
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
            onTouchStart={() => setIsPaused(true)}
            onTouchEnd={() => setIsPaused(false)}
            tabIndex={0}
          >
            {[...movers, ...movers, ...movers, ...movers, ...movers].map((mover, idx) => (
              <div
                key={mover.code + idx}
                className="flex-shrink-0 w-64 h-32 sm:w-80 sm:h-36 snap-start"
                aria-label={`${mover.name} (${mover.code})`}
              >
                <Card className="h-full flex flex-col justify-between border-amber-200 hover:shadow-lg transition-shadow bg-white/90">
                  <CardContent className="p-2 flex flex-col justify-between h-full">
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <h3 className="font-semibold text-sm text-gray-800 truncate">{mover.name}</h3>
                        <p className="text-xs text-gray-500">{mover.code}</p>
                      </div>
                      <span className={`text-sm font-bold ${mover.changePercent > 0 ? "text-green-600" : "text-red-600"}`}>
                        {mover.changePercent > 0 ? "+" : ""}{mover.changePercent}%
                      </span>
                    </div>
                    <p className="text-xs text-gray-700 mb-1 line-clamp-2">{mover.reason}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full text-xs border-amber-200 hover:bg-amber-50 hover:border-amber-300 bg-transparent"
                      onClick={() => onMoverSelect(mover)}
                    >
                      자세히 보기
                    </Button>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </div>
      </motion.section>
    </div>
  )
} 