"""미션 생성 서비스 — API 없이 스케줄러/이벤트가 호출하는 순수 callable.

흐름: gen_log 원자 claim → 저장된 PKG 스냅샷 읽기(없으면 build) → MissionPipeline 실행
→ user_missions 인스턴스 저장 → gen_log 상태 기록. 유저·날짜당 멱등.
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.repository import MissionGenerationRunRepository, MissionRepository
from app.domains.mission.schemas import PKG, PipelineConfig
from app.domains.pkg.dependencies import build_pkg_service
from app.domains.pkg.repository import PkgRepository

logger = logging.getLogger(__name__)

# 생성 토글: 안전 템플릿(M1) + KAG 관계(M3) + 안전게이트·병원리퍼럴(M4) + 구조화 출력(M5).
_GEN_CONFIG = PipelineConfig(M1_template=True, M3_kag=True, M4_verify_gate=True, M5_structured=True)
_DAILY_N = 3


class MissionGenerationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._runs = MissionGenerationRunRepository(db)
        self._missions = MissionRepository(db)
        self._pkg_repo = PkgRepository(db)

    async def generate_for_user(
        self, user_id: int, target_date: date, *, source: str = "scheduler"
    ) -> bool:
        """유저·날짜 미션을 멱등 생성. 생성 시 True, 스킵(이미 있음/PKG 없음/실패) 시 False."""
        if not self._runs.try_claim(user_id, target_date, source=source):
            return False  # 이미 생성됨/진행 중 (다른 틱·인스턴스가 선점)

        try:
            pkg = self._load_pkg(user_id)
            if pkg is None:
                self._runs.mark(user_id, target_date, "skipped")
                self._db.commit()
                return False

            # history(완료율·최근 미션)는 동적 — 정적 스냅샷 대신 생성 시점 값으로 overlay.
            # success_rate<0.3이면 엔진이 미션 강도를 낮춘다(완료→다음 생성 피드백 루프).
            pkg.history = self._missions.build_history(user_id, today=target_date)

            exclude = set(self._missions.recent_template_codes(user_id, today=target_date))
            mission_set = await MissionPipeline().generate_missions(
                pkg, _GEN_CONFIG, n=_DAILY_N, exclude_template_ids=exclude
            )
            for mission in mission_set.missions:
                self._missions.save_generated_mission(
                    user_id=user_id, assigned_date=target_date, mission=mission
                )
            self._runs.mark(
                user_id, target_date, "generated", mission_count=len(mission_set.missions)
            )
            self._db.commit()
            return True
        except Exception:
            self._db.rollback()
            self._runs.mark(user_id, target_date, "failed", error_code="GENERATION_ERROR")
            self._db.commit()
            logger.warning("mission generation failed (user_id=%s)", user_id, exc_info=True)
            return False

    async def regenerate_for_checkup(self, user_id: int, target_date: date) -> bool:
        """새 검진 이벤트: PKG가 바뀌었으니 당일 미완료 미션을 무효화하고 재생성한다.

        완료분은 보존(이미 획득), 미완료(ASSIGNED)만 삭제하고 gen_log를 지워 claim을 다시 연 뒤
        새 PKG로 재생성한다. 재생성은 best-effort(generate_for_user가 실패를 흡수)다.
        """
        self._missions.delete_incomplete_for_date(user_id, target_date)
        self._runs.delete_for_date(user_id, target_date)
        self._db.commit()
        return await self.generate_for_user(user_id, target_date, source="event")

    def _load_pkg(self, user_id: int) -> PKG | None:
        """미리 빌드된 스냅샷을 우선 사용하고, 없으면 build_pkg(검증검진 없으면 None)."""
        snapshot = self._pkg_repo.get_by_user(user_id)
        if snapshot is not None:
            return PKG.model_validate(snapshot.payload)
        try:
            return build_pkg_service(self._db).build_pkg(user_id)
        except NotFoundException:
            return None
