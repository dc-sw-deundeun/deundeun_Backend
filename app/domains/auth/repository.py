class AuthRepository:
    def find_user_by_email(self, email: str):
        raise NotImplementedError

    def save_user(self, user) -> None:
        raise NotImplementedError

    def save_email_token(self, token) -> None:
        raise NotImplementedError

    def find_email_token(self, token: str):
        raise NotImplementedError

    def save_password_reset_token(self, token) -> None:
        raise NotImplementedError

    def find_password_reset_token(self, token: str):
        raise NotImplementedError

    def save_refresh_token(self, token) -> None:
        raise NotImplementedError

    def delete_refresh_token(self, user_id: int) -> None:
        raise NotImplementedError
