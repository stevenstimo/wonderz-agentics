#!/bin/bash
# End-to-end test van skills system

echo "=== Skills System E2E Test ==="
echo ""

# Test 1: SEO Website Job
echo "Test 1: SEO Website Job"
curl -X POST http://localhost:8090/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_post": "schrijf 300 woorden over wielrennen voor een website",
    "user_id": "test",
    "source_platform": "website"
  }' | jq '.id'

echo "Created job. Wait 30 seconds for completion..."
sleep 30

# Check skill usage
echo ""
echo "Checking skill usage log..."
PGPASSWORD=wonderz123 psql -h localhost -U wonderz -d wonderz << 'SQL_END'
SELECT 
  l.job_id,
  a.name as agent_name,
  s.name as skill_name,
  s.skill_type
FROM skill_usage_log l
JOIN hired_agents a ON l.agent_id = a.agent_id
JOIN agent_skills s ON l.skill_id = s.skill_id
ORDER BY l.logged_at DESC
LIMIT 10;
SQL_END

echo ""
echo "Expected: SEO skill, structure skill, anti-patterns skill"
echo ""

# Test 2: B2B Job
echo "Test 2: B2B Professional Job"
curl -X POST http://localhost:8090/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_post": "schrijf 400 woorden productbeschrijving",
    "user_id": "test",
    "source_platform": "algemeen",
    "target_audience": "B2B professional"
  }' | jq '.id'

echo "Created B2B job. Wait 30 seconds..."
sleep 30

# Check skill usage again
echo ""
echo "Checking latest skill usage..."
PGPASSWORD=wonderz123 psql -h localhost -U wonderz -d wonderz << 'SQL_END'
SELECT 
  s.name as skill_name,
  COUNT(*) as usage_count
FROM skill_usage_log l
JOIN agent_skills s ON l.skill_id = s.skill_id
GROUP BY s.name
ORDER BY usage_count DESC;
SQL_END

echo ""
echo "Expected: B2B voice skill used in second job"
echo ""

# Check success rates
echo "Checking skill success rates..."
PGPASSWORD=wonderz123 psql -h localhost -U wonderz -d wonderz << 'SQL_END'
SELECT 
  skill_id,
  name,
  domain,
  success_rate,
  usage_count
FROM agent_skills
ORDER BY usage_count DESC, name;
SQL_END

echo ""
echo "=== Test Complete ==="
echo "Success rates should have evolved from initial 0.50"
