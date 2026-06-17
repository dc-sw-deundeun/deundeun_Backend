from sqlalchemy import Column, Integer

from app.database.base import Base


class HealthMetricReference(Base):
    __tablename__ = "health_metric_references"

    id = Column(Integer, primary_key=True)
    # metric_code, metric_name, description, reference_min, reference_max, unit
    # recommendations, avoidances
