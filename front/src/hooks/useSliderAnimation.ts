import { useRef, useEffect, useState } from "react"

export const useSliderAnimation = () => {
  const sliderRef = useRef<HTMLDivElement>(null)
  const [slideX, setSlideX] = useState(0)
  const [isPaused, setIsPaused] = useState(false)

  useEffect(() => {
    const slider = sliderRef.current
    if (!slider) return
    let req: number
    let lastTimestamp = 0
    let width = slider.scrollWidth / 2 // 한 세트 길이
    const speed = 1.1 // px per frame

    function step(timestamp: number) {
      if (isPaused) {
        req = requestAnimationFrame(step)
        return
      }
      if (!lastTimestamp) lastTimestamp = timestamp
      lastTimestamp = timestamp
      setSlideX((prev) => {
        if (Math.abs(prev) >= width) {
          return 0
        }
        return prev - speed
      })
      req = requestAnimationFrame(step)
    }
    req = requestAnimationFrame(step)
    return () => cancelAnimationFrame(req)
  }, [isPaused])

  return {
    sliderRef,
    slideX,
    isPaused,
    setIsPaused,
  }
} 