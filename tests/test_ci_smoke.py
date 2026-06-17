"""CI 인프라 smoke test — pytest가 항상 exit 0으로 종료되도록 보장합니다."""


def test_ci_smoke() -> None:
    """CI 파이프라인이 정상적으로 pytest를 실행할 수 있는지 확인합니다."""
    assert True
