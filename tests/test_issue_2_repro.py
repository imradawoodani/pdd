
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from pdd.fix_error_loop import fix_error_loop

def test_protect_tests_propagation_to_agentic_fallback(tmp_path, monkeypatch):
    """
    Test that the protect_tests flag is propagated to run_agentic_fix
    when fix_error_loop falls back to agentic mode.
    
    This is a regression test for issue #2: 
    "pdd fix: --protect-tests flag is dropped when falling back to agentic mode"
    """
    monkeypatch.chdir(tmp_path)
    
    # Setup minimal files
    code_file = tmp_path / "app.py"
    code_file.write_text("def run(): return False")
    
    test_file = tmp_path / "test_app.py"
    test_file.write_text("from app import run\ndef test_run(): assert run() is True")
    
    prompt_file = tmp_path / "app.prompt"
    prompt_file.write_text("Make app run return True")
    
    error_log = tmp_path / "errors.log"
    
    # Mock dependencies to trigger agentic fallback
    with patch("pdd.fix_error_loop.fix_errors_from_unit_tests") as mock_fix, \
         patch("pdd.fix_error_loop.run_agentic_fix") as mock_agentic, \
         patch("pdd.fix_error_loop.run_pytest_on_file") as mock_pytest:
        
        # Mock initial test failure
        mock_pytest.return_value = (1, 0, 0, "test failed")
        
        # Mock standard loop failure (success=False)
        mock_fix.return_value = (False, False, "", "", "still failing", 0.01, "gpt-4")
        
        # Mock run_agentic_fix to return a valid result
        mock_agentic.return_value = (True, "Fixed", 0.05, "agent", [])
        
        # Call fix_error_loop with protect_tests=True
        fix_error_loop(
            unit_test_file=str(test_file),
            code_file=str(code_file),
            prompt_file=str(prompt_file),
            prompt="Make app run return True",
            verification_program="",
            strength=0.5,
            temperature=0.7,
            max_attempts=1,
            budget=10.0,
            error_log_file=str(error_log),
            agentic_fallback=True,
            protect_tests=True
        )
        
        # Verify run_agentic_fix was called with protect_tests=True
        assert mock_agentic.called
        _, kwargs = mock_agentic.call_args
        assert kwargs.get("protect_tests") is True, "protect_tests flag not passed to run_agentic_fix"

def test_protect_tests_false_propagation(tmp_path, monkeypatch):
    """Verify that protect_tests=False is also propagated correctly."""
    monkeypatch.chdir(tmp_path)
    
    code_file = tmp_path / "app.py"
    code_file.write_text("def run(): return False")
    test_file = tmp_path / "test_app.py"
    test_file.write_text("...")
    prompt_file = tmp_path / "app.prompt"
    prompt_file.write_text("...")
    
    with patch("pdd.fix_error_loop.fix_errors_from_unit_tests") as mock_fix, \
         patch("pdd.fix_error_loop.run_agentic_fix") as mock_agentic, \
         patch("pdd.fix_error_loop.run_pytest_on_file") as mock_pytest:
        
        mock_pytest.return_value = (1, 0, 0, "test failed")
        mock_fix.return_value = (False, False, "", "", "still failing", 0.01, "gpt-4")
        mock_agentic.return_value = (True, "Fixed", 0.05, "agent", [])
        
        fix_error_loop(
            unit_test_file=str(test_file),
            code_file=str(code_file),
            prompt_file=str(prompt_file),
            prompt="...",
            verification_program="",
            strength=0.5,
            temperature=0.7,
            max_attempts=1,
            budget=10.0,
            error_log_file="errors.log",
            agentic_fallback=True,
            protect_tests=False
        )
        
        assert mock_agentic.called
        _, kwargs = mock_agentic.call_args
        assert kwargs.get("protect_tests") is False, "protect_tests=False not passed to run_agentic_fix"
