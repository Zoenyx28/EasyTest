"""ZenTao-inspired defect state machine.

States and transitions:
    unconfirmed -> confirm -> confirmed
    confirmed   -> assign  -> in_progress
    in_progress -> resolve -> resolved
    resolved    -> close   -> closed
    resolved    -> activate -> in_progress
    closed      -> activate -> in_progress
    confirmed   -> close   -> closed
    unconfirmed -> close   -> closed
"""
from __future__ import annotations

# ── States ──
STATUS_UNCONFIRMED = 'unconfirmed'
STATUS_CONFIRMED = 'confirmed'
STATUS_IN_PROGRESS = 'in_progress'
STATUS_RESOLVED = 'resolved'
STATUS_CLOSED = 'closed'

# ── Actions ──
ACTION_CONFIRM = 'confirm'    # unconfirmed -> confirmed
ACTION_ASSIGN = 'assign'      # confirmed -> in_progress
ACTION_RESOLVE = 'resolve'    # in_progress -> resolved
ACTION_CLOSE = 'close'        # resolved -> closed, confirmed -> closed, unconfirmed -> closed
ACTION_ACTIVATE = 'activate'  # resolved -> in_progress, closed -> in_progress

# ── Resolutions ──
RESOLUTIONS = ['fixed', 'duplicate', 'not_issue', 'cannot_reproduce', 'design', 'external', 'deferred']

# ── State machine valid transitions ──
TRANSITIONS = {
    STATUS_UNCONFIRMED: [ACTION_CONFIRM, ACTION_CLOSE],
    STATUS_CONFIRMED: [ACTION_ASSIGN, ACTION_CLOSE],
    STATUS_IN_PROGRESS: [ACTION_RESOLVE],
    STATUS_RESOLVED: [ACTION_CLOSE, ACTION_ACTIVATE],
    STATUS_CLOSED: [ACTION_ACTIVATE],
}

# Resolution is required when resolving
ACTION_REQUIRES_RESOLUTION = {ACTION_RESOLVE}


def apply_transition(current_status: str, action: str, **kwargs) -> dict:
    """Validate and apply a state transition.

    Args:
        current_status: The current defect status.
        action: The action to perform.
        **kwargs: May contain 'resolution' for resolve actions.

    Returns:
        dict with 'status' (new status) and 'resolution' (new resolution).

    Raises:
        ValueError: If the transition is invalid.
    """
    allowed = TRANSITIONS.get(current_status, [])
    if action not in allowed:
        raise ValueError(
            f'状态转换无效: 当前状态"{current_status}"不允许执行"{action}"操作'
        )

    new_status = _next_status(current_status, action)
    new_resolution = kwargs.get('resolution', '')

    # resolution is required for resolve action
    if action in ACTION_REQUIRES_RESOLUTION and not new_resolution:
        raise ValueError('解决缺陷时必须提供解决方案(Resolution)')

    if new_resolution and new_resolution not in RESOLUTIONS:
        raise ValueError(f'无效的解决方案: "{new_resolution}"，可选值: {", ".join(RESOLUTIONS)}')

    return {'status': new_status, 'resolution': new_resolution if action == ACTION_RESOLVE else ''}


def _next_status(current_status: str, action: str) -> str:
    """Determine the next status based on action."""
    mapping = {
        (STATUS_UNCONFIRMED, ACTION_CONFIRM): STATUS_CONFIRMED,
        (STATUS_UNCONFIRMED, ACTION_CLOSE): STATUS_CLOSED,
        (STATUS_CONFIRMED, ACTION_ASSIGN): STATUS_IN_PROGRESS,
        (STATUS_CONFIRMED, ACTION_CLOSE): STATUS_CLOSED,
        (STATUS_IN_PROGRESS, ACTION_RESOLVE): STATUS_RESOLVED,
        (STATUS_RESOLVED, ACTION_CLOSE): STATUS_CLOSED,
        (STATUS_RESOLVED, ACTION_ACTIVATE): STATUS_IN_PROGRESS,
        (STATUS_CLOSED, ACTION_ACTIVATE): STATUS_IN_PROGRESS,
    }
    return mapping.get((current_status, action), current_status)