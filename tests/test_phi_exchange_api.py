from fastapi.testclient import TestClient

from app.main import app


def test_consent_register_then_allowed_exchange() -> None:
    with TestClient(app) as client:
        register = client.post(
            "/consents",
            json={
                "consent_id": "api-c1",
                "patient_id": "api-p1",
                "granted_categories": ["diagnosis"],
                "granted_purposes": ["treatment"],
                "authorized_recipients": ["hie_hospital_north"],
            },
        )
        assert register.status_code == 201

        exchange = client.post(
            "/phi-exchanges",
            json={
                "consent_id": "api-c1",
                "patient_id": "api-p1",
                "disclosing_org": "hie_clinic_riverside",
                "receiving_org": "hie_hospital_north",
                "categories": ["diagnosis"],
                "purpose_of_use": "treatment",
            },
        )

    assert exchange.status_code == 200
    body = exchange.json()
    assert body["decision"]["allowed"] is True

    with TestClient(app) as client:
        evidence = client.get(f"/evidence/{body['request_id']}")
    assert evidence.status_code == 200
    assert evidence.json()["consent_id"] == "api-c1"


def test_exchange_without_registered_consent_is_denied() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/phi-exchanges",
            json={
                "consent_id": "never-registered",
                "patient_id": "api-p1",
                "disclosing_org": "hie_clinic_riverside",
                "receiving_org": "hie_hospital_north",
                "categories": ["diagnosis"],
                "purpose_of_use": "treatment",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["allowed"] is False


def test_exchange_rejects_unknown_phi_category_at_the_schema_level() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/phi-exchanges",
            json={
                "consent_id": "api-c1",
                "patient_id": "api-p1",
                "disclosing_org": "hie_clinic_riverside",
                "receiving_org": "hie_hospital_north",
                "categories": ["not_a_real_category"],
                "purpose_of_use": "treatment",
            },
        )

    assert response.status_code == 422
