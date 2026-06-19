from sqlalchemy import Column, Integer

from app.database.base import Base


class CheckupRecord(Base):
    __tablename__ = "checkup_records"

    id = Column(Integer, primary_key=True)
    # user_id, source_type, file_url, measured_at, analysis_status, created_at, updated_at


class CheckupMetricResult(Base):
    __tablename__ = "checkup_metric_results"

    id = Column(Integer, primary_key=True)
    # record_id, metric_code, metric_name, value, unit, status
    # reference_min, reference_max, interpretation, created_at


class CheckupFile(Base):
    __tablename__ = "checkup_files"

    id = Column(Integer, primary_key=True)
    # record_id, file_url, file_type, created_at


class MealRecord(Base):
    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True)
    # user_id, image_url, recognized_result, verified_status, created_at
