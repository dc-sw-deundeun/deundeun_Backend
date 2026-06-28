def can_delete_record(record) -> bool:
    """검진 기록 삭제 가능 여부. 소유권 검증은 RecordService에서 수행한다."""
    return record is not None
