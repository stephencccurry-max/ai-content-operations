import pytest

from app.domain.enums import RunStatus, TaskStatus, VersionStatus
from app.domain.tasks.status import derive_task_status

A = VersionStatus.APPROVED
W = VersionStatus.AWAITING_REVIEW
R = VersionStatus.REJECTED


@pytest.mark.parametrize(
    ("run_status", "versions", "expected_count", "expected"),
    [
        (None, [], 2, TaskStatus.QUEUED),
        (RunStatus.RUNNING, [], 2, TaskStatus.RUNNING),
        (RunStatus.FAILED, [], 2, TaskStatus.FAILED),
        (RunStatus.SUCCEEDED, [W, W], 2, TaskStatus.AWAITING_REVIEW),
        (RunStatus.SUCCEEDED, [W], 2, TaskStatus.PARTIALLY_READY),
        (RunStatus.SUCCEEDED, [A, W], 2, TaskStatus.AWAITING_REVIEW),
        (RunStatus.SUCCEEDED, [A, A], 2, TaskStatus.APPROVED),
        (RunStatus.SUCCEEDED, [R, R], 2, TaskStatus.CANCELLED),
        (RunStatus.SUCCEEDED, [A, R], 2, TaskStatus.APPROVED),
    ],
)
def test_status_truth_table(run_status, versions, expected_count, expected):
    assert (
        derive_task_status(
            run_status=run_status,
            version_statuses=versions,
            expected_platform_count=expected_count,
        )
        == expected
    )


def test_archived_wins_over_everything():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[A],
            expected_platform_count=1,
            needs_attention=True,
            cancelled=True,
            archived=True,
        )
        == TaskStatus.ARCHIVED
    )


def test_cancelled_wins_over_needs_attention():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[],
            expected_platform_count=1,
            needs_attention=True,
            cancelled=True,
        )
        == TaskStatus.CANCELLED
    )


def test_needs_attention_wins_over_running():
    assert (
        derive_task_status(
            run_status=RunStatus.RUNNING,
            version_statuses=[],
            expected_platform_count=1,
            needs_attention=True,
        )
        == TaskStatus.NEEDS_ATTENTION
    )


def test_change_requests_take_precedence_over_awaiting_review():
    assert (
        derive_task_status(
            run_status=RunStatus.SUCCEEDED,
            version_statuses=[W, W],
            expected_platform_count=2,
            has_change_requests=True,
        )
        == TaskStatus.CHANGES_REQUESTED
    )


def test_change_requests_do_not_override_cancellation():
    assert (
        derive_task_status(
            run_status=RunStatus.SUCCEEDED,
            version_statuses=[R, R],
            expected_platform_count=2,
            has_change_requests=True,
        )
        == TaskStatus.CANCELLED
    )
