from fastapi.testclient import TestClient

from app.main import app


def test_register_then_allowed_advisory() -> None:
    with TestClient(app) as client:
        register = client.post(
            "/dsi-registrations",
            json={
                "dsi_id": "api-d1",
                "model_name": "ApiTestScorer",
                "developer_name": "Acme Health",
                "developer_contact": "dev@acme.example",
                "funding_source": "internal",
                "output_value_description": "risk score",
                "output_type": "prediction",
                "intended_use": "flag high risk patients",
                "intended_patient_population": "adult inpatients",
                "intended_users": ["physician"],
                "decision_making_role": "informs",
                "cautioned_out_of_scope_uses": ["pediatric patients"],
                "known_risks_and_limitations": "lower sensitivity in edge cases",
            },
        )
        assert register.status_code == 201

        advisory = client.post(
            "/dsi-advisories",
            json={
                "dsi_id": "api-d1",
                "requesting_org": "hie_hospital_north",
                "encounter_id": "enc-1",
            },
        )

    assert advisory.status_code == 200
    body = advisory.json()
    assert body["decision"]["allowed"] is True
    assert body["advisory_output"] is not None

    with TestClient(app) as client:
        evidence = client.get(f"/evidence/{body['request_id']}")
    assert evidence.status_code == 200
    assert evidence.json()["dsi_id"] == "api-d1"


def test_advisory_without_registration_is_denied_and_no_output_produced() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/dsi-advisories",
            json={
                "dsi_id": "never-registered",
                "requesting_org": "hie_hospital_north",
                "encounter_id": "enc-1",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["allowed"] is False
    assert body["advisory_output"] is None


def test_registration_rejects_unknown_output_type_at_schema_level() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/dsi-registrations",
            json={
                "dsi_id": "api-d2",
                "model_name": "BadModel",
                "output_type": "not_a_real_output_type",
            },
        )

    assert response.status_code == 422
