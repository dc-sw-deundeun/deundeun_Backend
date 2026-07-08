"""Seed demo accounts for frontend smoke testing.

Run inside the API container after migrations:
docker compose --env-file /opt/deundeun/.env -f /opt/deundeun/docker-compose.yml \
  --profile deploy run --rm api python scripts/seed_demo_data.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.session import session_scope
from app.domains.auth.models import EmailVerification, RefreshToken
from app.domains.character import policy as character_policy
from app.domains.character.models import (
    CharacterGrowthLog,
    CharacterOwnedAnimal,
    CharacterProfile,
)
from app.domains.health_metric.models import HealthMetricAnalysis
from app.domains.mission.models import MissionGenerationRun, UserMission
from app.domains.mission.policy import local_date_for_timezone
from app.domains.notification.models import Notification, NotificationPreference
from app.domains.onboarding.models import WearableConnection, WearableStatus
from app.domains.pkg.models import PkgSnapshot
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.domains.user.models import OnboardingStep, User, UserStatus

DEMO_PASSWORD = "Demo1234!"
DEMO_EMAILS = (
    "demo-new@demo.deundeun.xyz",
    "demo-user@demo.deundeun.xyz",
    "demo-growth@demo.deundeun.xyz",
)


@dataclass(frozen=True)
class MetricSeed:
    code: str
    name: str
    value: str
    unit: str | None
    status: str
    reference_min: float | None = None
    reference_max: float | None = None


RECENT_METRICS = (
    MetricSeed("systolic_bp", "수축기혈압", "150", "mmHg", "risk", 90, 120),
    MetricSeed("fasting_glucose", "공복혈당", "130", "mg/dL", "risk", 70, 100),
    MetricSeed("ldl", "LDL 콜레스테롤", "160", "mg/dL", "risk", None, 130),
    MetricSeed("bmi", "체질량지수", "27.2", "kg/m2", "caution", 18.5, 24.9),
)
PAST_METRICS = (
    MetricSeed("systolic_bp", "수축기혈압", "128", "mmHg", "caution", 90, 120),
    MetricSeed("fasting_glucose", "공복혈당", "108", "mg/dL", "caution", 70, 100),
    MetricSeed("ldl", "LDL 콜레스테롤", "142", "mg/dL", "caution", None, 130),
    MetricSeed("bmi", "체질량지수", "26.1", "kg/m2", "caution", 18.5, 24.9),
)


def main() -> None:
    with session_scope() as db:
        users = {
            email: _upsert_user(db, email=email, nickname=nickname, step=step)
            for email, nickname, step in (
                ("demo-new@demo.deundeun.xyz", "신규데모", OnboardingStep.CONSENT.value),
                ("demo-user@demo.deundeun.xyz", "든든데모", OnboardingStep.COMPLETED.value),
                ("demo-growth@demo.deundeun.xyz", "성장데모", OnboardingStep.COMPLETED.value),
            )
        }

        db.execute(delete(EmailVerification).where(EmailVerification.email.in_(DEMO_EMAILS)))
        for user in users.values():
            _clear_demo_user_data(db, user.id)

        _seed_demo_new(db, users["demo-new@demo.deundeun.xyz"])
        _seed_demo_user(db, users["demo-user@demo.deundeun.xyz"])
        _seed_demo_growth(db, users["demo-growth@demo.deundeun.xyz"])

        db.commit()

    print("Seeded demo data:")
    for email in DEMO_EMAILS:
        print(f"- {email} / {DEMO_PASSWORD}")


def _upsert_user(db: Session, *, email: str, nickname: str, step: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(DEMO_PASSWORD),
            nickname=nickname,
            onboarding_step=step,
            timezone="Asia/Seoul",
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
        return user

    user.password_hash = hash_password(DEMO_PASSWORD)
    user.nickname = nickname
    user.onboarding_step = step
    user.timezone = "Asia/Seoul"
    user.status = UserStatus.ACTIVE
    db.flush()
    return user


def _clear_demo_user_data(db: Session, user_id: int) -> None:
    record_ids = list(db.scalars(select(CheckupRecord.id).where(CheckupRecord.user_id == user_id)))
    analysis_ids = list(
        db.scalars(select(HealthMetricAnalysis.id).where(HealthMetricAnalysis.user_id == user_id))
    )
    if record_ids:
        db.execute(delete(CheckupMetricResult).where(CheckupMetricResult.record_id.in_(record_ids)))
        db.execute(delete(CheckupRecord).where(CheckupRecord.id.in_(record_ids)))
    if analysis_ids:
        db.execute(delete(HealthMetricAnalysis).where(HealthMetricAnalysis.id.in_(analysis_ids)))

    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    for model in (
        UserMission,
        MissionGenerationRun,
        PkgSnapshot,
        Notification,
        NotificationPreference,
        WearableConnection,
        CharacterProfile,
    ):
        db.execute(delete(model).where(model.user_id == user_id))
    db.flush()


def _seed_demo_new(db: Session, user: User) -> None:
    _seed_notification_preference(db, user.id)


def _seed_demo_user(db: Session, user: User) -> None:
    now = datetime.now(UTC)
    today = local_date_for_timezone(user.timezone)

    _seed_notification_preference(db, user.id, mission=True, record=True, email=False, push=True)
    _seed_wearable(db, user.id, "SAMSUNG_HEALTH")

    past_record = _seed_checkup(
        db,
        user.id,
        measured_at=now - timedelta(days=38),
        metrics=PAST_METRICS,
    )
    recent_record = _seed_checkup(
        db,
        user.id,
        measured_at=now - timedelta(days=3),
        metrics=RECENT_METRICS,
    )
    _seed_health_analysis(db, user.id, recent_record.id, measured_at=recent_record.measured_at)
    _seed_pkg_snapshot(db, user.id, recent_record.id)
    _seed_character(db, user.id, total_exp=120)
    _seed_missions(db, user.id, today=today, completed_today=1)
    _seed_notifications(db, user.id)

    past_record.analysis_status = "COMPLETED"
    recent_record.analysis_status = "COMPLETED"


def _seed_demo_growth(db: Session, user: User) -> None:
    now = datetime.now(UTC)
    today = local_date_for_timezone(user.timezone)

    _seed_notification_preference(db, user.id, mission=True, record=False, email=True, push=True)
    _seed_wearable(db, user.id, "APPLE_HEALTH")
    record = _seed_checkup(
        db,
        user.id,
        measured_at=now - timedelta(days=8),
        metrics=(
            MetricSeed("systolic_bp", "수축기혈압", "118", "mmHg", "normal", 90, 120),
            MetricSeed("fasting_glucose", "공복혈당", "94", "mg/dL", "normal", 70, 100),
            MetricSeed("ldl", "LDL 콜레스테롤", "118", "mg/dL", "normal", None, 130),
            MetricSeed("bmi", "체질량지수", "23.4", "kg/m2", "normal", 18.5, 24.9),
        ),
    )
    record.analysis_status = "COMPLETED"
    _seed_health_analysis(
        db,
        user.id,
        record.id,
        measured_at=record.measured_at,
        title="건강 습관이 안정적으로 유지되고 있어요",
        summary="대부분의 지표가 정상 범위입니다. 현재 루틴을 유지해 주세요.",
        normal_count=4,
        caution_count=0,
        risk_count=0,
    )
    _seed_pkg_snapshot(db, user.id, record.id, conditions=["hypertension"])
    _seed_character(db, user.id, total_exp=1600)
    _seed_missions(db, user.id, today=today, completed_today=2)
    _seed_notifications(
        db,
        user.id,
        include_analysis=True,
        include_level_up=True,
        unread_level_up=True,
    )


def _seed_notification_preference(
    db: Session,
    user_id: int,
    *,
    mission: bool = True,
    record: bool = True,
    email: bool = True,
    push: bool = True,
) -> None:
    db.add(
        NotificationPreference(
            user_id=user_id,
            mission_alarm_enabled=mission,
            record_alarm_enabled=record,
            email_alarm_enabled=email,
            push_alarm_enabled=push,
        )
    )


def _seed_wearable(db: Session, user_id: int, provider: str) -> None:
    db.add(
        WearableConnection(
            user_id=user_id,
            provider=provider,
            status=WearableStatus.CONNECTED.value,
            scopes=["steps", "sleep", "heart_rate"],
            last_synced_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )


def _seed_checkup(
    db: Session,
    user_id: int,
    *,
    measured_at: datetime,
    metrics: tuple[MetricSeed, ...],
) -> CheckupRecord:
    record = CheckupRecord(
        user_id=user_id,
        source_type="MANUAL",
        measured_at=measured_at,
        ocr_status="COMPLETED",
        verification_status="VERIFIED",
        verified_at=measured_at + timedelta(minutes=10),
        analysis_status="COMPLETED",
    )
    db.add(record)
    db.flush()
    for metric in metrics:
        db.add(
            CheckupMetricResult(
                record_id=record.id,
                metric_code=metric.code,
                metric_name=metric.name,
                value=metric.value,
                unit=metric.unit,
                status=metric.status.upper(),
                reference_min=metric.reference_min,
                reference_max=metric.reference_max,
                source="MANUAL",
                confidence=1.0,
                is_edited=False,
            )
        )
    db.flush()
    return record


def _seed_health_analysis(
    db: Session,
    user_id: int,
    record_id: int,
    *,
    measured_at: datetime | None,
    title: str = "주의가 필요한 건강 지표가 있어요",
    summary: str = "혈압, 혈당, LDL 지표가 관리 범위 밖에 있어 생활 습관 점검이 필요합니다.",
    normal_count: int = 0,
    caution_count: int = 1,
    risk_count: int = 3,
) -> HealthMetricAnalysis:
    results = [
        _analysis_result("수축기혈압", "BP_SYS", "수축기혈압", 150, "mmHg", "risk"),
        _analysis_result("공복혈당", "FPG", "공복혈당", 130, "mg/dL", "risk"),
        _analysis_result("LDL 콜레스테롤", "LDL", "LDL", 160, "mg/dL", "risk"),
        _analysis_result("체질량지수", "BMI", "BMI", 27.2, "kg/m2", "caution"),
    ]
    if normal_count:
        results = [
            _analysis_result("수축기혈압", "BP_SYS", "수축기혈압", 118, "mmHg", "normal"),
            _analysis_result("공복혈당", "FPG", "공복혈당", 94, "mg/dL", "normal"),
            _analysis_result("LDL 콜레스테롤", "LDL", "LDL", 118, "mg/dL", "normal"),
            _analysis_result("체질량지수", "BMI", "BMI", 23.4, "kg/m2", "normal"),
        ]

    analysis = HealthMetricAnalysis(
        user_id=user_id,
        record_id=record_id,
        sex="male",
        measured_at=measured_at,
        overall_title=title,
        overall_summary=summary,
        normal_count=normal_count,
        caution_count=caution_count,
        risk_count=risk_count,
        unknown_count=0,
        explanation_status="generated",
        disclaimer="본 분석은 건강 관리 참고용이며 진단을 대체하지 않습니다.",
        request_payload={},
        results_payload=results,
        explanation_payload={
            "status": "generated",
            "summary": summary,
            "highlights": ["혈압과 혈당을 우선 관리해 주세요.", "식후 가벼운 걷기를 권장합니다."],
            "item_explanations": [
                {
                    "canonical_test_code": item["canonical_test_code"],
                    "input_label": item["input_label"],
                    "title": item["name"],
                    "explanation": f"{item['name']} 지표를 확인해 주세요.",
                    "status_label": item["status_label"],
                }
                for item in results
            ],
            "disclaimer": "본 분석은 건강 관리 참고용이며 진단을 대체하지 않습니다.",
        },
        summary_payload={
            "analysis_id": None,
            "overall": {
                "title": title,
                "summary": summary,
                "counts": {
                    "normal": normal_count,
                    "caution": caution_count,
                    "risk": risk_count,
                    "unknown": 0,
                },
            },
            "cards": [
                {
                    "code": item["canonical_test_code"],
                    "label": item["name"] or item["input_label"],
                    "value": item["value"],
                    "unit": item["unit"],
                    "status": item["status"],
                    "status_label": item["status_label"],
                    "value_text": f"{item['value']:g}{item['unit'] or ''}",
                    "badge_text": item["status_label"],
                    "range_bar": None,
                }
                for item in results
            ],
        },
        details_payload=[],
    )
    db.add(analysis)
    db.flush()
    return analysis


def _analysis_result(
    input_label: str,
    code: str,
    name: str,
    value: float,
    unit: str,
    status: str,
) -> dict:
    return {
        "input_label": input_label,
        "canonical_test_code": code,
        "name": name,
        "value": value,
        "unit": unit,
        "status": status,
        "status_label": {"normal": "정상", "caution": "주의", "risk": "위험"}[status],
        "matched_rule": "demo_seed",
        "note": None,
    }


def _seed_pkg_snapshot(
    db: Session,
    user_id: int,
    source_record_id: int,
    *,
    conditions: list[str] | None = None,
) -> None:
    condition_ids = conditions or ["hypertension", "type2_diabetes", "dyslipidemia"]
    labels = {
        "hypertension": "고혈압",
        "type2_diabetes": "제2형 당뇨병",
        "dyslipidemia": "이상지질혈증",
        "cardiovascular_disease": "심혈관질환",
    }
    nodes = [{"id": cid, "label": labels[cid], "type": "Disease"} for cid in condition_ids]
    nodes.append(
        {
            "id": "cardiovascular_disease",
            "label": labels["cardiovascular_disease"],
            "type": "Disease",
        }
    )
    db.add(
        PkgSnapshot(
            user_id=user_id,
            source_record_id=source_record_id,
            payload={
                "id": f"user-{user_id}",
                "name": "demo",
                "kind": "normal",
                "demographics": {"age": 42, "sex": "male"},
                "conditions": condition_ids,
                "medications": [],
                "wearable": {"steps_avg": 6400, "resting_hr": 68, "sleep_hours_avg": 6.7},
                "history": {"success_rate": 0.72, "recent_mission_titles": ["식후 15분 걷기"]},
                "nodes": nodes,
                "edges": [
                    {
                        "src": "hypertension",
                        "rel": "disease_disease",
                        "dst": "cardiovascular_disease",
                        "attrs": {"risk": "high"},
                    }
                ],
                "flags": {"cardiovascular_risk": True},
                "ground_truth": None,
            },
        )
    )


def _seed_character(db: Session, user_id: int, *, total_exp: int) -> None:
    level = character_policy.level_for_total_exp(total_exp)
    profile = CharacterProfile(user_id=user_id, level=level, total_exp=total_exp)
    db.add(profile)
    db.flush()

    before_total = 0
    for index, gained in enumerate((40, 80, 120, max(total_exp - 240, 0)), start=1):
        gained = min(gained, total_exp - before_total)
        if gained <= 0:
            continue
        after_total = before_total + gained
        db.add(
            CharacterGrowthLog(
                character_profile_id=profile.id,
                user_id=user_id,
                exp_gained=gained,
                before_level=character_policy.level_for_total_exp(before_total),
                after_level=character_policy.level_for_total_exp(after_total),
                before_total_exp=before_total,
                after_total_exp=after_total,
                reason="MISSION_COMPLETED",
                source="demo_seed",
                source_id=f"growth-{index}",
                note="프론트 데모용 성장 로그",
            )
        )
        before_total = after_total

    for animal in character_policy.animal_catalog_entries():
        if animal.unlock_level > level:
            continue
        db.add(
            CharacterOwnedAnimal(
                user_id=user_id,
                character_profile_id=profile.id,
                animal_code=animal.animal_code,
                unlocked_level=animal.unlock_level,
                unlocked_total_exp=animal.required_total_exp,
                unlocked_at=datetime.now(UTC) - timedelta(days=max(1, level - animal.unlock_level)),
            )
        )


def _seed_missions(
    db: Session,
    user_id: int,
    *,
    today,
    completed_today: int,
) -> None:
    today_payloads = [
        ("식후 15분 걷기", "exercise", "식후", 15),
        ("저녁 식사에서 채소 먼저 먹기", "diet", "저녁", None),
        ("잠들기 전 10분 스트레칭", "sleep", "취침 전", 10),
    ]
    for index, (title, mission_type, when, duration) in enumerate(today_payloads):
        status = "COMPLETED" if index < completed_today else "ASSIGNED"
        db.add(
            UserMission(
                user_id=user_id,
                template_id=None,
                assigned_date=today,
                status=status,
                xp_reward=0,
                template_code=f"demo_{mission_type}_{index}",
                payload=_mission_payload(title, mission_type, when, duration),
                completed_at=datetime.now(UTC) - timedelta(hours=index + 1)
                if status == "COMPLETED"
                else None,
            )
        )

    for day_offset in range(1, 31):
        assigned_date = today - timedelta(days=day_offset)
        for index, (title, mission_type, when, duration) in enumerate(today_payloads[:2]):
            completed = (day_offset + index) % 4 != 0
            db.add(
                UserMission(
                    user_id=user_id,
                    template_id=None,
                    assigned_date=assigned_date,
                    status="COMPLETED" if completed else "ASSIGNED",
                    xp_reward=0,
                    template_code=f"demo_history_{mission_type}_{index}",
                    payload=_mission_payload(title, mission_type, when, duration),
                    completed_at=datetime.now(UTC) - timedelta(days=day_offset)
                    if completed
                    else None,
                )
            )


def _mission_payload(
    title: str,
    mission_type: str,
    when: str,
    duration_min: int | None,
) -> dict:
    return {
        "title": title,
        "rationale": "데모 사용자의 건강 지표 관리를 위한 추천 미션입니다.",
        "grounded_on": ["고혈압->심혈관질환"],
        "execution": {"when": when, "duration_min": duration_min},
        "difficulty": 2,
        "mission_type": mission_type,
        "template_id": f"demo_{mission_type}",
        "source": "generated",
    }


def _seed_notifications(
    db: Session,
    user_id: int,
    *,
    include_analysis: bool = True,
    include_level_up: bool = True,
    unread_level_up: bool = False,
) -> None:
    now = datetime.now(UTC)
    if include_analysis:
        db.add(
            Notification(
                user_id=user_id,
                type="ANALYSIS_COMPLETED",
                title="건강 분석이 완료됐어요",
                body="건강 지표 분석 결과를 확인해 보세요.",
                deep_link="deundeun://health-metrics/analyses/demo",
                source="demo_seed",
                source_id="analysis-completed",
                read_at=None,
                created_at=now - timedelta(hours=3),
            )
        )
    if include_level_up:
        db.add(
            Notification(
                user_id=user_id,
                type="LEVEL_UP",
                title="캐릭터가 레벨업했어요",
                body="새로 열린 동물을 확인해 보세요.",
                deep_link="deundeun://characters/me",
                source="demo_seed",
                source_id="level-up",
                read_at=None if unread_level_up else now - timedelta(hours=1),
                created_at=now - timedelta(hours=2),
            )
        )


if __name__ == "__main__":
    main()
