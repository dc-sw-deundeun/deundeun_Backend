"""분석 결과 수신 워커입니다. Callback과 Polling 두 경로를 모두 stub으로 준비합니다."""


async def handle_analysis_callback(payload: dict) -> None:
    """분석 서버 callback 수신 시 AnalysisService.handle_callback()을 호출합니다."""
    raise NotImplementedError


async def poll_analysis_results() -> None:
    """PROCESSING 상태 Job을 주기적으로 조회합니다. (팀 결정 전 placeholder)"""
    raise NotImplementedError
