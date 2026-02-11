import pytest
import asyncio
from agents import copy_agent, reviewer_agent

@pytest.mark.asyncio
async def test_copy_reviewer_workflow():
    """Test Copy Agent → Reviewer → Retry loop"""
    
    # Setup payload
    payload = {
        "context": {
            "product": {
                "id": "gid://shopify/Product/123",
                "title": "Test Hat"
            }
        },
        "apply": False
    }
    
    # Run Copy Agent
    copy_result = await copy_agent.run(payload)
    print(f"\n✅ Copy result: {copy_result['data']}")
    assert copy_result["status"] in ["draft", "applied"]
    assert "draft_text" in copy_result["data"]
    
    # Run Reviewer Agent with correct payload structure
    reviewer_payload = {
        "context": {
            "copy_agent": copy_result  # Reviewer expects this path
        }
    }
    review_result = await reviewer_agent.run(reviewer_payload)
    print(f"✅ Review result: {review_result}")
    
    assert review_result["status"] in ["APPROVED", "NEEDS_CHANGES", "REJECTED"]
    # Test hat beschrijving moet lang genoeg zijn → APPROVED
    assert review_result["status"] == "APPROVED"