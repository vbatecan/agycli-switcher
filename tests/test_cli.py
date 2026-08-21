"""
End-to-end CLI integration tests.
"""

from pathlib import Path
import pytest

from agy_multiprofile.cli import main
from agy_multiprofile.core.storage import ProfileStore


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "agy-profile" in captured.out


def test_cli_no_args(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "agy-profile" in captured.out



def test_cli_list_and_create(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    ret = main(["create", "personal", "--email", "personal@gmail.com", "--desc", "My Personal Account"])
    assert ret == 0

    ret = main(["list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "personal" in captured.out
    assert "personal@gmail.com" in captured.out


def test_cli_switch_and_current(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    main(["create", "work", "--email", "work@company.com", "--clone-current"])
    ret = main(["switch", "work"])
    assert ret == 0

    ret = main(["current"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "work" in captured.out


def test_cli_doctor(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    ret = main(["doctor"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Doctor check passed" in captured.out


def test_cli_backups_and_trash(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    main(["create", "temp_prof", "--desc", "Temporary"])
    ret = main(["backups"])
    assert ret == 0

    main(["delete", "temp_prof", "-y"])
    ret = main(["trash"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "temp_prof" in captured.out


def test_cli_diff(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    main(["create", "alpha", "--desc", "Alpha"])
    main(["create", "beta", "--desc", "Beta"])
    ret = main(["diff", "alpha", "beta"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Diff between profiles" in captured.out or "identical" in captured.out

