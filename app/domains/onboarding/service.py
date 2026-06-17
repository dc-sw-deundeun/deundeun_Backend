class OnboardingService:
    def get_status(self, user_id: int):
        raise NotImplementedError

    def submit_initial_checkup(self, user_id: int, request) -> None:
        raise NotImplementedError

    def connect_wearable(self, user_id: int, request) -> None:
        raise NotImplementedError

    def complete_onboarding(self, user_id: int) -> None:
        raise NotImplementedError
