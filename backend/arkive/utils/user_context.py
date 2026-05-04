import logging
import time
from dataclasses import dataclass
from typing import Optional

from arkive.models.usage_policies import UsagePolicies
from arkive.models.user_policies import UserPolicies

log = logging.getLogger(__name__)


####################
# UserContext
#
# Resolved per-request view combining the base user record with their
# user_policy row and (optionally) the linked usage_policy bundle.
# Layer 2 checks (classification, access, policy) read from this object
# instead of re-querying on every hop.
####################


@dataclass
class UserContext:
    user_id: str
    email: str
    role: str  # 'admin', 'user', 'reviewer'
    department: Optional[str]
    clearance_level: int  # 0=public, 1=internal, 2=confidential, 3=restricted
    region: Optional[str]
    usage_policy_id: Optional[str]
    allowed_collection_ids: list[str]
    can_export: bool
    can_upload: bool
    requires_review_above_clearance: int
    is_admin: bool


# Safe defaults applied when no user_policy row exists for a user.
_DEFAULT_CLEARANCE = 0
_DEFAULT_CAN_EXPORT = False
_DEFAULT_CAN_UPLOAD = True
_DEFAULT_REVIEW_THRESHOLD = 2
_ADMIN_CLEARANCE = 3


async def resolve_user_context(user) -> UserContext:
    is_admin = user.role == 'admin'

    policy = UserPolicies.get_user_policy_by_user_id(user_id=user.id)

    if policy is None:
        department = None
        clearance_level = _DEFAULT_CLEARANCE
        region = None
        usage_policy_id = None
        allowed_collection_ids: list[str] = []
        can_export = _DEFAULT_CAN_EXPORT
        can_upload = _DEFAULT_CAN_UPLOAD
        requires_review_above_clearance = _DEFAULT_REVIEW_THRESHOLD
    else:
        department = policy.department
        clearance_level = policy.clearance_level
        region = policy.region
        usage_policy_id = (
            str(policy.usage_policy_id) if policy.usage_policy_id else None
        )
        allowed_collection_ids = list(policy.allowed_collection_ids)
        can_export = policy.can_export
        can_upload = policy.can_upload
        requires_review_above_clearance = _DEFAULT_REVIEW_THRESHOLD

        if policy.usage_policy_id is not None:
            usage_policy = UsagePolicies.get_usage_policy_by_id(
                id=policy.usage_policy_id
            )
            if usage_policy is not None:
                can_export = usage_policy.can_export
                can_upload = usage_policy.can_upload
                requires_review_above_clearance = (
                    usage_policy.requires_review_above_clearance
                )

    # Admins bypass stored clearance — they always see everything.
    if is_admin:
        clearance_level = _ADMIN_CLEARANCE

    return UserContext(
        user_id=user.id,
        email=user.email,
        role=user.role,
        department=department,
        clearance_level=clearance_level,
        region=region,
        usage_policy_id=usage_policy_id,
        allowed_collection_ids=allowed_collection_ids,
        can_export=can_export,
        can_upload=can_upload,
        requires_review_above_clearance=requires_review_above_clearance,
        is_admin=is_admin,
    )


####################
# In-process cache
#
# Per-worker dict. Cache key is user.id. Callers MUST invalidate on any
# user_policy or usage_policy update so stale entries don't outlive the
# mutation. TTL is a backstop, not the primary consistency mechanism.
####################


_context_cache: dict[str, tuple[UserContext, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


async def get_user_context(user) -> UserContext:
    now = time.time()
    cached = _context_cache.get(user.id)
    if cached is not None:
        ctx, stored_at = cached
        if now - stored_at < CACHE_TTL_SECONDS:
            return ctx

    ctx = await resolve_user_context(user)
    _context_cache[user.id] = (ctx, now)
    return ctx


async def invalidate_user_context(user_id: str) -> None:
    _context_cache.pop(user_id, None)
