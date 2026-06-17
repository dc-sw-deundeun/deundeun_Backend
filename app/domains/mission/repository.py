class MissionRepository:
    def find_today_by_user_id(self, user_id: int):
        raise NotImplementedError

    def find_user_mission(self, user_id: int, mission_id: int):
        raise NotImplementedError

    def update_completed(self, user_mission) -> None:
        raise NotImplementedError

    def find_by_user_and_date_range(self, user_id: int, start_date, end_date):
        raise NotImplementedError

    def save(self, mission) -> None:
        raise NotImplementedError

    def exists(self, mission_id: int) -> bool:
        raise NotImplementedError
