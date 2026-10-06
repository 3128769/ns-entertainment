import pytest

from nsapp import cli
from nsapp.errors import AppError
from nsapp.repositories import users
from nsapp.services import auth


@pytest.fixture(autouse=True)
def admin():
    users.ensure_tables()
    auth.ensure_admin()  # NS_ADMIN_PASSWORD from conftest


def test_changing_the_password_replaces_it_and_signs_everyone_out():
    old = auth.authenticate("admin", "test-password-only")
    assert auth.current_user(old) == "admin"
    result = auth.set_password("admin", "a-new-password")
    assert result == {"username": "admin", "created": False, "sessions_closed": 1}
    assert auth.current_user(old) is None
    assert auth.authenticate("admin", "test-password-only") is None
    assert auth.current_user(auth.authenticate("admin", "a-new-password")) == "admin"


def test_a_missing_admin_is_created():
    assert auth.set_password("fresh-user", "long-enough-pw")["created"] is True
    assert auth.authenticate("fresh-user", "long-enough-pw")


def test_short_passwords_are_rejected_and_change_nothing():
    with pytest.raises(AppError) as caught:
        auth.set_password("admin", "short")
    assert caught.value.code == "PASSWORD_TOO_SHORT"
    assert auth.authenticate("admin", "test-password-only")


def test_the_command_line_reads_the_password_from_the_environment(monkeypatch, capsys):
    monkeypatch.setenv("NS_NEW_PASSWORD", "from-the-environment")
    monkeypatch.setattr("sys.argv", ["nsapp.cli", "set-admin-password"])
    cli.main()
    assert "from-the-environment" not in capsys.readouterr().out  # the secret is never echoed
    assert auth.authenticate("admin", "from-the-environment")


def test_the_command_line_refuses_a_weak_password(monkeypatch):
    monkeypatch.setenv("NS_NEW_PASSWORD", "tiny")
    monkeypatch.setattr("sys.argv", ["nsapp.cli", "set-admin-password"])
    with pytest.raises(SystemExit, match="PASSWORD_TOO_SHORT"):
        cli.main()
