import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("PUBLIC_URL", "http://testserver")
os.environ["ALLOWED_ORIGINS"] = "http://testserver"
os.environ["PADDLE_WEBHOOK_SECRET"] = "pdl_ntfset_test"
os.environ["PADDLE_PRICE_TEAM"] = "pri_team"
os.environ["PADDLE_PRICE_BUSINESS"] = "pri_business"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import db as dbmod  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from app import models  # noqa: F401
    pg = os.environ.get("TEST_DATABASE_URL")  # e.g. postgresql+psycopg://sg:pw@localhost/mcpledger_test
    if pg:
        engine = create_engine(pg)
        dbmod.Base.metadata.drop_all(engine)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    dbmod.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    from app.main import app
    from app.security import auth_limiter, enroll_limiter
    auth_limiter.hits.clear()
    enroll_limiter.hits.clear()
    app.dependency_overrides[dbmod.get_db] = get_db
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        c.Session = Session
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def owner(client):
    r = client.post("/api/auth/signup", json={"email": "owner@acme.dev", "password": "correct horse 1",
                                              "name": "Ola", "org_name": "Acme"})
    assert r.status_code == 200, r.text
    return client
