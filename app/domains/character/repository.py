class CharacterRepository:
    def find_by_user_id(self, user_id: int):
        raise NotImplementedError

    def save(self, character) -> None:
        raise NotImplementedError

    def update(self, character) -> None:
        raise NotImplementedError

    def save_growth_log(self, log) -> None:
        raise NotImplementedError
