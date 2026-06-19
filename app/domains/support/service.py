class SupportService:
    def submit_inquiry(self, user_id: int, request) -> None:
        raise NotImplementedError

    def list_inquiries(self, user_id: int):
        raise NotImplementedError
