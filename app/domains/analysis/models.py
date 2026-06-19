from sqlalchemy import Column, Integer

from app.database.base import Base


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(Integer, primary_key=True)
    # record_id, user_id, external_job_id, status, requested_at, completed_at, error_message, created_at


class CheckupAnalysisSummary(Base):
    __tablename__ = "checkup_analysis_summaries"

    id = Column(Integer, primary_key=True)
    # record_id, summary_text, risk_level, positive_points, caution_points, recommendations, avoidances, created_at
