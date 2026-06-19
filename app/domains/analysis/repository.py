class AnalysisRepository:
    def save_job(self, job) -> None:
        raise NotImplementedError

    def find_job_by_id(self, job_id: int):
        raise NotImplementedError

    def find_job_by_external_id(self, external_job_id: str):
        raise NotImplementedError

    def update_job_status(self, job_id: int, status: str, error_message=None) -> None:
        raise NotImplementedError

    def save_summary(self, summary) -> None:
        raise NotImplementedError

    def find_summary_by_record_id(self, record_id: int):
        raise NotImplementedError

    def find_pending_jobs(self):
        raise NotImplementedError
