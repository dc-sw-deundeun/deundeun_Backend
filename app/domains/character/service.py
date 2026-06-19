class CharacterService:
    def get_my_character(self, user_id: int):
        raise NotImplementedError

    def gain_exp(self, user_id: int, amount: int, reason: str) -> None:
        """경험치를 획득합니다. 레벨·스테이지 업 조건을 내부에서 처리합니다.

        MissionService, RecordService에서 내부 호출합니다.
        클라이언트가 직접 호출하지 않도록 설계합니다.
        """
        raise NotImplementedError

    def update_stage(self, user_id: int, stage: int) -> None:
        raise NotImplementedError
