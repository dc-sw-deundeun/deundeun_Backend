def can_complete_mission(user_mission) -> bool:
    """미션 완료 가능 여부를 확인합니다."""
    raise NotImplementedError


def can_manually_complete(user_mission) -> bool:
    """수동 완료 가능 여부를 확인합니다."""
    raise NotImplementedError


def calculate_exp_reward(mission_type: str) -> int:
    """미션 타입에 따른 경험치 보상량을 계산합니다."""
    raise NotImplementedError


def calculate_weekly_statistics(user_missions: list) -> dict:
    """주간 미션 통계를 계산합니다."""
    raise NotImplementedError
