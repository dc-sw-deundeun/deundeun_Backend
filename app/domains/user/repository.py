class UserRepository:
    def find_by_id(self, user_id: int):
        raise NotImplementedError

    def find_by_email(self, email: str):
        raise NotImplementedError

    def save(self, user) -> None:
        raise NotImplementedError

    def update(self, user) -> None:
        raise NotImplementedError

    def delete(self, user_id: int) -> None:
        raise NotImplementedError

    def exists_by_email(self, email: str) -> bool:
        raise NotImplementedError
