"""Sign-in, roles and protection of client data (3.1.2)."""

from __future__ import annotations

import pytest

from aceest import auth, create_app, db
from aceest.errors import ConflictError, ValidationError


def test_first_admin_is_seeded_from_the_secret(app, admin_password):
    with app.app_context():
        assert [(u["username"], u["role"]) for u in db.list_users()] == [("admin", "Admin")]
        stored = db.find_user("admin")["password_hash"]
    assert admin_password not in stored
    assert stored.startswith("scrypt:")


def test_no_secret_means_no_default_account(tmp_path, caplog, settings):
    app = create_app("testing", overrides={**settings, "ADMIN_PASSWORD": "",
                                           "DATABASE": str(tmp_path / "empty.db")})
    with app.app_context():
        assert db.count_users() == 0
    assert "nobody can sign in" in caplog.text
    assert app.test_client().post("/login", data={"username": "admin", "password": "admin"}).status_code == 401


def test_seeding_twice_or_racing_another_replica_is_harmless(app, monkeypatch):
    auth.seed_admin(app)
    monkeypatch.setattr(db, "count_users", lambda: 0)  # as if another pod got there first
    auth.seed_admin(app)
    with app.app_context():
        assert len(db.list_users()) == 1


def test_pages_redirect_to_sign_in(anon_client):
    response = anon_client.get("/clients/Someone?x=1")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=/clients/Someone")


def test_sign_in_and_out(anon_client, admin_password):
    response = anon_client.post("/login", data={"username": "ADMIN", "password": admin_password})
    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    page = anon_client.get("/").get_data(as_text=True)
    assert "admin (Admin)" in page

    assert anon_client.post("/logout").status_code == 303
    assert anon_client.get("/").status_code == 302


def test_wrong_password_is_refused(anon_client):
    response = anon_client.post("/login", data={"username": "admin", "password": "nope"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.get_data(as_text=True)


@pytest.mark.parametrize(("target", "expected"), [
    ("/clients/Ravi", "/clients/Ravi"),
    ("https://evil.example/x", "/"),
    ("//evil.example", "/"),
    ("javascript:alert(1)", "/"),
    ("", "/"),
])
def test_next_only_points_back_into_the_site(anon_client, admin_password, target, expected):
    response = anon_client.post("/login", data={"username": "admin", "password": admin_password,
                                                "next": target})
    assert response.headers["Location"] == expected


def test_client_api_needs_credentials(anon_client, admin_password, profile_payload):
    response = anon_client.get("/api/clients")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Basic realm="ACEest"'
    assert anon_client.post("/api/clients", json=profile_payload).status_code == 401
    assert anon_client.get("/api/clients", auth=("admin", "wrong")).status_code == 401
    assert anon_client.get("/api/clients", auth=("admin", admin_password)).status_code == 200


def test_public_endpoints_stay_public(anon_client):
    assert anon_client.get("/api/health").status_code == 200
    assert anon_client.get("/api/programs").status_code == 200
    assert anon_client.get("/api/stats").status_code == 200
    assert anon_client.post("/api/calories", json={"weight_kg": 80, "program": "MG"}).status_code == 200


def test_admin_manages_users_and_coaches_cannot(client, app):
    created = client.post("/api/users", json={"username": "coach.anita", "password": "coach-password-1",
                                              "role": "coach"})
    assert created.status_code == 201
    assert created.get_json()["role"] == "Coach"
    assert "password_hash" not in created.get_json()

    coach = app.test_client()
    coach.post("/login", data={"username": "coach.anita", "password": "coach-password-1"})
    assert coach.get("/").status_code == 200
    assert coach.get("/users").status_code == 403
    assert coach.post("/api/users", json={"username": "x", "password": "y", "role": "Admin"}).status_code == 403
    assert "Users</a>" not in coach.get("/").get_data(as_text=True)


def test_users_page_and_form(client):
    page = client.post("/users", data={"username": "coach.ravi", "password": "coach-password-2",
                                       "role": "Coach"}, follow_redirects=True).get_data(as_text=True)
    assert "User coach.ravi (Coach) created" in page
    assert "<td>coach.ravi</td>" in page
    bad = client.post("/users", data={"username": "x", "password": "short", "role": "Coach"},
                      follow_redirects=True).get_data(as_text=True)
    assert "&#39;username&#39; must be 3-32 characters" in bad


@pytest.mark.parametrize(("username", "password", "role", "field"), [
    ("Ab", "long-enough-pass", "Coach", "username"),
    ("9lives", "long-enough-pass", "Coach", "username"),
    ("valid.name", "short", "Coach", "password"),
    ("valid.name", "long-enough-pass", "Owner", "role"),
])
def test_user_validation(app, username, password, role, field):
    with app.app_context(), pytest.raises(ValidationError) as excinfo:
        auth.create_user(username, password, role)
    assert excinfo.value.field == field


def test_duplicate_user_is_a_conflict(app):
    with app.app_context(), pytest.raises(ConflictError):
        auth.create_user("Admin", "another-password", "Admin")


def test_session_for_a_deleted_user_is_anonymous(app, client):
    with app.app_context():
        connection = db.get_db()
        connection.execute("DELETE FROM users")
        connection.commit()
    assert client.get("/").status_code == 302


def test_user_listing_never_exposes_hashes(client):
    users = client.get("/api/users").get_json()["users"]
    assert [u["username"] for u in users] == ["admin"]
    assert all("password_hash" not in u for u in users)
