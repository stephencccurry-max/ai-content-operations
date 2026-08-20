import time
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import Platform, VersionStatus
from app.errors import AppError
from app.infrastructure.db.models import (
    ContentOutputSlot,
    ContentOutputVersion,
    ContentTask,
    ProviderCall,
    TaskPlatform,
)
from app.infrastructure.providers.llm import (
    NOTE_PROMPT_VERSION,
    PROMPT_VERSION,
    SCRIPT_PROMPT_VERSION,
    get_llm_provider,
)
from app.infrastructure.providers.search import SearchHit, get_search_provider


def _get_or_create_slot(
    session: Session, task_id: uuid.UUID, platform: Platform
) -> ContentOutputSlot:
    task_platform = session.scalar(
        select(TaskPlatform).where(
            TaskPlatform.task_id == task_id, TaskPlatform.platform == platform.value
        )
    )
    if task_platform is None:
        raise AppError(
            "PLATFORM_NOT_IN_TASK", "该任务未选择这个平台", status_code=400
        )
    slot = session.scalar(
        select(ContentOutputSlot)
        .where(
            ContentOutputSlot.task_id == task_id,
            ContentOutputSlot.platform == platform.value,
            ContentOutputSlot.content_type == task_platform.content_type,
        )
        .with_for_update()
    )
    if slot is None:
        slot = ContentOutputSlot(
            task_id=task_id,
            platform=platform.value,
            content_type=task_platform.content_type,
        )
        session.add(slot)
        session.flush()
    return slot


def _next_version(session: Session, slot_id: uuid.UUID) -> int:
    current = session.scalar(
        select(func.max(ContentOutputVersion.version)).where(
            ContentOutputVersion.slot_id == slot_id
        )
    )
    return (current or 0) + 1


def _prompt_version(provider_name: str, platform: Platform) -> str:
    if platform is Platform.XIAOHONGSHU:
        return NOTE_PROMPT_VERSION if provider_name == "zhipu" else PROMPT_VERSION
    return SCRIPT_PROMPT_VERSION


def _ensure_research_sources(session: Session, task: ContentTask) -> None:
    if task.research_sources:
        return
    search = get_search_provider()
    started = time.perf_counter()
    hits = search.search(task.topic)
    latency_ms = int((time.perf_counter() - started) * 1000)
    task.research_sources = [
        {"title": hit.title, "url": hit.url, "content": hit.content} for hit in hits
    ]
    session.add(
        ProviderCall(
            task_id=task.id,
            provider=search.name,
            model=search.name,
            latency_ms=latency_ms,
            status="succeeded",
            input_tokens=0,
            output_tokens=0,
            estimated_cost=0,
        )
    )
    session.flush()


def generate_output(
    session: Session, task_id: uuid.UUID, platform: Platform
) -> ContentOutputVersion:
    task = session.scalar(
        select(ContentTask).where(ContentTask.id == task_id).with_for_update()
    )
    if task is None:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    slot = _get_or_create_slot(session, task_id, platform)
    _ensure_research_sources(session, task)
    sources = [SearchHit(**row) for row in task.research_sources]
    provider = get_llm_provider()
    prompt_version = _prompt_version(provider.name, platform)

    started = time.perf_counter()
    try:
        if platform is Platform.XIAOHONGSHU:
            result = provider.generate_note(
                task.topic, task.audience, task.tone, sources
            )
        else:
            result = provider.generate_script(
                task.topic, task.audience, task.tone, sources
            )
    except AppError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        session.add(
            ProviderCall(
                task_id=task_id,
                provider=provider.name,
                model=provider.model,
                prompt_version=prompt_version,
                latency_ms=latency_ms,
                status="failed",
                error_code=exc.code,
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0,
            )
        )
        session.commit()
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    payload = result.payload

    call = ProviderCall(
        task_id=task_id,
        provider=provider.name,
        model=provider.model,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
        status="succeeded",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost=0,
    )
    session.add(call)
    session.flush()

    version = ContentOutputVersion(
        slot_id=slot.id,
        version=_next_version(session, slot.id),
        status=VersionStatus.AWAITING_REVIEW.value,
        title_snapshot=payload.get("title") or payload.get("hook"),
        payload_json=payload,
        prompt_version=prompt_version,
        model=provider.model,
        provider_call_id=call.id,
    )
    session.add(version)
    session.flush()
    slot.current_version_id = version.id
    session.flush()
    return version


def create_manual_version(
    session: Session, slot_id: uuid.UUID, payload: dict
) -> ContentOutputVersion:
    slot = session.scalar(
        select(ContentOutputSlot)
        .where(ContentOutputSlot.id == slot_id)
        .with_for_update()
    )
    if slot is None:
        raise AppError("SLOT_NOT_FOUND", "内容位不存在", status_code=404)

    version = ContentOutputVersion(
        slot_id=slot.id,
        version=_next_version(session, slot.id),
        status=VersionStatus.AWAITING_REVIEW.value,
        title_snapshot=payload.get("title"),
        payload_json=payload,
    )
    session.add(version)
    session.flush()
    slot.current_version_id = version.id
    session.flush()
    return version
