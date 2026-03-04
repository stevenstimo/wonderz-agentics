import unittest

from app.services.progress_tracker import compute_progress
from models.unified import JobStatus


class ProgressTrackerTests(unittest.TestCase):
    def test_compute_progress_with_plan_and_steps(self):
        job = {
            "status": JobStatus.RUNNING.value,
            "context": '{"plan":{"steps":[{"step_index":1},{"step_index":2},{"step_index":3}]}}',
        }
        steps = [
            {"step_name": "copy_agent", "status": "success"},
            {"step_name": "copy_agent::prepare", "status": "success"},
            {"step_name": "reviewer_agent", "status": "in_progress"},
        ]

        progress = compute_progress(job, steps)

        self.assertEqual(progress["completed_steps"], 1)
        self.assertEqual(progress["total_steps"], 3)
        self.assertEqual(progress["current_step"], "reviewer_agent")
        self.assertEqual(progress["latest_status"], JobStatus.RUNNING.value)
        self.assertEqual(progress["percent"], 33.3)


class JobStatusTests(unittest.TestCase):
    def test_job_status_includes_cancelled(self):
        self.assertEqual(JobStatus.CANCELLED.value, "CANCELLED")


if __name__ == "__main__":
    unittest.main()
