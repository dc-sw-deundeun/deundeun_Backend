from app.domains.auth.exceptions import InvalidTokenException
from app.domains.onboarding import policy
from app.domains.onboarding.exceptions import (
    OnboardingAlreadyCompletedException,
    OnboardingIncompleteException,
    WearableConnectionNotFoundException,
)
from app.domains.onboarding.hooks import on_onboarding_complete
from app.domains.onboarding.models import WearableProvider, WearableStatus
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.onboarding.schemas import (
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
    WearableAction,
    WearableConnectionItem,
    WearableConnectRequest,
    WearableConnectResponse,
    WearableDisconnectResponse,
)
from app.domains.user.models import OnboardingStep, User, UserStatus
from app.infrastructure.wearable.wearable_client import WearableClient


class OnboardingService:
    def __init__(self, repo: OnboardingRepository, wearable_client: WearableClient) -> None:
        self.repo = repo
        self.wearable_client = wearable_client

    def _require_active_user(self, user_id: int) -> User:
        user = self.repo.get_user_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()
        return user

    def get_status(self, user_id: int) -> OnboardingStatusResponse:
        user = self._require_active_user(user_id)
        connections = self.repo.list_wearable_connections(user_id)
        return OnboardingStatusResponse(
            onboarding_step=user.onboarding_step,
            is_completed=user.onboarding_step == OnboardingStep.COMPLETED.value,
            wearable_connections=[WearableConnectionItem.model_validate(c) for c in connections],
        )

    async def connect_wearable(
        self, user_id: int, request: WearableConnectRequest
    ) -> WearableConnectResponse:
        user = self._require_active_user(user_id)
        policy.ensure_step(user.onboarding_step, OnboardingStep.WEARABLE)

        connection_item: WearableConnectionItem | None = None

        if request.action == WearableAction.CONNECT:
            assert request.provider is not None  # 스키마 검증으로 보장됨
            result = await self.wearable_client.connect(
                user_id=user_id,
                provider=request.provider.value,
                scopes=request.scopes,
            )
            status = WearableStatus.CONNECTED if result.connected else WearableStatus.ERROR
            connection = self.repo.upsert_wearable_connection(
                user_id=user_id,
                provider=request.provider.value,
                status=status.value,
                scopes=result.scopes,
            )
            connection_item = WearableConnectionItem.model_validate(connection)

        user.onboarding_step = OnboardingStep.INITIAL_CHECKUP
        self.repo.db.commit()
        return WearableConnectResponse(
            onboarding_step=OnboardingStep.INITIAL_CHECKUP.value,
            connection=connection_item,
        )

    def disconnect_wearable(
        self, user_id: int, provider: WearableProvider
    ) -> WearableDisconnectResponse:
        user = self._require_active_user(user_id)
        deleted = self.repo.delete_wearable_connection(user_id, provider.value)
        if not deleted:
            raise WearableConnectionNotFoundException()

        remaining = self.repo.list_wearable_connections(user_id)
        if user.onboarding_step == OnboardingStep.INITIAL_CHECKUP.value and not remaining:
            user.onboarding_step = OnboardingStep.WEARABLE

        self.repo.db.commit()
        return WearableDisconnectResponse(
            onboarding_step=user.onboarding_step,
            wearable_connections=[WearableConnectionItem.model_validate(c) for c in remaining],
        )

    def complete_onboarding(self, user_id: int) -> OnboardingCompleteResponse:
        user = self._require_active_user(user_id)

        if user.onboarding_step == OnboardingStep.COMPLETED.value:
            raise OnboardingAlreadyCompletedException()
        if user.onboarding_step != OnboardingStep.CHECKUP_VERIFIED.value:
            raise OnboardingIncompleteException(
                message="검진 결과 검증(CHECKUP_VERIFIED) 후에 온보딩을 완료할 수 있습니다."
            )

        user.onboarding_step = OnboardingStep.COMPLETED
        self.repo.db.commit()
        on_onboarding_complete(user_id)
        return OnboardingCompleteResponse(onboarding_step=OnboardingStep.COMPLETED.value)
