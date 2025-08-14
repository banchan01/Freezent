# **Freezent: 멀티 에이전트 기반 주가 조작 및 불공정 거래 탐지 시스템**

**AI 기반의 지능형 불공정 거래 분석 및 리포팅 플랫폼**

![KB_s_kr3.png](front/public/KB_s_kr3.png)

## 📜 개요

**Freezent**는 점차 지능화되고 복잡해지는 주가 조작 및 불공정 거래 행위에 대응하기 위해 개발된 멀티 에이전트 기반 분석 시스템입니다. 여러 전문 에이전트가 각자의 역할을 수행하며 데이터를 수집 및 분석하고, 오케스트레이터(Orchestrator)가 이 결과들을 종합하여 최종적으로 투자자에게 신뢰도 높은 분석 리포트를 제공합니다.

본 시스템은 단순히 과거 데이터를 분석하는 것을 넘어, 공시, 뉴스, 기업 정보, 기술적 지표 등 다양한 비정형/정형 데이터를 실시간으로 분석하여 잠재적인 이상 징후를 포착하는 것을 목표로 합니다.

## ✨ 주요 기능

*   **멀티 에이전트 시스템 (Multi-Agent System)**
    *   **뉴스 분석 에이전트**: 최신 뉴스를 분석하여 기업 관련 호재/악재 및 시장 센티멘트를 파악합니다.
    *   **공시 분석 에이전트**: DART 공시를 분석하여 유상증자, 보호예수, 실적 발표 등 주가에 영향을 미치는 주요 이벤트를 감지합니다.
    *   **LSTM-AE 기반 이상 탐지 에이전트**: 주가 및 거래량 시계열 데이터를 LSTM-Autoencoder 앙상블 모델로 분석하여 비정상적인 거래 패턴을 탐지합니다.

*   **종합 분석 리포트 생성**
    *   각 에이전트가 분석한 내용을 종합하여, 최종적으로 투자자가 이해하기 쉬운 형태의 종합 리포트를 생성합니다.
    *   Markdown 형식으로 리포트를 제공하여 가독성과 확장성을 높였습니다.

*   **대화형 UI/UX**
    *   사용자는 간단한 검색을 통해 원하는 종목의 분석 리포트를 요청하고 확인할 수 있습니다.
    *   Next.js 기반의 반응형 웹 인터페이스를 제공하여 사용자 편의성을 극대화했습니다.

## 🏗️ 시스템 아키텍처

Freezent는 명확하게 분리된 4개의 핵심 파트(Frontend, Backend, Agent, Model)로 구성되어 있습니다.

```
[Frontend] <=> [Backend] <=> [Agent System] <=> [ML Model]
```

1.  **Frontend (Next.js, TypeScript)**
    *   사용자 인터페이스(UI/UX)를 담당합니다.
    *   사용자로부터 분석 대상 기업명을 입력받아 백엔드에 API 요청을 보냅니다.
    *   백엔드로부터 받은 최종 분석 리포트를 Markdown 뷰어를 통해 시각화합니다.

2.  **Backend (Python, FastAPI)**
    *   프론트엔드와 에이전트 시스템 간의 API 게이트웨이 역할을 수행합니다.
    *   프론트엔드의 요청을 받아 에이전트 시스템의 오케스트레이터에게 작업을 위임합니다.
    *   에이전트 시스템으로부터 받은 최종 결과를 프론트엔드에 전달합니다.

3.  **Agent System (Python, LangChain-like ReWOO Architecture)**
    *   **Orchestrator (`meta_planner`, `fusion_solver`)**: 시스템의 두뇌 역할을 합니다. 사용자 쿼리를 해석하여 가장 적합한 에이전트들에게 작업을 분배하고, 각 에이전트로부터 받은 결과를 종합(Fusion)하여 최종 리포트를 생성합니다.
    *   **Specialized Agents (`news_rewoo`, `filings_rewoo`, `lstm_agent`)**: 특정 도메인에 특화된 에이전트입니다. 각 에이전트는 `Planner`, `Worker`, `Solver`의 구조를 가집니다.
        *   **Planner**: 작업 계획을 수립합니다.
        *   **Worker**: 계획에 따라 실제 도구(Tools)를 사용하여 데이터를 수집하고 분석합니다.
        *   **Solver**: Worker의 실행 결과를 바탕으로 중간 결론을 도출합니다.
    *   **Tools**: 각 에이전트가 사용하는 기능 모음입니다. (예: 뉴스 검색, 공시 정보 조회, 보호예수 물량 조회, LSTM 모델 추론 등)

4.  **ML Model (PyTorch, LSTM-Autoencoder Ensemble)**
    *   주가, 거래량 등 시계열 데이터의 이상 패턴을 탐지하는 딥러닝 모델입니다.
    *   여러 개의 LSTM-AE 모델을 앙상블하여 탐지 성능과 안정성을 높였습니다.
    *   Agent System의 `lstm_model_tool`을 통해 모델의 추론 기능이 제공됩니다.

## 🛠️ 기술 스택

*   **Frontend**: `Next.js`, `React`, `TypeScript`, `Tailwind CSS`
*   **Backend**: `Python`, `FastAPI`
*   **Agent/AI**: `Python`, ReWOO (Reasoning WithOut Observation) Agent Architecture, `Pydantic`
*   **ML Model**: `PyTorch`, `LSTM-Autoencoder`
*   **Data Source**: DART API, Naver News API, KRX DATA

## 🚀 실행 방법

### 사전 준비

*   Python 3.9+
*   Node.js 20.x+
*   각 폴더(`front`, `back`, `agent`)의 `.env.example` 파일을 `.env` 파일로 복사하고, 필요한 API 키 및 환경 변수를 설정하세요.

### 1. Backend 실행

```bash
cd back
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Agent 실행

```bash
cd agent
pip install -r requirements.txt
python main.py
```

### 3. Frontend 실행

```bash
cd front
npm install
npm run dev
```

이제 브라우저에서 `http://localhost:3000`으로 접속하여 시스템을 사용할 수 있습니다.

## 👥 팀 정보

*   **팀명**: Freezent
*   **팀원**: [팀원 이름], [팀원 이름], ...
