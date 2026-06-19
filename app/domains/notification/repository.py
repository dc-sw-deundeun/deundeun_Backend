class NotificationRepository:
    def find_logs_by_user_id(self, user_id: int):
        raise NotImplementedError

    def save_log(self, log) -> None:
        raise NotImplementedError

    def find_preference_by_user_id(self, user_id: int):
        raise NotImplementedError

    def save_preference(self, preference) -> None:
        raise NotImplementedError

    def find_push_token_by_user_id(self, user_id: int):
        raise NotImplementedError
