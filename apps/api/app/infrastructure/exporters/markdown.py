from pathlib import Path


def render_markdown(task, slot, version) -> str:
    payload = version.payload_json
    hashtags = " ".join(f"#{tag}" for tag in payload.get("hashtags", []))
    lines = [
        f"# {payload.get('title') or payload.get('hook') or task.topic}",
        "",
        f"> 平台：{slot.platform}　版本：{version.version}",
        "",
        payload.get("body") or payload.get("script") or "",
    ]
    if hashtags:
        lines += ["", hashtags]
    return "\n".join(lines) + "\n"


def write_export(export_dir: Path, task_id, version, content: str) -> Path:
    export_dir = Path(export_dir).resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{task_id}-v{version.version}.md"
    target = (export_dir / filename).resolve()
    if export_dir not in target.parents:
        raise ValueError("导出路径超出允许目录")
    target.write_text(content, encoding="utf-8")
    return target
