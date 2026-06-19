class SupportRepository:
    def save(self, inquiry) -> None:
        raise NotImplementedError

    def find_by_user_id(self, user_id: int):
        raise NotImplementedError
