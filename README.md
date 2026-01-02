# **Freezent**

<!-- <img width="428" height="359" alt="kb_login_poster" src="https://github.com/user-attachments/assets/a4d43fda-56cd-4b3e-b590-3a478a0cb45d" /> -->

**Freezent**는 주가 조작 및 불공정 거래 행위에 대응하기 위해 개발된 LangGraph 기반 멀티 에이전트 분석 시스템입니다.<br>
`News_agent`, `Filings_agent`, `LSTM_agent`로 구성된 각 에이전트가 정형·비정형 데이터를 독립적으로 분석하여 정보의 비대칭성을 해소하고 투자자의 합리적인 의사결정을 지원하는 것을 목표로 합니다.

**시연 영상**

![시연영상](https://github.com/user-attachments/assets/df9e7fe7-c7de-43e7-b9c1-77bd863372a3)

---

## ✨ 주요 기능

### 1. 멀티 에이전트 시스템
<img width="743" alt="LSTM-AE Analysis" src="https://github.com/user-attachments/assets/9347d96d-c1e0-4740-b3b4-236a37cb9b26" /> <br>
Freezent는 ReWOO(Reasoning WithOut Observation) 아키텍처 기반의 멀티 에이전트 시스템으로, 각 도메인에 특화된 에이전트들이 독립적으로 분석을 수행한 뒤 그 결과를 종합합니다. <br>
시스템 전반은 **Orchestrator**가 제어하며, **Meta Planner**가 사용자 요청을 하위 분석 작업으로 분해하고, **Fusion Solver**가 각 에이전트의 분석 결과를 통합하여 최종 결론을 도출합니다.

*   **뉴스 분석 에이전트 (News Agent)**: 뉴스 데이터를 수집/분석하여 기업에 미치는 호재 및 악재를 분류하고, 정보의 신뢰도를 평가합니다.
*   **공시 분석 에이전트 (Filings Agent)**: 공시 문서를 분석하여 주가 변동성에 영향을 미칠 수 있는 주요 이벤트를 식별합니다.
*   **이상 탐지 에이전트 (Anomaly Detection Agent)**: LSTM-Autoencoder 모델을 활용하여 주가 시계열에서 이상 거래 패턴을 탐지합니다.

### 2. 정형·비정형 데이터 통합 분석

Freezent는 정형 데이터와 비정형 데이터를 결합하여 기존 시스템이 놓칠 수 있는 미세한 조작 징후까지 탐지합니다.

#### 📊 정형 데이터 분석
- **LSTM-AE 기반 이상 탐지 모델**
  - **데이터셋**: KRX 정보데이터 시스템의 *KOSPI 전종목 시세* (2005.01 ~ 2025.07)
  - **앙상블 학습**: 전체 KOSPI 종목 중 300개를 선정하여 학습, 종목 편향 최소화
  - **이상 징후 판단**: 30일 윈도우의 주가·거래량 시계열에 대해 Reconstruction Error를 산출하고, 사전 정의된 Threshold 초과 여부로 이상 여부를 판정
  *   **성능 예시**: 실제 주가 조작 논란이 있었던 '삼부토건'의 데이터 테스트 결과, 논란이 발생한 5월~7월 구간에서 모델이 산출한 이상치 비율(Ratio)이 급격히 상승하는 것을 확인할 수 있습니다.
        <img width="1344" alt="Sam-bu Analysis" src="https://github.com/user-attachments/assets/4b443fa9-d503-475c-a744-f200171df726" />

#### 📑 비정형 데이터 분석
- **뉴스 신뢰도 및 연관성 분석**
  - **데이터 수집**: HTS 뉴스 제공 플랫폼 *Infostockdaily* 크롤링
  - **연관성 판단**: 기사 핵심 주제와 분석 대상 종목 간 직접적 연관성 여부 판별
  - **신뢰도 평가**: 기사 출처, 어조, 근거 정보를 기반으로 비동기 분석 수행, 허위 정보 및 찌라시성 뉴스 필터링

- **유동주식 비율 분석**
  - **데이터 소스**: DART *최대주주 현황* API, 사업보고서
  - **분석 지표**: 최대주주 기말 보유 주식 지분율
  - **비교 기준**: KOSPI 평균 유동주식 비율(≈57%) 대비 상대적 유동성 평가

- **제3자 배정 유상증자 감지**
  - **데이터 소스**: DART *유상증자결정* 공시
  - **탐지 기준**: 신주 발행 방식이 제3자 배정에 해당하는지 여부
  - **분석 목적**: 경영권 변동 및 특정 세력 개입 가능성 신호 포착

- **실적 변동성 및 기재 정정 추적**
  - **데이터 소스**: DART *영업실적등에대한전망(공정공시)*
  - **분석 지표**: QoQ / YoY 기준 실적 변동폭
  - **이상 신호**: 공시 이후 *기재 정정* 발생 여부
  - **판별 방식**: 정정 사유 및 전후 문맥에 대한 LLM 기반 분석

- **의무보유(보호예수) 현황 추적**
  - **데이터 소스**: Seibro *의무보유등록/반환정보*
  - **구조화 항목**: 의무보유 여부, 비율, 해제일, 설정 사유
  - **리스크 신호**: 보호예수 해제 시점 기반 Overhang 발생 가능성

- **거래량 및 등락률 이상 패턴 탐지**
  - **데이터 결합**: 개별종목 시세 데이터, 보호예수 정보
  - **시나리오 A**: 보호예수 해제 전후 대량 거래 및 가격 하락
  - **시나리오 B**: 보호예수 기간 중 비정상적 거래량 증가 또는 가격 상승
  - **통계 기준**: 최근 5일 평균 거래량·등락률을 최근 30일 기준과 비교

---

## 🏗️ 아키텍쳐
<img width="1139" alt="Architecture Diagram" src="https://github.com/user-attachments/assets/3a581fca-9575-424e-bbb7-02b0ee6465ea" />

## 🛠️ 기술 스택

### 🌐 Frontend
![Next.js](https://img.shields.io/badge/Next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

### 🤖 Agent / Backend
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0E76A8?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge)

### 🧠 DL Model
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![LSTM-AE](https://img.shields.io/badge/LSTM--Autoencoder-Deep_Learning?style=for-the-badge)

### 🔌 MCP
![FastMCP](https://img.shields.io/badge/FastMCP-MCP-orange?style=for-the-badge)

### 📊 Data Source
![DART](https://img.shields.io/badge/DART-Open_API-1E40AF?style=for-the-badge)
![KRX](https://img.shields.io/badge/KRX-Market_Data-2563EB?style=for-the-badge)
![SEIBro](https://img.shields.io/badge/SEIBro-Financial_Data-0F766E?style=for-the-badge)


---

## 🚀 실행 방법

### 사전 준비

*   **Python**: 3.9 이상
*   **Node.js**: 20.x 이상
*   **API Keys**: 프로젝트 루트 및 각 폴더(`front`, `agent`)의 `.env.example`을 참고하여 `.env` 파일을 생성하고 필요한 키를 입력하세요.

### 0. 프로젝트 복제 (Clone)
```bash
git clone https://github.com/banchan01/Freezent.git
```

### 1. MCP-SERVER 실행 (필수)
에이전트가 사용할 도구 서버를 먼저 실행합니다.
```bash
cd Freezent
pip install -r requirements.txt
cd agent/mcp-server-local
python mcp-server.py
```

### 2. Agent 서버 실행
메인 에이전트 서버를 실행합니다.
```bash
cd ../..  # Freezent 루트로 이동
python app.py
```

### 3. Frontend 실행
사용자 인터페이스를 실행합니다.
```bash
cd front
npm install
npm run dev
```

브라우저 주소창에 `http://localhost:3000`을 입력하여 Freezent를 시작하세요.

---

## 👥 팀 정보

**Team Freezent**

*   **김민찬** 
*   **김태균** 
