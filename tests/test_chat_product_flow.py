from server import build_chat_response, seed_state


def test_chat_response_uses_pack_scoped_knowledge_and_citations():
    state = seed_state()

    response = build_chat_response(state, "E-204 cooling pump", "after-sales", "tenant-demo")

    assert response["pack_id"] == "after-sales"
    assert response["evidence_count"] >= 1
    assert response["matches"][0]["citation_id"]
    assert response["citations"][0]["document_id"]
    assert "证据" in response["reply"]
