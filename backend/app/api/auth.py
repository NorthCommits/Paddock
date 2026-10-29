from fastapi import APIRouter, Query, Request

from app.api.deps import ActorDep, DbDep, IdentityDep, PersonDep, client_ip
from app.schemas.auth import (
    HandleCheckOut,
    MeOut,
    OnboardIn,
    OnboardingOut,
    ProfileUpdate,
    UserOut,
)
from app.services import accounts

router = APIRouter(prefix="/v1", tags=["auth"])

# Sign up, sign in, email codes and password reset all happen in Neon Auth.
# These routes cover the Paddock side: picking a handle and reading the profile.


@router.get("/onboarding", response_model=OnboardingOut)
async def onboarding(db: DbDep, identity: IdentityDep):
    """Has this Neon user finished creating a Paddock account? If not, offer handle ideas."""
    exists = await accounts.find_by_neon(db, identity) is not None
    return OnboardingOut(
        needs_onboarding=not exists,
        email=identity.email,
        name=identity.name,
        suggestions=[] if exists else await accounts.suggest_handles(db, identity),
    )


@router.get("/handles/check", response_model=HandleCheckOut)
async def check_handle(
    identity: IdentityDep, db: DbDep, handle: str = Query(min_length=1, max_length=60)
):
    handle = handle.strip().lower()
    reason = accounts.handle_problem(handle)
    if reason is None and not await accounts.handle_is_free(db, handle):
        reason = "That handle is already taken"
    return HandleCheckOut(handle=handle, available=reason is None, reason=reason)


@router.post("/onboarding", status_code=201, response_model=UserOut)
async def finish_onboarding(body: OnboardIn, request: Request, db: DbDep, identity: IdentityDep):
    return await accounts.onboard(
        db,
        identity,
        handle=body.handle,
        display_name=body.display_name,
        ip=client_ip(request),
    )


@router.get("/me", response_model=MeOut)
async def me(actor: ActorDep):
    return MeOut(user=UserOut.model_validate(actor.user), scopes=sorted(actor.scopes))


@router.patch("/me", response_model=UserOut)
async def update_me(body: ProfileUpdate, request: Request, db: DbDep, actor: PersonDep):
    return await accounts.update_profile(
        db, actor.user, body.display_name, client_ip(request), theme=body.theme
    )
