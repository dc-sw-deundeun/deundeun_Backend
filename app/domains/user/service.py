class UserService:
    def get_profile(self, user_id: int):
        raise NotImplementedError

    def update_profile(self, user_id: int, request) -> None:
        raise NotImplementedError

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        raise NotImplementedError

    def delete_account(self, user_id: int) -> None:
        raise NotImplementedError
