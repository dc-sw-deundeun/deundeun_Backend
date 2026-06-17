class RecordService:
    def upload_checkup(self, user_id: int, file, request) -> None:
        """검진 결과지를 업로드하고 분석 Job을 생성합니다.

        흐름:
        1. FileStorage에 결과지 저장
        2. CheckupRecord 생성
        3. AnalysisService.create_analysis_job() 호출
        4. MissionService.check_record_related_mission() (Phase 4)
        5. CharacterService.gain_exp() (Phase 4)
        """
        raise NotImplementedError

    def list_checkups(self, user_id: int):
        raise NotImplementedError

    def get_checkup(self, user_id: int, record_id: int):
        raise NotImplementedError

    def get_metrics(self, user_id: int, record_id: int):
        """검진 항목별 수치를 조회합니다."""
        raise NotImplementedError

    def delete_checkup(self, user_id: int, record_id: int) -> None:
        raise NotImplementedError

    def create_meal_record(self, user_id: int, request) -> None:
        raise NotImplementedError

    def list_meal_records(self, user_id: int):
        raise NotImplementedError
