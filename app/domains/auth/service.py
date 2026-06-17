class AuthService:
    def signup(self, request) -> None:
        """회원가입을 처리합니다."""
        raise NotImplementedError

    def login(self, request) -> None:
        """로그인을 처리하고 JWT 토큰을 반환합니다."""
        raise NotImplementedError

    def logout(self, user_id: int) -> None:
        """로그아웃하고 refresh token을 무효화합니다."""
        raise NotImplementedError

    def refresh_token(self, refresh_token: str) -> None:
        """Refresh token으로 새 access token을 발급합니다."""
        raise NotImplementedError

    def request_email_verification(self, email: str) -> None:
        """이메일 인증 토큰을 발송합니다."""
        raise NotImplementedError

    def confirm_email_verification(self, token: str) -> None:
        """이메일 인증 토큰을 검증합니다."""
        raise NotImplementedError

    def request_password_reset(self, email: str) -> None:
        """비밀번호 재설정 이메일을 발송합니다."""
        raise NotImplementedError

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        """비밀번호를 재설정합니다."""
        raise NotImplementedError
