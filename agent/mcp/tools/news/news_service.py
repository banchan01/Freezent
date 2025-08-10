# tools/news/news_service.py

# ===== 1) 크롤링 =====
import os
import re
import json
import asyncio
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, urlparse
from typing import List, Dict, Any, Tuple, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.infostockdaily.co.kr"


def clean_text(tag):
    return tag.get_text(separator=" ", strip=True) if tag else "내용 없음"


def crawl_articles_by_stock(
    stock_name: str, max_articles: int = 10
) -> List[Dict[str, str]]:
    articles: List[Dict[str, str]] = []
    page = 1
    skip_pattern = r"^\[\d{4}[^\]]+\]"
    encoded_name = quote(stock_name)

    while len(articles) < max_articles:
        print(
            f"[+] '{stock_name}' 검색, {page}페이지 요청 중... (현재 {len(articles)}/{max_articles}개)"
        )
        search_url = f"{BASE_URL}/news/articleList.html?sc_section_code=S1N17&view_type=sm&sc_word={encoded_name}&page={page}"

        try:
            res = requests.get(search_url, verify=False, timeout=10)
            res.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[!] 페이지 요청 실패: {e}")
            break

        soup = BeautifulSoup(res.text, "html.parser")
        article_blocks = soup.select("div.list-block")
        if not article_blocks:
            print("[-] 더 이상 기사 없음. 탐색 중단.")
            break

        for block in article_blocks:
            if len(articles) >= max_articles:
                break

            title_tag = block.select_one("div.list-titles a")
            if not title_tag:
                continue

            preview_title = title_tag.get_text(strip=True)
            if re.match(skip_pattern, preview_title):
                print(f"  [-] 제목 형식 불일치로 제외: {preview_title}")
                continue

            link = urljoin(BASE_URL, title_tag.get("href"))

            try:
                detail_res = requests.get(link, verify=False, timeout=10)
                detail_soup = BeautifulSoup(detail_res.text, "html.parser")

                full_title = clean_text(
                    detail_soup.select_one("div.article-head-title")
                )
                content_tag = detail_soup.select_one("div#article-view-content-div")

                if content_tag:
                    if tag_group_div := content_tag.select_one(".tag-group"):
                        tag_group_div.decompose()
                    if script_tag := content_tag.find("script"):
                        script_tag.decompose()
                    if copyright_div := content_tag.select_one(".view-copyright"):
                        copyright_div.decompose()
                    if editors_div := content_tag.select_one(".view-editors"):
                        editors_div.decompose()
                    p_tags = content_tag.find_all("p")
                    if p_tags:
                        p_tags[-1].decompose()

                content = clean_text(content_tag)

                date_text = "날짜 정보 없음"
                info_lis = detail_soup.select("div.info-text li")
                for li in info_lis:
                    if "최종수정" in li.get_text():
                        date_text = (
                            li.get_text(strip=True).replace("최종수정", "").strip()
                        )
                        break
                if date_text == "날짜 정보 없음":
                    for li in info_lis:
                        if "승인" in li.get_text():
                            date_text = (
                                li.get_text(strip=True).replace("승인", "").strip()
                            )
                            break

                articles.append(
                    {
                        "종목명": stock_name,
                        "제목": full_title,
                        "날짜": date_text,
                        "본문": content,
                        "링크": link,
                    }
                )
                print(f"  [+] 저장됨: {full_title}")

            except Exception as e:
                print(f"[!] 기사 크롤링 실패: {link} → {e}")

        page += 1

    return articles


# ===== 2) GPT 분석 =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "환경변수 OPENAI_API_KEY가 필요합니다."
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


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
1. 수치/팩트 부족
2. 근거 불분명한 출처
3. 과도한 형용사·감정적 수식어
4. 숫자 대비 수식어 비율 과다
5. 본문 길이에 비해 정보 부족
6. ‘기대’ 중심 서술
7. 기술/산업 추상어 남용
(Strong 기준)
8. 인과관계 과장
9. 공식 공시/기관 출처 부재
10. 투자 유도/가격 단정
11. 제목-본문 불일치
12. 시점 불일치/과거 재활용
13. 이해상충 가능성

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


async def analyze_articles(
    items: List[Dict[str, str]], concurrency: int = 5, model: str = "gpt-4.1"
) -> List[Tuple[Dict[str, str], Dict[str, Any]]]:
    sem = asyncio.Semaphore(concurrency)
    results: List[Tuple[Dict[str, str], Dict[str, Any]]] = [None] * len(items)

    async def worker(i: int, it: Dict[str, str]):
        async with sem:
            res = await analyze_article(
                it["stock_name"], it["article_content"], model=model
            )
            results[i] = (it, res)

    await asyncio.gather(
        *[asyncio.create_task(worker(i, it)) for i, it in enumerate(items)]
    )
    return results
