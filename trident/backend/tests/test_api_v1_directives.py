"""API tests — directive 100B §12.3."""

from __future__ import annotations


def test_schema_status_ok(client, minimal_project_ids) -> None:
    r = client.get("/api/v1/system/schema-status")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tables_missing"] == []


def test_create_list_get_directive(client, minimal_project_ids, auth_headers) -> None:
    ids = minimal_project_ids
    payload = {
        "project_id": str(ids["project_id"]),
        "title": "API directive",
        "graph_id": "gx",
        "status": "DRAFT",
    }
    c = client.post("/api/v1/directives/", json=payload, headers=auth_headers)
    assert c.status_code == 200, c.text
    did = c.json()["directive"]["id"]

    lst = client.get("/api/v1/directives/", headers=auth_headers)
    assert lst.status_code == 200
    ids_found = {item["id"] for item in lst.json()["items"]}
    assert did in ids_found

    one = client.get(f"/api/v1/directives/{did}", headers=auth_headers)
    assert one.status_code == 200
    assert one.json()["directive"]["title"] == "API directive"
    assert one.json()["task_ledger"]["current_state"] == "DRAFT"
