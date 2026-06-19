class OnboardingRepository:
    def find_progress_by_user_id(self, user_id: int):
        raise NotImplementedError

    def save_progress(self, progress) -> None:
        raise NotImplementedError

    def save_initial_checkup(self, checkup) -> None:
        raise NotImplementedError

    def save_wearable_connection(self, connection) -> None:
        raise NotImplementedError
