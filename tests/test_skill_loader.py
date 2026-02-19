"""
Basic tests for SkillLoader service.
Run these to verify the service works before integrating into agents.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.services.skill_loader import SkillLoader
from app.db import db_pool


async def test_get_agent_skills():
    """Test loading skills for an agent."""

    loader = SkillLoader(db_pool)

    # Max (copywriter) should have 5 skills
    skills = await loader.get_agent_skills('agent:copywriter:skilled-001')

    print(f"✓ Loaded {len(skills)} skills for Max")
    assert len(skills) == 5, f"Expected 5 skills, got {len(skills)}"

    # Check skill structure
    first_skill = skills[0]
    assert 'skill_id' in first_skill
    assert 'name' in first_skill
    assert 'content' in first_skill
    assert 'proficiency' in first_skill

    print("✓ Skill structure correct")


async def test_skill_context_composition():
    """Test composing skills into context string."""

    loader = SkillLoader(db_pool)

    skills = await loader.get_agent_skills('agent:copywriter:skilled-001')
    context = loader.compose_skill_context(skills)

    assert len(context) > 100, "Context should be substantial"
    assert "Skill:" in context, "Context should contain skill headers"
    assert "proficiency" in context.lower(), "Context should mention proficiency"

    print(f"✓ Composed {len(context)} chars of skill context")
    print(f"  First 200 chars: {context[:200]}...")


async def test_determine_applicable_skills():
    """Test skill filtering based on task context."""

    loader = SkillLoader(db_pool)

    all_skills = await loader.get_agent_skills('agent:copywriter:skilled-001')

    # Test 1: Website platform should trigger SEO skill
    context_website = {
        'job_post': 'schrijf over wielrennen',
        'platform': 'website',
        'target_audience': 'algemeen'
    }

    applicable_web = loader.determine_applicable_skills(all_skills, context_website)
    seo_skill = next((s for s in applicable_web if 'seo' in s['skill_id']), None)
    assert seo_skill is not None, "SEO skill should be selected for website"
    print(f"✓ Website job: {len(applicable_web)} skills (SEO included)")

    # Test 2: B2B audience should trigger B2B voice
    context_b2b = {
        'job_post': 'schrijf productbeschrijving',
        'platform': 'algemeen',
        'target_audience': 'B2B professional'
    }

    applicable_b2b = loader.determine_applicable_skills(all_skills, context_b2b)
    b2b_voice = next((s for s in applicable_b2b if 'b2b' in s['skill_id']), None)
    assert b2b_voice is not None, "B2B voice should be selected for B2B audience"
    print(f"✓ B2B job: {len(applicable_b2b)} skills (B2B voice included)")

    # Test 3: Casual audience should trigger casual voice
    context_casual = {
        'job_post': 'schrijf blog voor jeugd',
        'platform': 'blog',
        'target_audience': 'jeugd 16-25'
    }

    applicable_casual = loader.determine_applicable_skills(all_skills, context_casual)
    casual_voice = next((s for s in applicable_casual if 'casual' in s['skill_id']), None)
    assert casual_voice is not None, "Casual voice should be selected for youth"
    print(f"✓ Casual job: {len(applicable_casual)} skills (casual voice included)")


async def test_skill_usage_tracking():
    """Test recording skill usage."""

    loader = SkillLoader(db_pool)

    # Record usage
    await loader.record_skill_usage(
        job_id='TEST-001',
        agent_id='agent:copywriter:skilled-001',
        skill_ids=['skill:copywriting:seo', 'skill:structure:content-hierarchy']
    )

    print("✓ Skill usage recorded")

    # Verify in database
    async with db_pool.acquire() as conn:
        logs = await conn.fetch("""
            SELECT * FROM skill_usage_log
            WHERE job_id = 'TEST-001'
        """)

    assert len(logs) == 2, f"Expected 2 log entries, got {len(logs)}"
    print(f"✓ Found {len(logs)} log entries in database")


async def run_all_tests():
    """Run all tests."""

    print("\n=== Testing SkillLoader Service ===\n")

    try:
        await test_get_agent_skills()
        await test_skill_context_composition()
        await test_determine_applicable_skills()
        await test_skill_usage_tracking()

        print("\n✅ All tests passed!\n")
        return True

    except AssertionError as exc:
        print(f"\n❌ Test failed: {exc}\n")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}\n")
        return False


if __name__ == "__main__":
    asyncio.run(run_all_tests())
