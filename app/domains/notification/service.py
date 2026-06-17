class NotificationService:
    def list_notifications(self, user_id: int):
        raise NotImplementedError

    def get_settings(self, user_id: int):
        raise NotImplementedError

    def update_settings(self, user_id: int, request) -> None:
        raise NotImplementedError

    def create_log(self, user_id: int, notification_type: str, channel: str, title: str, content: str) -> None:
        raise NotImplementedError

    def send_test_notification(self, user_id: int) -> None:
        raise NotImplementedError
