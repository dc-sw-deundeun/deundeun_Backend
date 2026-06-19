class MissionService:
    def get_today_missions(self, user_id: int):
        raise NotImplementedError

    def complete_mission(self, user_id: int, mission_id: int) -> None:
        """미션을 완료합니다.

        흐름:
        1. 미션 존재 여부 확인
        2. 해당 사용자의 미션인지 확인
        3. 이미 완료된 미션인지 확인
        4. 완료 상태로 변경
        5. CharacterService.gain_exp() 호출 (Phase 4에서 연결)
        6. NotificationService 로그 저장
        """
        raise NotImplementedError

    def verify_mission(self, user_id: int, mission_id: int) -> None:
        raise NotImplementedError

    def get_calendar(self, user_id: int):
        raise NotImplementedError

    def get_weekly_statistics(self, user_id: int):
        raise NotImplementedError

    def check_record_related_mission(self, user_id: int) -> None:
        """검진 등록 관련 미션을 확인하고 자동 완료합니다."""
        raise NotImplementedError
