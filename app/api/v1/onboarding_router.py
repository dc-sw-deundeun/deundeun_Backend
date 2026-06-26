from fastapi import APIRouter, Depends, Security

from app.core.dependencies import bearer_scheme, get_current_user, get_onboarding_service
from app.core.response import not_implemented_response, success_response
from app.domains.onboarding.schemas import WearableConnectRequest
from app.domains.onboarding.service import OnboardingService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/status",
    summary="온보딩 상태 조회",
    description="현재 온보딩 단계와 웨어러블 연결 상태를 반환합니다. Authorization 헤더 필요.",
    dependencies=[Security(bearer_scheme)],
)
def get_onboarding_status(
    current_user: CurrentUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    result = service.get_status(current_user.id)
    return success_response(data=result.model_dump(mode="json"))


@router.post(
    "/checkup",
    summary="초기 검진 업로드 (Phase 3 연동 예정)",
    description="최초 검진 기록 업로드는 검진 도메인(Phase 3)에서 처리합니다.",
)
async def submit_initial_checkup():
    return not_implemented_response()


@router.post(
    "/wearable",
    summary="웨어러블 연동 (CONNECT/SKIP)",
    description=(
        "앱이 온디바이스에서 Apple Health(HealthKit)/Health Connect 권한을 처리한 뒤 "
        "연결 결과를 전달합니다. SKIP도 가능하며, 처리 후 INITIAL_CHECKUP 단계로 전이됩니다. "
        "Authorization 헤더 필요."
    ),
    dependencies=[Security(bearer_scheme)],
)
async def connect_wearable(
    body: WearableConnectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    result = await service.connect_wearable(current_user.id, body)
    return success_response(
        message="웨어러블 단계를 처리했습니다.", data=result.model_dump(mode="json")
    )


@router.post(
    "/complete",
    summary="온보딩 완료",
    description="검진 검증(CHECKUP_VERIFIED) 이후 온보딩을 최종 완료합니다. Authorization 헤더 필요.",
    dependencies=[Security(bearer_scheme)],
)
def complete_onboarding(
    current_user: CurrentUser = Depends(get_current_user),
    service: OnboardingService = Depends(get_onboarding_service),
):
    result = service.complete_onboarding(current_user.id)
    return success_response(message="온보딩을 완료했습니다.", data=result.model_dump())
