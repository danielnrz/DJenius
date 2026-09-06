import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from djenius.application import LocalAppService
from djenius.core.models import SetPlan
from djenius.audio.qa.models import QAResult, QAViolation

@pytest.fixture
def temp_service(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    service = LocalAppService(data_dir=data_dir, output_dir=output_dir)
    return service, str(music_dir)

def test_qa_failure_raises_value_error(temp_service):
    service, music_path = temp_service
    
    with patch("djenius.application.plan_set") as mock_plan_set, \
         patch("djenius.application.run_qa_gate") as mock_run_qa, \
         patch("djenius.application.LocalAppService._profiles_for_library") as mock_profiles:
        
        mock_plan = SetPlan()
        mock_plan_set.return_value = mock_plan
        mock_profiles.return_value = []
        
        qa_result = QAResult(passed=False)
        qa_result.add(QAViolation(module="test", metric="test_metric", threshold=1.0, observed=0.5))
        mock_run_qa.return_value = qa_result
        
        job_id = service.start_plan(library_path=music_path, duration_minutes=2, request="test")
        
        import time
        for _ in range(100):
            job = service.get_job(job_id)
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.01)
        
        assert job["status"] == "failed"
        assert "QA Gate failed before plan storage. Violations: test.test_metric (observed 0.5 vs threshold 1.0)" in job["error"]

def test_qa_success_appends_passed_reason(temp_service):
    service, music_path = temp_service
    
    with patch("djenius.application.plan_set") as mock_plan_set, \
         patch("djenius.application.run_qa_gate") as mock_run_qa, \
         patch("djenius.application.LocalAppService._profiles_for_library") as mock_profiles:
        
        mock_plan = SetPlan()
        mock_plan_set.return_value = mock_plan
        mock_profiles.return_value = []
        
        mock_run_qa.return_value = QAResult(passed=True)
        
        job_id = service.start_plan(library_path=music_path, duration_minutes=2, request="test")
        
        import time
        for _ in range(100):
            job = service.get_job(job_id)
            if job["status"] in ("completed", "failed"):
                break
            time.sleep(0.01)
        
        assert job["status"] == "completed"
        plan_id = job["result"]["id"]
        plan = service.get_plan(plan_id)
        assert "QA Gate Status: PASSED" in plan.human_readable_reasons
