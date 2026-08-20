from collections.abc import Sequence

from app.domain.enums import RunStatus, TaskStatus, VersionStatus


def derive_task_status(
    *,
    run_status: RunStatus | None,
    version_statuses: Sequence[VersionStatus],
    expected_platform_count: int,
    needs_attention: bool = False,
    cancelled: bool = False,
    archived: bool = False,
    has_change_requests: bool = False,
) -> TaskStatus:
    if archived:
        return TaskStatus.ARCHIVED
    if cancelled:
        return TaskStatus.CANCELLED
    if needs_attention:
        return TaskStatus.NEEDS_ATTENTION
    if run_status is None:
        return TaskStatus.QUEUED
    if run_status is RunStatus.FAILED:
        return TaskStatus.FAILED
    if run_status is RunStatus.CANCELLED:
        return TaskStatus.CANCELLED
    if run_status is RunStatus.RUNNING:
        return TaskStatus.RUNNING

    settled = [s for s in version_statuses if s is not VersionStatus.DRAFT]
    if not settled:
        return TaskStatus.RUNNING
    if all(s is VersionStatus.REJECTED for s in settled):
        return TaskStatus.CANCELLED
    if has_change_requests:
        return TaskStatus.CHANGES_REQUESTED
    live = [s for s in settled if s is not VersionStatus.REJECTED]
    if len(settled) < expected_platform_count:
        return TaskStatus.PARTIALLY_READY
    if all(s is VersionStatus.APPROVED for s in live):
        return TaskStatus.APPROVED
    return TaskStatus.AWAITING_REVIEW
