"""
API Endpoint Validation & Error Handling Tests
Tests all endpoints for proper error handling, input validation, and response formats
"""

import json
import os
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestCase:
    """Represents a single test case"""
    name: str
    endpoint: str
    method: str
    payload: dict
    expected_status: int
    should_pass: bool
    description: str


class APIValidationTester:
    """Validates API endpoints for error handling and input validation"""
    
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.results: List[Dict[str, Any]] = []
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case"""
        self.test_cases.append(test_case)
    
    def generate_crew_test_cases(self) -> List[TestCase]:
        """Generate crew endpoint test cases"""
        return [
            # Valid cases
            TestCase(
                name="Crew: Create valid member",
                endpoint="/api/crew",
                method="POST",
                payload={"name": "Alice Developer", "role": "Developer", "specialization": "Python"},
                expected_status=200,
                should_pass=True,
                description="Should successfully create crew member with valid data"
            ),
            # Invalid cases
            TestCase(
                name="Crew: Create with empty name",
                endpoint="/api/crew",
                method="POST",
                payload={"name": "", "role": "Developer"},
                expected_status=422,
                should_pass=False,
                description="Should reject empty name"
            ),
            TestCase(
                name="Crew: Create with invalid role",
                endpoint="/api/crew",
                method="POST",
                payload={"name": "Bob", "role": "InvalidRole"},
                expected_status=422,
                should_pass=False,
                description="Should reject invalid role"
            ),
            TestCase(
                name="Crew: Create with long name",
                endpoint="/api/crew",
                method="POST",
                payload={"name": "A" * 150, "role": "Developer"},
                expected_status=422,
                should_pass=False,
                description="Should reject name exceeding 100 characters"
            ),
            TestCase(
                name="Crew: Get with invalid crew_id",
                endpoint="/api/crew/invalid_id",
                method="GET",
                payload={},
                expected_status=404,
                should_pass=False,
                description="Should return 404 for non-existent crew member"
            ),
            TestCase(
                name="Crew: Update with invalid status",
                endpoint="/api/crew/crew_123",
                method="PUT",
                payload={"status": "unknown_status"},
                expected_status=422,
                should_pass=False,
                description="Should reject invalid status value"
            ),
            TestCase(
                name="Crew: Update with invalid progress",
                endpoint="/api/crew/crew_123",
                method="PUT",
                payload={"progress": 150},
                expected_status=422,
                should_pass=False,
                description="Should reject progress > 100"
            ),
        ]
    
    def generate_training_test_cases(self) -> List[TestCase]:
        """Generate training endpoint test cases"""
        return [
            # Valid cases
            TestCase(
                name="Training: Request with valid data",
                endpoint="/api/training/request",
                method="POST",
                payload={
                    "crew_id": "dev_123",
                    "agent_name": "Alice",
                    "training_url": "https://example.com/training",
                    "training_title": "Advanced Python"
                },
                expected_status=200,
                should_pass=True,
                description="Should create training session with valid data"
            ),
            # Invalid cases
            TestCase(
                name="Training: Request with empty crew_id",
                endpoint="/api/training/request",
                method="POST",
                payload={
                    "crew_id": "",
                    "agent_name": "Alice",
                    "training_url": "https://example.com"
                },
                expected_status=422,
                should_pass=False,
                description="Should reject empty crew_id"
            ),
            TestCase(
                name="Training: Request with invalid URL",
                endpoint="/api/training/request",
                method="POST",
                payload={
                    "crew_id": "dev_123",
                    "agent_name": "Alice",
                    "training_url": "invalid-url-without-protocol"
                },
                expected_status=422,
                should_pass=False,
                description="Should reject URL without http/https"
            ),
            TestCase(
                name="Training: Request with very long URL",
                endpoint="/api/training/request",
                method="POST",
                payload={
                    "crew_id": "dev_123",
                    "agent_name": "Alice",
                    "training_url": "https://example.com/" + "a" * 2100
                },
                expected_status=422,
                should_pass=False,
                description="Should reject URL exceeding 2048 characters"
            ),
            TestCase(
                name="Training: Complete with empty knowledge_base",
                endpoint="/api/training/train_abc123/complete",
                method="POST",
                payload={"session_id": "train_abc123", "knowledge_base": ""},
                expected_status=422,
                should_pass=False,
                description="Should reject empty knowledge base content"
            ),
            TestCase(
                name="Training: Complete with oversized knowledge_base",
                endpoint="/api/training/train_abc123/complete",
                method="POST",
                payload={
                    "session_id": "train_abc123",
                    "knowledge_base": "X" * 11000
                },
                expected_status=422,
                should_pass=False,
                description="Should reject knowledge base exceeding 10000 characters"
            ),
        ]
    
    def generate_hr_test_cases(self) -> List[TestCase]:
        """Generate HR endpoint test cases"""
        return [
            # Valid cases
            TestCase(
                name="HR: Analyze performance with valid data",
                endpoint="/api/hr/analyze-performance",
                method="POST",
                payload={
                    "agent_id": "dev_123",
                    "agent_name": "Alice Developer",
                    "performance_data": {
                        "tasks_completed": 15,
                        "success_rate": 0.92,
                        "quality_score": 8.5
                    }
                },
                expected_status=200,
                should_pass=True,
                description="Should analyze performance with valid metrics"
            ),
            # Invalid cases
            TestCase(
                name="HR: Analyze with empty agent_id",
                endpoint="/api/hr/analyze-performance",
                method="POST",
                payload={
                    "agent_id": "",
                    "agent_name": "Alice",
                    "performance_data": {"success_rate": 0.9}
                },
                expected_status=422,
                should_pass=False,
                description="Should reject empty agent_id"
            ),
            TestCase(
                name="HR: Analyze with empty performance_data",
                endpoint="/api/hr/analyze-performance",
                method="POST",
                payload={
                    "agent_id": "dev_123",
                    "agent_name": "Alice",
                    "performance_data": {}
                },
                expected_status=422,
                should_pass=False,
                description="Should reject empty performance_data"
            ),
            TestCase(
                name="HR: Register improvement with invalid severity",
                endpoint="/api/hr/register-improvement",
                method="POST",
                payload={
                    "agent_id": "dev_123",
                    "agent_name": "Alice",
                    "title": "Improve error handling",
                    "severity": "minor"
                },
                expected_status=422,
                should_pass=False,
                description="Should reject invalid severity level"
            ),
            TestCase(
                name="HR: Register improvement with empty title",
                endpoint="/api/hr/register-improvement",
                method="POST",
                payload={
                    "agent_id": "dev_123",
                    "agent_name": "Alice",
                    "title": ""
                },
                expected_status=422,
                should_pass=False,
                description="Should reject empty title"
            ),
        ]
    
    def generate_ceo_test_cases(self) -> List[TestCase]:
        """Generate CEO endpoint test cases"""
        return [
            # Valid cases
            TestCase(
                name="CEO: Make plan with valid project",
                endpoint="/api/ceo/plan",
                method="POST",
                payload={
                    "project_idea": "Build a scalable shoe store website",
                    "context": {"platform": "Shopify", "budget": "$50k"}
                },
                expected_status=200,
                should_pass=True,
                description="Should create project plan"
            ),
            # Invalid cases
            TestCase(
                name="CEO: Make plan with empty project_idea",
                endpoint="/api/ceo/plan",
                method="POST",
                payload={"project_idea": ""},
                expected_status=422,
                should_pass=False,
                description="Should reject empty project_idea"
            ),
            TestCase(
                name="CEO: Make plan with oversized idea",
                endpoint="/api/ceo/plan",
                method="POST",
                payload={"project_idea": "X" * 1500},
                expected_status=422,
                should_pass=False,
                description="Should reject project_idea exceeding 1000 characters"
            ),
            TestCase(
                name="CEO: Hire agent with valid role",
                endpoint="/api/ceo/hire",
                method="POST",
                payload={
                    "name": "Charlie Developer",
                    "role": "Developer",
                    "specialization": "FastAPI"
                },
                expected_status=200,
                should_pass=True,
                description="Should hire new agent"
            ),
            TestCase(
                name="CEO: Hire with invalid role",
                endpoint="/api/ceo/hire",
                method="POST",
                payload={
                    "name": "Charlie",
                    "role": "UnknownRole"
                },
                expected_status=422,
                should_pass=False,
                description="Should reject invalid role"
            ),
            TestCase(
                name="CEO: Request approval with invalid type",
                endpoint="/api/ceo/approval/request",
                method="POST",
                payload={
                    "request_type": "invalid_type",
                    "details": {"reason": "test"}
                },
                expected_status=422,
                should_pass=False,
                description="Should reject invalid request_type"
            ),
        ]
    
    def generate_all_test_cases(self) -> List[TestCase]:
        """Generate all test cases"""
        all_cases = []
        all_cases.extend(self.generate_crew_test_cases())
        all_cases.extend(self.generate_training_test_cases())
        all_cases.extend(self.generate_hr_test_cases())
        all_cases.extend(self.generate_ceo_test_cases())
        return all_cases
    
    def print_test_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("API ENDPOINT VALIDATION TEST CASES GENERATED")
        print("="*80 + "\n")
        
        total = len(self.test_cases)
        by_endpoint = {}
        
        for test in self.test_cases:
            endpoint = test.endpoint.split('?')[0]  # Remove query params
            if endpoint not in by_endpoint:
                by_endpoint[endpoint] = []
            by_endpoint[endpoint].append(test)
        
        print(f"Total test cases: {total}\n")
        
        for endpoint in sorted(by_endpoint.keys()):
            tests = by_endpoint[endpoint]
            print(f"📍 {endpoint}")
            for test in tests:
                status_indicator = "✅" if test.should_pass else "❌"
                print(f"  {status_indicator} {test.name}")
                print(f"     └─ {test.description}")
            print()
        
        # Generate test categories
        valid_tests = sum(1 for t in self.test_cases if t.should_pass)
        invalid_tests = sum(1 for t in self.test_cases if not t.should_pass)
        
        print(f"Valid Input Tests: {valid_tests}")
        print(f"Error Handling Tests: {invalid_tests}")
        print("\n" + "="*80)
    
    def export_test_cases_to_json(self, filepath: str):
        """Export test cases to JSON for use in test runners"""
        test_data = {
            "generated_at": datetime.now().isoformat(),
            "total_tests": len(self.test_cases),
            "tests": [
                {
                    "name": test.name,
                    "endpoint": test.endpoint,
                    "method": test.method,
                    "payload": test.payload,
                    "expected_status": test.expected_status,
                    "should_pass": test.should_pass,
                    "description": test.description
                }
                for test in self.test_cases
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print(f"\n💾 Test cases exported to: {filepath}")


# Run if executed directly
if __name__ == "__main__":
    tester = APIValidationTester()
    tester.test_cases = tester.generate_all_test_cases()
    tester.print_test_summary()
    
    # Export for use with pytest or similar
    output_dir = os.getenv("TEST_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "api_test_cases.json")
    tester.export_test_cases_to_json(output_file)
