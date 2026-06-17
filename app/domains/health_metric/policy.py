def classify_metric_status(value: float, reference_min: float, reference_max: float) -> str:
    """수치와 기준값을 비교해 상태(NORMAL/CAUTION/DANGER)를 반환합니다."""
    raise NotImplementedError
