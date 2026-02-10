from app.core.config import settings
settings.RATE_LIMIT_PER_MINUTE = 1000

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.db_session import Base, get_db, build_database_url
from main import app

from app.modules.users.models import UserModel
from app.modules.patients.models import PatientModel
from app.modules.appointments.models import AppointmentsModel
from app.modules.inventory.models import InventoryItemModel
from app.modules.billing.models import BillingInvoiceModel, PharmacyWalkInBillModel
from app.modules.asset_management.models import RoomModel, MachineModel
import os
TEST_TENANT_ID = "test_tenant_xyz"

# Override settings for tests
settings.TENANT_ID = TEST_TENANT_ID

@pytest.fixture(scope="session")
def db_engine():
    """Create database engine for test session"""
    engine = create_engine(build_database_url())
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    yield engine
    # Optional: cleanup tables after session if using dedicated test DB
    # Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a new database session for a test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """Create a TestClient with a database session override."""
    def override_get_db():
        yield db_session

    # 1. Override FastAPI dependency
    app.dependency_overrides[get_db] = override_get_db
    
    # 2. Monkeypatch get_db in all places it might be used
    # Use import_module to avoid local name conflict with the 'app' FastAPI instance
    import importlib
    ds_mod = importlib.import_module("app.core.db_session")
    utils_mod = importlib.import_module("app.core.db_utils")
    deps_mod = importlib.import_module("app.core.dependencies")
    
    monkeypatch.setattr(ds_mod, "get_db", override_get_db)
    monkeypatch.setattr(utils_mod, "get_db", override_get_db)
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(db_engine):
    """Cleanup test tenant data before and after test session."""
    def _cleanup():
        Session = sessionmaker(bind=db_engine)
        session = Session()
        try:
            # Delete order matters for foreign keys
            session.query(PharmacyWalkInBillModel).filter(PharmacyWalkInBillModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(BillingInvoiceModel).filter(BillingInvoiceModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(AppointmentsModel).filter(AppointmentsModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(PatientModel).filter(PatientModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(InventoryItemModel).filter(InventoryItemModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(MachineModel).filter(MachineModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(RoomModel).filter(RoomModel.tenant_id == TEST_TENANT_ID).delete()
            session.query(UserModel).filter(UserModel.tenant_id == TEST_TENANT_ID).delete()
            session.commit()
        except Exception as e:
            print(f"Cleanup error: {e}")
            session.rollback()
        finally:
            session.close()

    _cleanup() # Before
    yield
    _cleanup() # After

@pytest.fixture
def test_password():
    return "Password123"

@pytest.fixture
def owner_data(test_password):
    return {
        "firstname": "John",
        "lastname": "Doe",
        "phone": "9876543210",
        "username": "admin_owner",
        "password": test_password,
        "user_type": "owner"
    }

@pytest.fixture
def auth_headers(client, owner_data):
    """Helper fixture to get auth headers for owner."""
    # Register owner if not exists
    client.post("/api/auth/register", json=owner_data)
    
    # Login
    response = client.post(
        "/api/auth/login",
        data={"username": owner_data["username"], "password": owner_data["password"]}
    )
    res_json = response.json()
    token = res_json.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}
