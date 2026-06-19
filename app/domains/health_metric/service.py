class HealthMetricService:
    def get_reference(self, metric_code: str):
        """건강 항목 기준값·설명을 조회합니다."""
        raise NotImplementedError

    def build_metric_detail(self, record_id: int, metric_code: str):
        """CheckupMetricResult + HealthMetricReference + AnalysisSummary를 조합합니다."""
        raise NotImplementedError
