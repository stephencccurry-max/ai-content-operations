from sqlalchemy import inspect


def test_baseline_migration_creates_core_tables(db_session):
    tables = set(inspect(db_session.bind).get_table_names())

    assert {
        "projects",
        "content_tasks",
        "task_platforms",
        "workflow_runs",
        "workflow_step_runs",
        "content_output_slots",
        "content_output_versions",
        "review_decisions",
        "audit_events",
        "idempotency_keys",
        "provider_calls",
    } <= tables


def test_slot_is_unique_per_task_platform_and_content_type(db_session):
    from sqlalchemy import inspect as sa_inspect

    constraints = sa_inspect(db_session.bind).get_unique_constraints(
        "content_output_slots"
    )
    columns = [tuple(c["column_names"]) for c in constraints]

    assert ("task_id", "platform", "content_type") in columns


def test_version_is_unique_per_slot(db_session):
    from sqlalchemy import inspect as sa_inspect

    constraints = sa_inspect(db_session.bind).get_unique_constraints(
        "content_output_versions"
    )
    columns = [tuple(c["column_names"]) for c in constraints]

    assert ("slot_id", "version") in columns


def test_health_reports_database_status(client):
    body = client.get("/api/v1/health").json()

    assert body["database"] == "ok"
