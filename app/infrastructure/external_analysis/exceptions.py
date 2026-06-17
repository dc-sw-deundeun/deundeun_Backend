class AnalysisServerException(Exception):
    """외부 분석 서버 통신 오류입니다."""

    def __init__(self, message: str = "분석 서버 통신에 실패했습니다.") -> None:
        self.message = message
        super().__init__(message)


class AnalysisTimeoutException(AnalysisServerException):
    def __init__(self) -> None:
        super().__init__("분석 서버 응답 시간이 초과되었습니다.")


class AnalysisJobNotFoundException(AnalysisServerException):
    def __init__(self, external_job_id: str) -> None:
        super().__init__(f"분석 Job을 찾을 수 없습니다: {external_job_id}")
