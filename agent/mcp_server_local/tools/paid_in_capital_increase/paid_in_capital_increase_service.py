import os
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)

def get_paid_in_analysis(corp_code: str) -> dict:
    """
    특정 기업의 유상증자 내역을 조회하고,
    OpenAI Chat 모델로 투자 판단 / 주가조작 위험 분석을 요청.
    """
    if not DART_API_KEY:
        return {"error": "DART_API_KEY is not set."}
    if not OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY is not set."}

    BASE_URL = "https://opendart.fss.or.kr/api/piicDecsn.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": "20250101",
        "end_de": "20250814",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"HTTP/Parsing error: {e}"}

    if data.get("status") != "000":
        return {"error": f"DART API status {data.get('status')}: {data.get('message')}"}

    piic_list = data.get("list", []) or []

    field_description = """
다음은 DART 'piicDecsn' API의 필드 설명입니다:

- status: 에러 및 정보 코드
- message: 에러 및 정보 메시지
- list: 유상증자 내역 리스트
  - rcept_no: 접수번호
  - corp_cls: 법인구분
  - corp_code: 고유번호
  - corp_name: 회사명
  - nstk_ostk_cnt: 신주의 종류와 수 (보통주식, 주)
  - nstk_estk_cnt: 신주의 종류와 수 (기타주식, 주)
  - fv_ps: 1주당 액면가액 (원)
  - bfic_tisstk_ostk: 증자전 발행주식총수 (보통주식, 주)
  - bfic_tisstk_estk: 증자전 발행주식총수 (기타주식, 주)
  - fdpp_fclt: 자금조달의 목적 - 시설자금 (원)
  - fdpp_bsninh: 자금조달의 목적 - 영업양수자금 (원)
  - fdpp_op: 자금조달의 목적 - 운영자금 (원)
  - fdpp_dtrp: 자금조달의 목적 - 채무상환자금 (원)
  - fdpp_ocsa: 자금조달의 목적 - 타법인 증권 취득자금 (원)
  - fdpp_etc: 자금조달의 목적 - 기타자금 (원)
  - ic_mthn: 증자방식
  - ssl_at: 공매도 해당여부
  - ssl_bgd: 공매도 시작일
  - ssl_edd: 공매도 종료일
"""

    try:
        prompt = (
            f"{field_description}\n\n"
            "아래는 특정 기업의 과거 유상증자(제3자배정 포함) 공시 데이터입니다.\n"
            "각 공시를 참고하여 다음 항목을 분석해주세요:\n"
            "1. 투자 판단 (긍정/부정 요인과 근거 포함)\n"
            "2. 주가조작 위험 가능성 평가 (패턴, 비정상 자금조달 목적, 공매도 정보 등을 종합)\n\n"
            f"공시 데이터:\n{piic_list}"
        )

        chat_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        analysis_text = chat_resp.choices[0].message.content.strip()
    except Exception as e:
        return {"error": f"Chat model error: {e}", "piic_list": piic_list}

    return {
        "corp_code": corp_code,
        "piic_list": piic_list,
        "analysis": analysis_text,
    }
