class AnalysisService:
    def create_analysis_job(self, record_id: int, user_id: int):
        """분석 Job을 생성하고 외부 분석 서버에 요청합니다.

        흐름:
        1. AnalysisJob 생성 (status=PENDING)
        2. AnalysisClient.request_analysis() 호출
        3. external_job_id 저장, status=PROCESSING
        """
        raise NotImplementedError

    def get_job_status(self, job_id: int):
        raise NotImplementedError

    def get_job_result(self, job_id: int):
        raise NotImplementedError

    def handle_callback(self, payload) -> None:
        """분석 서버 callback 수신 시 결과를 저장합니다."""
        raise NotImplementedError

    def poll_pending_jobs(self) -> None:
        """Polling worker용 — PROCESSING 상태 Job의 결과를 조회합니다."""
        raise NotImplementedError
