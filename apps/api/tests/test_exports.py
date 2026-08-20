from pathlib import Path

import pytest

HEADERS = {"X-Internal-Token": "test-internal-token"}
PAYLOAD = {
    "topic": "咖啡因如何影响睡眠质量",
    "audience": "熬夜上班族",
    "goal": "education",
    "platforms": ["xiaohongshu"],
    "tone": "专业、实用",
}


@pytest.fixture()
def version(client):
    task_id = client.post(
        "/api/v1/tasks", json=PAYLOAD, headers={"Idempotency-Key": "k"}
    ).json()["id"]
    return client.post(
        f"/internal/v1/tasks/{task_id}/generate/xiaohongshu", headers=HEADERS
    ).json()


def test_export_rejects_unapproved_version(client, version):
    response = client.post(f"/api/v1/output-versions/{version['id']}/export")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VERSION_NOT_APPROVED"


def test_export_writes_utf8_markdown_file(client, version, tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path))

    client.post(
        f"/api/v1/output-versions/{version['id']}/review",
        json={"version": 1, "decision": "approve"},
    )
    response = client.post(f"/api/v1/output-versions/{version['id']}/export")

    assert response.status_code == 201
    path = Path(response.json()["file_path"])
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "咖啡因" in text
    assert "版本：1" in text
    get_settings.cache_clear()


def test_rendered_markdown_contains_title_body_and_hashtags():
    from app.infrastructure.exporters.markdown import render_markdown

    class _Task:
        topic = "咖啡因如何影响睡眠质量"

    class _Slot:
        platform = "xiaohongshu"

    class _Version:
        version = 3
        payload_json = {
            "title": "标题",
            "body": "正文内容",
            "hashtags": ["睡眠", "咖啡"],
        }

    text = render_markdown(_Task(), _Slot(), _Version())

    assert "# 标题" in text
    assert "正文内容" in text
    assert "#睡眠" in text
    assert "版本：3" in text


def test_write_export_blocks_path_traversal(tmp_path):
    import uuid

    from app.infrastructure.exporters.markdown import write_export

    class _Version:
        id = uuid.uuid4()
        version = 1
        slot_id = uuid.uuid4()

    with pytest.raises(ValueError):
        write_export(tmp_path, "../../evil", _Version(), "x")
