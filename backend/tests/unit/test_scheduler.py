from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tracker.scheduler import PhaseNotReady, install_background_scheduler, reserve_task, scheduler_status


def test_scheduler_is_not_running_on_linux():
    status = scheduler_status("linux")
    assert status["backend"] == "disabled"
    assert status["running"] is False
    assert status["installed"] is False
    assert "launchd" in status["detail"]


def test_scheduler_is_not_installed_on_macos_in_phase_one():
    status = scheduler_status("darwin")
    assert status["backend"] == "launchd"
    assert status["running"] is False
    assert status["installed"] is False


def test_installing_the_scheduler_is_refused():
    with pytest.raises(PhaseNotReady):
        install_background_scheduler()


def test_launchd_template_is_disabled_and_does_not_check_prices():
    repo = Path(__file__).resolve().parents[3]
    plist = (repo / "packaging" / "macos" / "com.local.amazonpricetracker.monitor.plist").read_text(
        encoding="utf-8"
    )
    script = (repo / "scripts" / "macos-scheduler.sh").read_text(encoding="utf-8")
    assert "com.local.amazonpricetracker.monitor" in plist
    assert "<key>Disabled</key>" in plist
    assert "<true/>" in plist
    assert "password" not in plist.lower()
    assert "macos-scheduler.sh" in plist
    assert "not enabled" in script
    assert "Amazon" in script


def test_reserve_task_blocks_duplicates_until_the_lock_expires(migrated_conn):
    start = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)
    assert reserve_task(
        migrated_conn,
        profile_id="local",
        task_key="price-check",
        now=start,
        min_interval=timedelta(hours=1),
        owner="a",
    )
    assert (
        reserve_task(
            migrated_conn,
            profile_id="local",
            task_key="price-check",
            now=start + timedelta(minutes=30),
            min_interval=timedelta(hours=1),
            owner="b",
        )
        is False
    )
    assert reserve_task(
        migrated_conn,
        profile_id="local",
        task_key="other-task",
        now=start,
        min_interval=timedelta(hours=1),
        owner="c",
    )
    assert reserve_task(
        migrated_conn,
        profile_id="local",
        task_key="price-check",
        now=start + timedelta(hours=1),
        min_interval=timedelta(hours=1),
        owner="d",
    )
