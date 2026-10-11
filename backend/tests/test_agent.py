from app.agent import deterministic_decision
from app.seed_data import POLICIES

def test_laptop_refresh_conflict_is_flagged():
    req={"id":"REQ-01","message":"My laptop won't turn on at all, it is about 3.5 years old"}
    result=deterministic_decision(req,POLICIES)
    assert result["action"]=="Flag for Review"
    assert {p["id"] for p in result["matched_policy"]}=={"KB-03","AM-01"}

def test_vague_request_is_flagged():
    req={"id":"REQ-15","message":"hey can you help, its not working"}
    result=deterministic_decision(req,POLICIES)
    assert result["action"]=="Flag for Review"
    assert result["confidence"] < 0.65

def test_guest_wifi_is_auto_resolved():
    req={"id":"REQ-02","message":"Can I get Wi-Fi access for a guest visiting our office tomorrow?"}
    result=deterministic_decision(req,POLICIES)
    assert result["action"]=="Auto-Resolve"
    assert result["matched_policy"][0]["id"]=="KB-07"
