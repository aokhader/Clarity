"""`cli auth` stops with the missing setting's name when the Clio app is not set up.

It used to print an authorize URL with `client_id=None` in it. Settings are built
without the .env file, so the developer's own Clio app never reaches a test, and no
request is made.
"""

from pathlib import Path

import pytest

from app import cli
from app.clio import oauth
from app.config import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, data_dir: Path, **values: str) -> None:
    settings = Settings(_env_file=None, data_dir=data_dir, **values)  # type: ignore[call-arg]
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(oauth, "get_settings", lambda: settings)


@pytest.mark.parametrize(
    ("values", "missing", "present"),
    [
        ({}, ["CLIO_CLIENT_ID", "CLIO_CLIENT_SECRET"], []),
        ({"clio_client_id": "invented-id"}, ["CLIO_CLIENT_SECRET"], ["CLIO_CLIENT_ID"]),
        (
            {"clio_client_secret": "invented-secret"},
            ["CLIO_CLIENT_ID"],
            ["CLIO_CLIENT_SECRET"],
        ),
    ],
)
def test_auth_names_the_missing_settings_and_builds_no_url(
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    values: dict[str, str],
    missing: list[str],
    present: list[str],
) -> None:
    _settings(monkeypatch, data_dir, **values)

    def no_wait(_state: str) -> str:
        raise AssertionError("auth must stop before waiting for Clio")

    monkeypatch.setattr(oauth, "wait_for_code", no_wait)

    assert cli.main(["auth"]) == 1

    out, err = capsys.readouterr()
    assert "oauth/authorize" not in out + err
    assert "None" not in out + err
    assert all(name in err for name in missing)
    assert all(name not in err for name in present)
    assert ".env" in err


def test_no_authorize_url_is_built_without_a_client_id(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _settings(monkeypatch, data_dir)

    with pytest.raises(oauth.ClioNotAuthorized, match="CLIO_CLIENT_ID"):
        oauth.authorize_url("invented-state")
