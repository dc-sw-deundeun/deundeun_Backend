class RecordRepository:
    def save(self, record) -> None:
        raise NotImplementedError

    def find_by_id(self, record_id: int):
        raise NotImplementedError

    def find_by_user_id(self, user_id: int):
        raise NotImplementedError

    def delete(self, record_id: int) -> None:
        raise NotImplementedError

    def save_file(self, checkup_file) -> None:
        raise NotImplementedError

    def find_metrics_by_record_id(self, record_id: int):
        raise NotImplementedError

    def save_metric_result(self, metric_result) -> None:
        raise NotImplementedError

    def save_meal_record(self, meal_record) -> None:
        raise NotImplementedError

    def find_meal_records_by_user_id(self, user_id: int):
        raise NotImplementedError
