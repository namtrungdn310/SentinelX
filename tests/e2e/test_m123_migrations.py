"""Opt-in migration paths on disposable DBs in the explicitly configured QA server."""

import asyncio
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

URL = os.getenv("SENTINELX_MIGRATION_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Requires isolated PostgreSQL migration QA server")


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, "0004_m2_network_windows", "0004_m3_detection_events"])
async def test_upgrade_from_empty_or_existing_head_preserves_data(previous: str | None) -> None:
    database = "sentinelx_migration_qa_" + uuid4().hex
    admin = create_async_engine(URL, isolation_level="AUTOCOMMIT")
    target_url = make_url(URL).set(database=database)
    target = create_async_engine(target_url)
    environment = {
        **os.environ,
        "SENTINELX_DATABASE__URL": target_url.render_as_string(hide_password=False),
    }

    async def migrate(action: str, revision: str) -> None:
        await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "alembic", action, revision],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        async with admin.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database}"'))
        if previous:
            await migrate("upgrade", previous)
            project, node = uuid4(), uuid4()
            async with target.begin() as connection:
                await connection.execute(
                    text("INSERT INTO projects (id,name) VALUES (:id,'preserved')"), {"id": project}
                )
                await connection.execute(
                    text(
                        "INSERT INTO nodes (id,project_id,hostname,ip_address) "
                        "VALUES (:id,:project,'host','192.0.2.1')"
                    ),
                    {"id": node, "project": project},
                )
                await connection.execute(
                    text(
                        "INSERT INTO telemetry_metric_samples "
                        "(node_id,observed_at,cpu_usage_pct,memory_usage_pct) "
                        "VALUES (:id,now(),40,50)"
                    ),
                    {"id": node},
                )
                if previous == "0004_m2_network_windows":
                    await connection.execute(
                        text(
                            "INSERT INTO telemetry_network_windows "
                            "(node_id,window_id,window_start,window_end,received_at,interface,"
                            "features,omitted_packets,skipped_windows) VALUES "
                            "(:id,:window,now()-interval '10 seconds',now(),now(),'eth0',"
                            "'[]'::jsonb,0,0)"
                        ),
                        {"id": node, "window": uuid4()},
                    )
                else:
                    await connection.execute(
                        text(
                            "INSERT INTO detection_events "
                            "(id,node_id,detector_name,severity,confidence_score,details) "
                            "VALUES (:id,:node,'migration_probe','HIGH',0.9,'{}'::jsonb)"
                        ),
                        {"id": uuid4(), "node": node},
                    )
        await migrate("upgrade", "head")
        async with target.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars().all() == ["0006_detection_state"]
            for table in ("telemetry_network_windows", "detection_events", "detection_node_state"):
                assert (
                    await connection.execute(text("SELECT to_regclass(:table)"), {"table": table})
                ).scalar_one() == table
            if previous:
                assert (
                    await connection.execute(text("SELECT count(*) FROM telemetry_metric_samples"))
                ).scalar_one() == 1
                table = (
                    "telemetry_network_windows"
                    if previous.endswith("network_windows")
                    else "detection_events"
                )
                assert (
                    await connection.execute(text(f"SELECT count(*) FROM {table}"))
                ).scalar_one() == 1
        await migrate("downgrade", "0005_merge_m2_m3")
        await migrate("upgrade", "head")
    finally:
        await target.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        await admin.dispose()
