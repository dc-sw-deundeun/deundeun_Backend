# Alembic autogenerate를 위해 모든 SQLAlchemy 모델을 여기서 import합니다.
# 새 도메인 모델 추가 시 반드시 이 파일에도 import를 추가해야 합니다.

from app.domains.auth.models import (  # noqa: F401
    AccessTokenBlacklist,
    ConsentHistory,
    EmailVerification,
    RefreshToken,
)
from app.domains.health_metric.models import HealthMetricAnalysis, HealthMetricReference  # noqa: F401
from app.domains.user.models import User  # noqa: F401
