from pydantic import BaseModel
from typing import Optional, List


class StockIdentifier(BaseModel):
    """주식 식별자 모델 (종목명 또는 종목코드)"""

    stock_name: Optional[str] = None
    stock_code: Optional[str] = None


class CorpCodeRequest(BaseModel):
    """고유번호 조회 요청 모델"""

    identifier: StockIdentifier


class CorpInfo(BaseModel):
    """기업 정보 모델"""

    corp_code: str
    corp_name: str
    corp_eng_name: Optional[str] = None
    stock_code: Optional[str] = None
    modify_date: Optional[str] = None


class CorpCodeResponse(BaseModel):
    """고유번호 조회 응답 모델"""

    success: bool
    corp_code: Optional[str] = None
    corp_name: Optional[str] = None
    corp_eng_name: Optional[str] = None
    stock_code: Optional[str] = None
    modify_date: Optional[str] = None
    error: Optional[str] = None


class DownloadResponse(BaseModel):
    """다운로드 응답 모델"""

    success: bool
    message: Optional[str] = None
    path: Optional[str] = None
    error: Optional[str] = None
    status: Optional[int] = None


# 최대주주 현황 관련 모델
class MajorShareholderResponse(BaseModel):
    """최대주주 현황 API 응답 모델"""

    status: str
    message: str
    trmend_posesn_stock_qota_rt: float  # 기말 소유 주식 지분율


class FloatingStockResponse(BaseModel):
    """유동주식 비율 계산 응답 모델"""

    success: bool
    floating_ratio: Optional[float] = None  # 현재 유동주식 비율
    deviation_from_average: Optional[float] = None  # 평균 대비 차이
    is_above_average: Optional[bool] = None  # 평균보다 큰지 여부
    error: Optional[str] = None
