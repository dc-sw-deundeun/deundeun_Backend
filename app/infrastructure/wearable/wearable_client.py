from dataclasses import dataclass
from typing import Protocol


@dataclass
class WearableConnectResult:
    """웨어러블 연결 시도 결과."""

    connected: bool
    scopes: list[str] | None = None


class WearableClient(Protocol):
    """웨어러블/헬스 플랫폼 연동 인터페이스.

    Apple Health(HealthKit)는 서버용 API가 없어 실제 권한 처리는 앱이
    온디바이스에서 수행한다. 백엔드 클라이언트는 연결 상태 확정/검증과
    (후속 Phase의) 데이터 수신 경로를 추상화한다.
    """

    async def connect(
        self, user_id: int, provider: str, scopes: list[str] | None
    ) -> WearableConnectResult: ...


class StubWearableClient:
    """개발/테스트용 stub.

    앱이 전달한 연결 요청을 그대로 성공 처리한다. (실제 외부 호출 없음)
    """

    async def connect(
        self, user_id: int, provider: str, scopes: list[str] | None
    ) -> WearableConnectResult:
        return WearableConnectResult(connected=True, scopes=scopes)
