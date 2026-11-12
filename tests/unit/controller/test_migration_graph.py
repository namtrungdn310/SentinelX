"""Both previously deployed M2/M3 heads must have a single common upgrade target."""

from pathlib import Path

from alembic.script import ScriptDirectory


def test_m2_and_m3_keep_their_revisions_and_join_before_detection_state() -> None:
    scripts = ScriptDirectory(str(Path(__file__).resolve().parents[3] / "migrations"))
    assert scripts.get_heads() == ["0009_m8_recovery_actions"]
    merge = scripts.get_revision("0005_merge_m2_m3")
    assert merge is not None
    assert isinstance(merge.down_revision, tuple)
    assert set(merge.down_revision) == {"0004_m2_network_windows", "0004_m3_detection_events"}
    for previous in ("0004_m2_network_windows", "0004_m3_detection_events"):
        revision = scripts.get_revision(previous)
        assert revision is not None and revision.down_revision == "0003_f8_telemetry_metric_samples"
        assert list(scripts.iterate_revisions("head", previous))
