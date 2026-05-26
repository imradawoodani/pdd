
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure we can import from the project
sys.path.append(str(Path(__file__).parent.parent))

# Mock necessary modules that might be imported and cause issues in test environment
sys.modules["pdd.track_cost"] = MagicMock()
sys.modules["pdd.operation_log"] = MagicMock()

from pdd.fix_error_loop import _safe_run_agentic_fix

def test_protect_tests_propagation_to_agentic_fallback():
    """
    Test that the protect_tests flag is correctly propagated to run_agentic_fix
    during the agentic fallback phase.
    """
    # We want to verify that when _safe_run_agentic_fix is called, 
    # it passes protect_tests to run_agentic_fix.
    
    # Note: Currently _safe_run_agentic_fix does NOT accept protect_tests,
    # so we'll first test if we can even pass it (it should fail if not updated).
    # Then we'll mock run_agentic_fix to see what it receives.
    
    with patch("pdd.fix_error_loop.run_agentic_fix") as mock_run_agentic:
        mock_run_agentic.return_value = (True, "Success", 0.0, "model", [])
        
        # In a real scenario, fix_error_loop would call _safe_run_agentic_fix
        # We want to ensure _safe_run_agentic_fix can handle protect_tests=True
        try:
            _safe_run_agentic_fix(
                prompt_file="test.prompt",
                code_file="test.py",
                unit_test_file="test_test.py",
                error_log_file="error.log",
                protect_tests=True  # This is what's missing in the signature
            )
        except TypeError as e:
            pytest.fail(f"protect_tests parameter is missing from _safe_run_agentic_fix signature: {e}")
            
        # Verify that protect_tests=True was passed to run_agentic_fix
        args, kwargs = mock_run_agentic.call_args
        assert kwargs.get("protect_tests") is True, "protect_tests flag was not propagated to run_agentic_fix"

def test_fix_error_loop_passes_protect_tests_to_fallback():
    """
    Test that fix_error_loop passes its protect_tests argument to _safe_run_agentic_fix.
    """
    from pdd.fix_error_loop import fix_error_loop
    
    # Mock dependencies of fix_error_loop
    with patch("pdd.fix_error_loop.run_pytest_on_file") as mock_pytest, \
         patch("pdd.fix_error_loop._safe_run_agentic_fix") as mock_safe_agentic, \
         patch("pdd.fix_error_loop.os.path.isfile", return_value=True), \
         patch("pdd.fix_error_loop.os.path.exists", return_value=True), \
         patch("pdd.fix_error_loop.os.remove"), \
         patch("builtins.open", MagicMock()):
        
        # Set up mocks to trigger agentic fallback
        # Initial test fails
        mock_pytest.return_value = (1, 0, 0, "Initial failure")
        # Agentic fallback succeeds
        mock_safe_agentic.return_value = (True, "Agent fixed it", 0.5, "agent-model", ["test.py"])
        
        # Call fix_error_loop with protect_tests=True and max_attempts=0 to trigger fallback immediately
        # (or max_attempts=1 and make the loop fail)
        fix_error_loop(
            unit_test_file="test_test.py",
            code_file="test.py",
            prompt_file="test.prompt",
            prompt="fix it",
            verification_program="verify.py",
            strength=0.5,
            temperature=0.0,
            max_attempts=0, # Trigger fallback immediately
            budget=10.0,
            protect_tests=True,
            agentic_fallback=True
        )
        
        # Verify _safe_run_agentic_fix was called with protect_tests=True
        assert mock_safe_agentic.called
        kwargs = mock_safe_agentic.call_args.kwargs
        assert kwargs.get("protect_tests") is True, "fix_error_loop did not pass protect_tests to _safe_run_agentic_fix"
