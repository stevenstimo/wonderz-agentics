"""
Workflow Integration Tests & Validation
Tests the entire end-to-end crew workflow: hiring → training → approval → feedback
"""

import asyncio
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid

# For this demo, we'll validate workflows without actual DB calls
# In production, integrate with your FastAPI/Supabase stack

@dataclass
class WorkflowStep:
    """Represents a single step in the workflow"""
    name: str
    status: str  # pending, in_progress, completed, failed
    description: str
    timestamp: str
    error_msg: Optional[str] = None
    data: Optional[dict] = None


class WorkflowIntegrationValidator:
    """Validates and tests the complete crew management workflow"""
    
    def __init__(self):
        self.workflow_steps: List[WorkflowStep] = []
        self.crew_members: Dict[str, dict] = {}
        self.approval_queue: List[dict] = []
        self.training_sessions: Dict[str, dict] = {}
        self.improvement_records: Dict[str, list] = {}
        self.test_results: Dict[str, bool] = {}
    
    def log_step(self, name: str, status: str, description: str, error_msg: Optional[str] = None, data: Optional[dict] = None):
        """Log a workflow step"""
        step = WorkflowStep(
            name=name,
            status=status,
            description=description,
            timestamp=datetime.now().isoformat(),
            error_msg=error_msg,
            data=data
        )
        self.workflow_steps.append(step)
        status_emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
        print(f"{status_emoji} [{name}] {description}" + (f" (Error: {error_msg})" if error_msg else ""))
    
    # ========================================
    # STEP 1: Hiring Workflow
    # ========================================
    
    def validate_hire_agent_request(self, hire_data: dict) -> bool:
        """Validate hire agent request data"""
        required_fields = ["name", "role"]
        
        # Check required fields
        for field in required_fields:
            if field not in hire_data or not hire_data[field]:
                self.log_step("validate_hire", "failed", f"Missing required field: {field}", error_msg=f"Field '{field}' is required")
                return False
        
        # Validate role
        valid_roles = ["Developer", "Product Owner", "Reviewer", "DevOps", "AI"] 
        if hire_data.get("role") not in valid_roles:
            self.log_step("validate_hire", "failed", f"Invalid role: {hire_data['role']}", error_msg=f"Role must be one of {valid_roles}")
            return False
        
        # Check specialization if provided
        if "specialization" in hire_data and hire_data["specialization"] and len(hire_data["specialization"]) > 200:
            self.log_step("validate_hire", "failed", "Specialization too long", error_msg="Specialization must be <= 200 characters")
            return False
        
        self.log_step("validate_hire", "completed", f"Validated hire request for {hire_data['name']}", data=hire_data)
        return True
    
    async def workflow_hire_agent(self, hire_data: dict) -> str:
        """Execute hiring workflow"""
        if not self.validate_hire_agent_request(hire_data):
            return None
        
        crew_id = f"crew_{uuid.uuid4().hex[:8]}"
        self.crew_members[crew_id] = {
            "id": crew_id,
            "name": hire_data["name"],
            "role": hire_data["role"],
            "specialization": hire_data.get("specialization", ""),
            "status": "active",
            "hired_at": datetime.now().isoformat(),
            "performance_score": 0,
            "completed_tasks": 0
        }
        self.improvement_records[crew_id] = []
        
        self.log_step("hire_agent", "completed", f"Hired {hire_data['name']} with ID {crew_id}", data=self.crew_members[crew_id])
        return crew_id
    
    # ========================================
    # STEP 2: Training Request & Approval
    # ========================================
    
    def validate_training_request(self, training_data: dict) -> tuple[bool, str]:
        """Validate training request"""
        required_fields = ["crew_id", "agent_name", "training_url"]
        
        # Check required fields
        for field in required_fields:
            if field not in training_data or not training_data[field]:
                error_msg = f"Missing required field: {field}"
                self.log_step("validate_training", "failed", error_msg, error_msg=error_msg)
                return False, error_msg
        
        # Validate crew_id exists
        if training_data["crew_id"] not in self.crew_members:
            error_msg = f"Crew member {training_data['crew_id']} not found"
            self.log_step("validate_training", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        # Validate URL format
        training_url = training_data["training_url"]
        if not (training_url.startswith("http://") or training_url.startswith("https://")):
            error_msg = "Training URL must start with http:// or https://"
            self.log_step("validate_training", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        self.log_step("validate_training", "completed", f"Validated training request for {training_data['agent_name']}", data=training_data)
        return True, ""
    
    async def workflow_request_training(self, training_data: dict) -> tuple[str, str]:
        """Execute training request workflow"""
        valid, error = self.validate_training_request(training_data)
        if not valid:
            return None, None
        
        session_id = f"train_{uuid.uuid4().hex[:12]}"
        self.training_sessions[session_id] = {
            "session_id": session_id,
            "crew_id": training_data["crew_id"],
            "agent_name": training_data["agent_name"],
            "training_url": training_data["training_url"],
            "training_title": training_data.get("training_title", "Untitled"),
            "status": "pending",
            "approval_status": "pending",
            "requested_at": datetime.now().isoformat(),
            "approved_at": None,
            "completed_at": None
        }
        
        # Auto-register approval request
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        self.approval_queue.append({
            "approval_id": approval_id,
            "request_type": "training",
            "status": "pending",
            "details": {
                "session_id": session_id,
                "agent": training_data["agent_name"],
                "url": training_data["training_url"]
            },
            "requested_at": datetime.now().isoformat(),
            "approved_at": None,
            "rejected_at": None
        })
        
        self.log_step("request_training", "completed", f"Training request {session_id} created, awaiting CEO approval", 
                      data={"session_id": session_id, "approval_id": approval_id})
        
        return session_id, approval_id
    
    # ========================================
    # STEP 3: CEO Approval Decision
    # ========================================
    
    async def workflow_ceo_decision(self, approval_id: str, approved: bool) -> bool:
        """Execute CEO approval decision"""
        # Find approval
        approval = None
        for appr in self.approval_queue:
            if appr["approval_id"] == approval_id:
                approval = appr
                break
        
        if not approval:
            self.log_step("ceo_decision", "failed", f"Approval {approval_id} not found", 
                          error_msg=f"Approval request not found")
            return False
        
        if approval["status"] != "pending":
            self.log_step("ceo_decision", "failed", f"Cannot decide on non-pending approval", 
                          error_msg=f"Approval status is {approval['status']}, not pending")
            return False
        
        # Update approval
        approval["status"] = "approved" if approved else "rejected"
        approval["approved_at" if approved else "rejected_at"] = datetime.now().isoformat()
        
        # If training approval, update training session status
        if approval["request_type"] == "training":
            session_id = approval["details"]["session_id"]
            if session_id in self.training_sessions:
                self.training_sessions[session_id]["approval_status"] = "approved" if approved else "rejected"
                if approved:
                    self.training_sessions[session_id]["status"] = "in_progress"
                    self.training_sessions[session_id]["approved_at"] = datetime.now().isoformat()
        
        decision_text = "approved" if approved else "rejected"
        self.log_step("ceo_decision", "completed", f"CEO {decision_text} approval {approval_id}", 
                      data={"approval_id": approval_id, "decision": decision_text})
        
        return True
    
    # ========================================
    # STEP 4: Training Completion
    # ========================================
    
    def validate_complete_training(self, session_id: str, knowledge_base: str) -> tuple[bool, str]:
        """Validate training completion request"""
        if session_id not in self.training_sessions:
            error_msg = f"Training session {session_id} not found"
            self.log_step("validate_complete", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        session = self.training_sessions[session_id]
        
        # Verify approval status
        if session["approval_status"] != "approved":
            error_msg = f"Cannot complete training that is not approved. Status: {session['approval_status']}"
            self.log_step("validate_complete", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        # Validate knowledge base content
        if not knowledge_base or len(knowledge_base.strip()) == 0:
            error_msg = "Knowledge base content cannot be empty"
            self.log_step("validate_complete", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        self.log_step("validate_complete", "completed", f"Validated completion for {session_id}", 
                      data={"session_id": session_id})
        return True, ""
    
    async def workflow_complete_training(self, session_id: str, knowledge_base: str) -> bool:
        """Execute training completion workflow"""
        valid, error = self.validate_complete_training(session_id, knowledge_base)
        if not valid:
            return False
        
        session = self.training_sessions[session_id]
        session["status"] = "completed"
        session["knowledge_base"] = knowledge_base
        session["completed_at"] = datetime.now().isoformat()
        
        self.log_step("complete_training", "completed", f"Training {session_id} marked as completed", 
                      data={"session_id": session_id})
        
        return True
    
    # ========================================
    # STEP 5: HR Performance Analysis & Feedback
    # ========================================
    
    def validate_performance_analysis_request(self, agent_id: str, performance_data: dict) -> tuple[bool, str]:
        """Validate performance analysis request"""
        if agent_id not in self.crew_members:
            error_msg = f"Agent {agent_id} not found"
            self.log_step("validate_perf_analysis", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        # Check required performance metrics
        if not performance_data or not isinstance(performance_data, dict):
            error_msg = "Performance data must be a non-empty dictionary"
            self.log_step("validate_perf_analysis", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        self.log_step("validate_perf_analysis", "completed", f"Validated performance analysis for {agent_id}", 
                      data={"agent_id": agent_id})
        return True, ""
    
    async def workflow_hr_feedback(self, agent_id: str, performance_data: dict, feedback: str) -> bool:
        """Execute HR feedback workflow"""
        valid, error = self.validate_performance_analysis_request(agent_id, performance_data)
        if not valid:
            return False
        
        improvement_record = {
            "id": f"imp_{uuid.uuid4().hex[:8]}",
            "agent_id": agent_id,
            "title": "Performance Feedback",
            "summary": feedback[:100],
            "details": feedback,
            "severity": "medium",
            "status": "open",
            "source": "hr_agent",
            "created_at": datetime.now().isoformat()
        }
        
        self.improvement_records[agent_id].append(improvement_record)
        
        self.log_step("hr_feedback", "completed", f"HR feedback registered for {agent_id}", 
                      data=improvement_record)
        
        return True
    
    # ========================================
    # STEP 6: Error Recovery & Workflow Branching
    # ========================================
    
    async def workflow_rejection_resubmit(self, approval_id: str) -> tuple[bool, str]:
        """Handle rejection and allow resubmission"""
        # Find the rejected approval
        rejected_approval = None
        for appr in self.approval_queue:
            if appr["approval_id"] == approval_id and appr["status"] == "rejected":
                rejected_approval = appr
                break
        
        if not rejected_approval:
            error_msg = f"No rejected approval found with ID {approval_id}"
            self.log_step("resubmit_rejected", "failed", error_msg, error_msg=error_msg)
            return False, error_msg
        
        # Create new approval with same details
        new_approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        new_approval = {
            "approval_id": new_approval_id,
            "request_type": rejected_approval["request_type"],
            "status": "pending",
            "details": rejected_approval["details"].copy(),
            "requested_at": datetime.now().isoformat(),
            "approved_at": None,
            "rejected_at": None
        }
        self.approval_queue.append(new_approval)
        
        self.log_step("resubmit_rejected", "completed", f"Resubmitted {rejected_approval['request_type']} request as {new_approval_id}", 
                      data={"original_id": approval_id, "new_approval_id": new_approval_id})
        
        return True, new_approval_id
    
    # ========================================
    # END-TO-END WORKFLOW TEST
    # ========================================
    
    async def run_complete_workflow_test(self) -> Dict[str, any]:
        """Run a complete end-to-end workflow test"""
        print("\n" + "="*80)
        print("WORKFLOW INTEGRATION TEST - COMPLETE CYCLE")
        print("="*80 + "\n")
        
        try:
            # Step 1: Hire an agent
            print("📋 STEP 1: Hiring Agent")
            print("-" * 40)
            agent_id = await self.workflow_hire_agent({
                "name": "Sophia Developer",
                "role": "Developer",
                "specialization": "Python & FastAPI"
            })
            if not agent_id:
                self.test_results["hire"] = False
                return self._generate_report()
            self.test_results["hire"] = True
            
            # Step 2: Request training
            print("\n📚 STEP 2: Requesting Training")
            print("-" * 40)
            session_id, approval_id = await self.workflow_request_training({
                "crew_id": agent_id,
                "agent_name": "Sophia Developer",
                "training_url": "https://docs.python.org/3/",
                "training_title": "Advanced Python Patterns"
            })
            if not session_id:
                self.test_results["request_training"] = False
                return self._generate_report()
            self.test_results["request_training"] = True
            
            # Step 3: CEO approves training
            print("\n✅ STEP 3: CEO Approves Training")
            print("-" * 40)
            approved = await self.workflow_ceo_decision(approval_id, approved=True)
            if not approved:
                self.test_results["ceo_approval"] = False
                return self._generate_report()
            self.test_results["ceo_approval"] = True
            
            # Step 4: Agent completes training
            print("\n🎓 STEP 4: Agent Completes Training")
            print("-" * 40)
            completed = await self.workflow_complete_training(
                session_id,
                "Learned: generators, decorators, async/await patterns; Applied context managers to resource management"
            )
            if not completed:
                self.test_results["complete_training"] = False
                return self._generate_report()
            self.test_results["complete_training"] = True
            
            # Step 5: HR collects and registers feedback
            print("\n👥 STEP 5: HR Feedback Collection")
            print("-" * 40)
            feedback_success = await self.workflow_hr_feedback(
                agent_id,
                {
                    "tasks_completed": 15,
                    "success_rate": 0.92,
                    "quality_score": 8.5,
                    "error_count": 2
                },
                "Sophia shows strong technical growth post-training. Recommend advanced async patterns training."
            )
            if not feedback_success:
                self.test_results["hr_feedback"] = False
                return self._generate_report()
            self.test_results["hr_feedback"] = True
            
            # Step 6: Test rejection and resubmission
            print("\n⚠️  STEP 6: Testing Rejection & Resubmission")
            print("-" * 40)
            
            # Create another training request
            session_id_2, approval_id_2 = await self.workflow_request_training({
                "crew_id": agent_id,
                "agent_name": "Sophia Developer",
                "training_url": "https://docs.sqlalchemy.org/",
                "training_title": "SQLAlchemy ORM Mastery"
            })
            
            # CEO rejects it
            rejected = await self.workflow_ceo_decision(approval_id_2, approved=False)
            if not rejected:
                self.test_results["rejection"] = False
                return self._generate_report()
            
            # Resubmit
            resubmit_success, new_approval_id = await self.workflow_rejection_resubmit(approval_id_2)
            if resubmit_success:
                # CEO approves the resubmission
                await self.workflow_ceo_decision(new_approval_id, approved=True)
                self.test_results["resubmit"] = True
            else:
                self.test_results["resubmit"] = False
            
            # All steps passed
            self.test_results["overall"] = True
            
        except Exception as e:
            print(f"\n❌ WORKFLOW TEST FAILED: {str(e)}")
            self.test_results["overall"] = False
        
        return self._generate_report()
    
    def _generate_report(self) -> Dict[str, any]:
        """Generate workflow test report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(self.workflow_steps),
            "completed_steps": sum(1 for s in self.workflow_steps if s.status == "completed"),
            "failed_steps": sum(1 for s in self.workflow_steps if s.status == "failed"),
            "test_results": self.test_results,
            "workflow_steps": [
                {
                    "name": s.name,
                    "status": s.status,
                    "description": s.description,
                    "timestamp": s.timestamp,
                    "error": s.error_msg,
                    "data": s.data
                } for s in self.workflow_steps
            ],
            "crew_members": self.crew_members,
            "training_sessions": self.training_sessions,
            "improvements": self.improvement_records,
            "approval_queue": self.approval_queue,
            "summary": {
                "success": self.test_results.get("overall", False),
                "hire_success": self.test_results.get("hire", False),
                "training_success": self.test_results.get("request_training", False),
                "approval_success": self.test_results.get("ceo_approval", False),
                "completion_success": self.test_results.get("complete_training", False),
                "feedback_success": self.test_results.get("hr_feedback", False),
                "error_handling_success": self.test_results.get("resubmit", False)
            }
        }
        
        return report
    
    def print_report(self, report: Dict[str, any]):
        """Print formatted workflow test report"""
        print("\n" + "="*80)
        print("WORKFLOW TEST REPORT")
        print("="*80)
        
        summary = report["summary"]
        print(f"\n📊 OVERALL RESULT: {'✅ PASSED' if summary['success'] else '❌ FAILED'}")
        print(f"\nTest Results:")
        print(f"  Hiring: {'✅' if summary['hire_success'] else '❌'}")
        print(f"  Training Request: {'✅' if summary['training_success'] else '❌'}")
        print(f"  CEO Approval: {'✅' if summary['approval_success'] else '❌'}")
        print(f"  Training Completion: {'✅' if summary['completion_success'] else '❌'}")
        print(f"  HR Feedback: {'✅' if summary['feedback_success'] else '❌'}")
        print(f"  Error Recovery: {'✅' if summary['error_handling_success'] else '❌'}")
        
        print(f"\nWorkflow Statistics:")
        print(f"  Total Steps: {report['total_steps']}")
        print(f"  Completed: {report['completed_steps']}")
        print(f"  Failed: {report['failed_steps']}")
        
        print(f"\nCrew Members Created: {len(report['crew_members'])}")
        print(f"Training Sessions: {len(report['training_sessions'])}")
        print(f"Improvements Registered: {sum(len(v) for v in report['improvements'].values())}")
        
        print("\n" + "="*80)


# Run workflow test if executed directly
if __name__ == "__main__":
    validator = WorkflowIntegrationValidator()
    report = asyncio.run(validator.run_complete_workflow_test())
    validator.print_report(report)
    
    # Write report to JSON
    output_dir = os.getenv("TEST_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "workflow_test_report.json")
    with open(output_file, "w") as f:
        # Convert datetime objects to strings for JSON serialization
        def serialize_report(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")
        
        json.dump(report, f, indent=2, default=serialize_report)
    
    print(f"\n📄 Full report saved to: {output_file}")
