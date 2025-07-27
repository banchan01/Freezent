import { DailyMover, StockReport } from "@/types/stock"

export const mockDailyMovers: DailyMover[] = [
  {
    code: "005930",
    name: "삼성전자",
    changePercent: 8.5,
    reason: "4분기 실적 호조",
    detailedExplanation:
      "삼성전자는 예상치를 상회한 4분기 실적 발표 이후 8.5% 급등했습니다. AI 칩 수요와 메모리 가격 회복에 힘입어 반도체 부문에서 기록적인 이익을 달성했습니다.",
    newsItems: [
      "4분기 실적, 애널리스트 예상치 대비 15% 상회",
      "AI 칩 부문 40% 성장",
      "2년 하락 끝에 메모리 가격 안정화",
    ],
  },
  {
    code: "000660",
    name: "SK하이닉스",
    changePercent: -6.2,
    reason: "의심스러운 거래량 급증",
    detailedExplanation:
      "SK하이닉스는 평균 대비 3배 수준의 거래량 급증 속에서 6.2% 하락했습니다. 특정 뉴스 촉매는 확인되지 않았으나, 기술적 지표는 기관 매도 압력을 시사합니다.",
    newsItems: [
      "평균 대비 300% 높은 거래량",
      "금일 회사 공시 없음",
      "95,000원 기술적 지지선 하향 이탈",
    ],
  },
  {
    code: "035420",
    name: "네이버",
    changePercent: 12.3,
    reason: "AI 파트너십 발표",
    detailedExplanation:
      "네이버는 마이크로소프트와의 전략적 AI 파트너십을 발표한 뒤 12.3% 급등했습니다. 이번 협력으로 네이버 검색과 클라우드 서비스에 고급 AI 기능이 통합될 예정입니다.",
    newsItems: [
      "마이크로소프트와 AI 통합을 위한 파트너십",
      "Q2에 새로운 AI 검색 기능 출시 예정",
      "동남아 클라우드 사업 확대",
    ],
  },
  {
    code: "051910",
    name: "LG화학",
    changePercent: -4.8,
    reason: "규제 우려",
    detailedExplanation:
      "LG화학은 배터리 제조에 영향을 미치는 새로운 환경 규제 우려로 4.8% 하락했습니다. 정부는 리튬 정제 시설에 대한 더 엄격한 가이드라인을 발표했습니다.",
    newsItems: [
      "새로운 환경 규제 발표",
      "배터리 시설의 컴플라이언스 비용 상승",
      "3개 증권사에서 투자의견 하향",
    ],
  },
  {
    code: "006400",
    name: "삼성SDI",
    changePercent: 7.2,
    reason: "전기차 배터리 수주 확대",
    detailedExplanation:
      "삼성SDI는 글로벌 전기차 업체와의 대규모 배터리 공급 계약 체결 소식에 7.2% 급등했습니다. 향후 3년간 연간 50GWh 규모의 배터리 공급이 예상됩니다.",
    newsItems: [
      "글로벌 전기차 업체와 50GWh 공급 계약",
      "미국 조지아주 배터리 공장 확장",
      "고성능 배터리 기술 개발 성과",
    ],
  },
]

export const createMockReport = (stockCode: string): StockReport => ({
  code: stockCode.toUpperCase(),
  name: stockCode === "005930" ? "삼성전자" : stockCode,
  currentPrice: 71500,
  change: 2500,
  changePercent: 3.6,
  volume: 15420000,
  analysis: [
    "최근 5거래일 동안 기관 매수세가 유입되며 강한 상승 모멘텀을 보입니다.",
    "기술적 지표상 75,000원 부근의 주요 저항선 접근이 관측됩니다.",
    "최근 실적이 시장 기대치를 상회하며 애널리스트들의 긍정적인 평가가 이어지고 있습니다.",
    "다만, 글로벌 경기 불확실성으로 인한 변동성 확대에는 유의가 필요합니다.",
  ],
  keyIndicators: [
    { label: "가격 변화", value: "+3.6%", status: "positive" },
    { label: "평균 대비 거래량", value: "+45%", status: "positive" },
    { label: "RSI", value: "68.5", status: "neutral" },
    { label: "P/E 비율", value: "12.4", status: "positive" },
    { label: "이상치 점수", value: "Low", status: "positive" },
  ],
}) 