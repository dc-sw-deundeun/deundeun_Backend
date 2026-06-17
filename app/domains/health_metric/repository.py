class HealthMetricRepository:
    def find_by_metric_code(self, metric_code: str):
        raise NotImplementedError

    def find_all(self):
        raise NotImplementedError

    def save(self, reference) -> None:
        raise NotImplementedError
