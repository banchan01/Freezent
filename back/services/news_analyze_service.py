import os
import asyncio
import json
from openai import AsyncOpenAI
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv


load_dotenv()

# ===== 2. OpenAI 클라이언트 =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "환경변수 OPENAI_API_KEY가 필요합니다."

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ===== 3. GPT 분석 프롬프트 =====
def build_prompt(stock_name: str, article_content: str) -> str:
    return f"""
너는 기사 본문을 분석해 **'{stock_name}' 관련성**과 **신뢰성이 낮을 수 있는 이유**를 판단하는 전문가다.  
오직 제공된 기사 텍스트만 근거로 사용하며, **추가 추정이나 외부 사실 생성은 금지**한다.  
반드시 **JSON 형식**으로만 응답한다.

[1단계: 관련성 판단]
- '{stock_name}'이 기사에서 중심 주제로 다뤄지는지 평가한다.
- '{stock_name}'이 잠깐 언급되거나, 주제와 거의 무관하면 "관련성 낮음"으로 표시한다.
- 관련성이 낮으면 신뢰도 평가는 생략하고, 관련성 판단 이유만 작성한다.

[2단계: 신뢰도 평가] (관련성 높음일 때만 진행)
[판정 원칙: 보수적(Conservative)]
- 기본값은 "정상(높음/보통)"이며, **명확한 증거**가 있을 때만 "낮음"으로 판정한다.
- "낮음" 판정 조건:
  (A) 주요 기준(Strong) 중 2개 이상이 강하게 성립하고, 각 기준마다 기사 원문에서 직접 인용한 근거 문장이 있음  
  (B) 또는 주요 기준 1개가 매우 강하게 성립하고, 보조 기준 중 1개 이상이 성립하며, 근거 문장이 있음
- 위 조건을 충족하지 못하면 "불충분"으로 판정한다.
- 기사 안에 스스로의 주장을 제한하는 표현(“~할 수 있다”, “~가능성”, “만약 ~라면”)이나 **공식 근거(공시·기관명·자료 링크)**가 있으면 감점한다.

[신뢰도 평가 기준]
(보조 기준)
1. 수치/팩트 부족: 매출·계약금액·성장률 등 구체 수치 없음
2. 근거 불분명한 출처: "~에 따르면", "~로 알려졌다" 등
3. 과도한 형용사·감정적 수식어: "막대한", "세계 최초", "핵심 수혜주"
4. 숫자 대비 수식어 비율 과다
5. 본문 길이에 비해 정보 부족
6. ‘기대’ 중심 서술: "기대된다", "가능성 있다"
7. 기술/산업 추상어 남용: "4차 산업", "혁신기술", "미래 성장성"
(Strong 기준)
8. 인과관계 과장: 연관 약한 사건을 "~때문에 급등" 등으로 단정
9. 공식 공시/기관 출처 부재
10. 투자 유도/가격 단정: 매수 권유·급등 암시·목표가 제시(근거/리스크 부재)
11. 제목-본문 불일치: 제목의 주장/수치가 본문에 없음
12. 시점 불일치/과거 재활용: 오래된·조건부·미래 내용을 현재 사실처럼 표기
13. 이해상충 가능성: 광고·제휴·협찬·지분 관계 암시

[출력 JSON 형식]
{{
  "관련성": "높음/낮음",
  "관련성 판단 근거": "관련성을 이렇게 판단한 이유",
  "신뢰도 평가": {{
    "해당되는 기준과 판단 이유": [
      {{
        "기준 번호": "8",
        "판단 이유": "왜 해당되는지 구체적으로 설명",
        "근거 발췌": "기사 원문에서 인용한 1~2문장",
        "증거 강도": "약함/보통/강함"
      }}
    ],
    "추가 점검 결과": {{
      "제목_본문_불일치": false,
      "시점_불일치": false,
      "이해상충_징후": false
    }},
    "최종 판단": {{
      "신뢰도 수준": "높음/보통/낮음/불충분",
      "신뢰도 점수": 0.00,
      "에스컬레이션 필요": false,
      "판단 근거": "핵심 이유 요약 (2~4줄)"
    }}
  }}
}}

기사 내용:
{article_content}
"""


# ===== 4. GPT 분석 함수 =====
async def analyze_article(
    stock_name: str, article_content: str, model: str = "gpt-4.1"
) -> Dict[str, Any]:
    user_prompt = build_prompt(stock_name, article_content)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "너는 신뢰도 분석 전문가야. 주어진 기사 내용을 위 기준에 따라 분석하고 JSON 형식으로 결과를 제공해.",
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=90,
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {"raw": resp.choices[0].message.content, "error": "JSON parse failed"}


# ===== 5. 병렬 분석 =====
async def analyze_articles(
    items: List[Dict[str, str]], concurrency: int = 5
) -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
    sem = asyncio.Semaphore(concurrency)
    results: List[Tuple[Dict[str, str], Dict[str, Any]]] = [None] * len(items)

    async def worker(i: int, it: Dict[str, str]):
        async with sem:
            res = await analyze_article(it["stock_name"], it["article_content"])
            results[i] = (it, res)

    await asyncio.gather(
        *[asyncio.create_task(worker(i, it)) for i, it in enumerate(items)]
    )
    return results
