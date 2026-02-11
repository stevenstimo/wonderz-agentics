#!/usr/bin/env python3
"""
Run Workflow Integration Tests
Execute with: python web-ui/backend/test_workflow_integration.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_integration import WorkflowIntegrationValidator


async def main():
    """Run the complete workflow integration test"""
    print("\n🚀 Starting Workflow Integration Tests...\n")
    
    validator = WorkflowIntegrationValidator()
    report = await validator.run_complete_workflow_test()
    
    # Print detailed report
    validator.print_report(report)
    
    # Return exit code based on success
    if report["summary"]["success"]:
        print("\n✅ All workflow tests PASSED!")
        return 0
    else:
        print("\n❌ Some workflow tests FAILED!")
        print("\nFailed steps:")
        for step in report["workflow_steps"]:
            if step["status"] == "failed":
                print(f"  - {step['name']}: {step['error']}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
