class HomeService:
    """홈 화면용 Aggregation Service입니다. DB 모델 없이 각 도메인 서비스를 조합합니다."""

    def get_home(self, user_id: int):
        """홈 메인 데이터를 반환합니다.

        조합 대상:
        - UserService: 사용자 정보
        - CharacterService: 캐릭터 상태
        - MissionService: 오늘의 미션 요약
        - RecordService: 최근 검진 기록 요약
        - NotificationService: 알림 요약
        """
        raise NotImplementedError

    def get_summary(self, user_id: int):
        """홈 요약 데이터를 반환합니다."""
        raise NotImplementedError
