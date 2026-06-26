from app.infrastructure.wearable.wearable_client import StubWearableClient, WearableClient


def get_wearable_client() -> WearableClient:
    """현재는 StubWearableClient만 제공한다.

    실제 데이터 동기화(앱 → 백엔드 push)는 후속 Phase에서 구현하며,
    그때 provider별 검증 클라이언트로 교체한다.
    """
    return StubWearableClient()
