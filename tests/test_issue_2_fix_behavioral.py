import os
import shutil
from pathlib import Path
import subprocess
from unittest.mock import patch, MagicMock
import pytest
import sys
from click.testing import CliRunner

# Ensure we can import from the project
sys.path.append(str(Path(__file__).parent.parent))

from pdd.fix_error_loop import fix_error_loop, _safe_run_agentic_fix
from pdd.agentic_fix import run_agentic_fix
from pdd.commands.fix import fix

# --- Helpers and Mocks ---

def _df():
    import pandas as pd
    return pd.DataFrame(
        [
            {"provider": "anthropic", "model": "claude-3",   "api_key": "ANTHROPIC_API_KEY"},
            {"provider": "google",    "model": "gemini-pro", "api_key": "GOOGLE_API_KEY"},
            {"provider": "openai",    "model": "gpt-4",      "api_key": "OPENAI_API_KEY"},
        ]
    )

def _prep_files(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    code   = tmp_path / "buggy.py"
    testf  = tmp_path / "test_file.py"
    err    = tmp_path / "error.log"
    prompt.write_text("prompt", encoding="utf-8")
    code.write_text("print('bug')\n", encoding="utf-8")
    testf.write_text("assert True\n", encoding="utf-8")
    err.write_text("", encoding="utf-8")
    return str(prompt), str(code), str(testf), str(err)

@pytest.fixture
def mock_files(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    code_file = d / "code.py"
    test_file = d / "test_code.py"
    prompt_file = d / "prompt.txt"
    
    code_file.write_text("def foo(): return 1")
    test_file.write_text("def test_foo(): assert foo() == 1")
    prompt_file.write_text("Write foo")
    
    return str(code_file), str(test_file), str(prompt_file)

@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    # Ensure we use the prompts and data from the worktree
    monkeypatch.setenv("PDD_PATH", str(Path(__file__).parent.parent))
    monkeypatch.setenv("PDD_AGENTIC_LOGLEVEL", "quiet")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

# --- Step 8 Planned Tests ---

# Test 1: fix_error_loop propagates protect_tests to agentic fallback
@patch("pdd.fix_error_loop.run_pytest_on_file")
@patch("pdd.fix_error_loop._safe_run_agentic_fix")
def test_fix_error_loop_propagates_protect_tests(mock_safe_agentic, mock_pytest, mock_files, tmp_path):
    """
    Test 1: Verify that fix_error_loop propagates the protect_tests flag
    to the agentic fallback wrapper.
    """
    code, test, prompt = mock_files
    # Mock pytest to fail initially to trigger fix loop
    mock_pytest.return_value = (1, 0, 0, "Fail")
    
    # Mock _safe_run_agentic_fix to succeed
    mock_safe_agentic.return_value = (True, "Fixed", 0.1, "agent", [])
    
    # Mock fix_errors_from_unit_tests to fail to trigger fallback
    with patch("pdd.fix_error_loop.fix_errors_from_unit_tests") as mock_fix:
        mock_fix.return_value = (False, False, "", "", "No fix", 0.1, "model")
        
        fix_error_loop(
            test, code, prompt, "prompt", "verify.py", 0.5, 0.1, 0, 1.0,
            agentic_fallback=True,
            protect_tests=True,
            error_log_file=str(tmp_path / "err.log")
        )
        
        # Verify _safe_run_agentic_fix was called with protect_tests=True
        assert mock_safe_agentic.called
        kwargs = mock_safe_agentic.call_args.kwargs
        assert kwargs.get("protect_tests") is True, "BUG: protect_tests=True was not passed to _safe_run_agentic_fix"

# Test 2: agentic_fix instruction file content honors protect_tests
def test_agentic_fix_instruction_content_honors_protect_tests(tmp_path, monkeypatch):
    """
    Test 2: Verify that when fix_error_loop triggers agentic fallback with protect_tests=True,
    the generated instruction file explicitly includes Test Protection Mode: true.
    """
    p_prompt, p_code, p_test, p_err = _prep_files(tmp_path)
    
    # Mock dependencies to trigger fallback
    monkeypatch.setattr("pdd.agentic_fix._load_model_data", lambda _: _df())
    monkeypatch.setattr("pdd.fix_error_loop.run_pytest_on_file", lambda *a, **k: (1, 0, 0, "Fail"))
    monkeypatch.setattr("pdd.fix_error_loop.fix_errors_from_unit_tests", lambda *a, **k: (False, False, "", "", "No fix", 0.1, "model"))
    monkeypatch.setattr("pdd.agentic_fix.run_agentic_task", lambda instruction, **kwargs: (True, "output", 0.05, "anthropic"))
    monkeypatch.setattr("pdd.agentic_fix._verify_and_log", lambda *a, **k: True)
    monkeypatch.setattr("pdd.agentic_common._find_cli_binary", lambda cmd, config=None: "/usr/bin/shim")
    
    # Capture the instruction file content before it is unlinked
    captured_content = []
    original_write_text = Path.write_text
    def mock_write_text(self, content, *args, **kwargs):
        if "agentic_fix_instructions.txt" in str(self):
            captured_content.append(content)
        return original_write_text(self, content, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", mock_write_text)
    
    fix_error_loop(
        p_test, p_code, p_prompt, "prompt", "verify.py", 0.5, 0.1, 0, 1.0,
        agentic_fallback=True,
        protect_tests=True,
        error_log_file=str(tmp_path / "err.log")
    )
    
    assert len(captured_content) > 0, "Instruction file was never written"
    content = captured_content[0]
    
    # THE BUG: fix_error_loop currently drops protect_tests when calling _safe_run_agentic_fix,
    # so content will contain "## Test Protection Mode: false"
    # THE FIX: it should contain "true"
    assert "## Test Protection Mode: true" in content, "BUG: Instruction file says false despite protect_tests=True"

# Test 3: agentic_fix scope guard reverts unauthorized test changes
def test_agentic_fix_scope_guard_reverts_test_changes(tmp_path, monkeypatch):
    """
    Test 3: Verify that if protect_tests=True, any changes made by the agent
    to the test file are REVERTED by the scope guard.
    """
    p_prompt, p_code, p_test, p_err = _prep_files(tmp_path)
    
    # Initial content
    test_path = Path(p_test)
    original_test_content = test_path.read_text()
    code_path = Path(p_code)
    
    # Mock run_agentic_task to simulate agent modifying both code and test
    def mock_run_task(instruction, cwd, **kwargs):
        code_path.write_text("fixed code")
        test_path.write_text("malicious test change")
        return (True, "Fixed both", 0.05, "anthropic")
        
    monkeypatch.setattr("pdd.agentic_fix.run_agentic_task", mock_run_task)
    monkeypatch.setattr("pdd.agentic_fix._load_model_data", lambda _: _df())
    monkeypatch.setattr("pdd.agentic_fix._verify_and_log", lambda *a, **k: True)
    monkeypatch.setattr("pdd.agentic_common._find_cli_binary", lambda cmd, config=None: "/usr/bin/shim")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("PDD_AGENTIC_LOGLEVEL", "quiet")

    # Mock _revert_out_of_scope_changes to use the real one but we need to make sure 
    # it can run without git if possible, or mock git.
    # Actually pdd/agentic_common.py's _revert_out_of_scope_changes uses git if it can.
    # Let's mock git to avoid the warning and ensure it works.
    with patch("pdd.agentic_common.subprocess.run") as mock_run:
        # Mock git status to return something so it thinks it's a git repo
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        
        run_agentic_fix(
            p_prompt, p_code, p_test, p_err, cwd=tmp_path,
            protect_tests=True
        )
    
    # Code should be changed
    assert code_path.read_text() == "fixed code", "Code should be allowed to change"
    # Test should be REVERTED
    # THE BUG: currently it is preserved because test_path is in allowed_files
    # THE FIX: test_path should be removed from allowed_files when protect_tests=True
    assert test_path.read_text() == original_test_content, \
        "BUG: Test file changes were NOT reverted despite protect_tests=True"

# Test 4: CLI fix command propagates --protect-tests flag
def test_cli_fix_command_propagation():
    """
    Test 4: Verify that the --protect-tests flag in the CLI command
    is correctly passed down to fix_main.
    """
    runner = CliRunner()
    # Patch where fix_main is actually imported and used in pdd.commands.fix
    with patch("pdd.fix_main.fix_main") as mock_fix_main:
        mock_fix_main.return_value = (True, "test", "code", 1, 0.1, "model")
        
        result = runner.invoke(fix, [
            "p.prompt", "c.py", "t.py",
            "--loop", "--protect-tests",
            "--verification-program", "verify.py"
        ])
        
        assert result.exit_code == 0
        assert mock_fix_main.called
        kwargs = mock_fix_main.call_args.kwargs
        assert kwargs.get("protect_tests") is True, "BUG: --protect-tests flag did not propagate to fix_main"

# Test 5: fix_error_loop non-Python fallback honors protect_tests
@patch("pdd.fix_error_loop._safe_run_agentic_fix")
def test_fix_error_loop_non_python_fallback(mock_safe_agentic, tmp_path):
    """
    Test 5: Verify that when fix_error_loop jumps straight to agentic fallback
    for non-Python files, it still honors the protect_tests flag.
    """
    code_file = tmp_path / "index.js"
    code_file.write_text("console.log('bug')")
    test_file = tmp_path / "test.js"
    test_file.write_text("test")
    
    mock_safe_agentic.return_value = (True, "Fixed", 0.1, "agent", [])
    
    with patch("pdd.fix_error_loop.get_test_command_for_file") as mock_get_cmd:
        # Trigger "No verification command" branch which jumps to fallback
        mock_get_cmd.return_value = None
        
        fix_error_loop(
            str(test_file), str(code_file), "p.prompt", "prompt", "v.sh",
            0.5, 0.1, 1, 1.0,
            agentic_fallback=True,
            protect_tests=True,
            error_log_file=str(tmp_path / "err.log")
        )
        
        assert mock_safe_agentic.called
        assert mock_safe_agentic.call_args.kwargs.get("protect_tests") is True, \
            "BUG: protect_tests=True was not passed during non-Python fallback"

# --- Step 5 Reproduction Tests ---

# Reproduction test from Step 5
def test_step5_protect_tests_propagation_to_agentic_fallback():
    """
    Reproduction test from Step 5:
    Test that the protect_tests flag is correctly propagated to run_agentic_fix
    during the agentic fallback phase.
    """
    # Note: Currently _safe_run_agentic_fix does NOT accept protect_tests,
    # so we'll first test if we can even pass it (it should fail if not updated).
    
    with patch("pdd.fix_error_loop.run_agentic_fix") as mock_run_agentic:
        mock_run_agentic.return_value = (True, "Success", 0.0, "model", [])
        
        try:
            _safe_run_agentic_fix(
                prompt_file="test.prompt",
                code_file="test.py",
                unit_test_file="test_test.py",
                error_log_file="error.log",
                protect_tests=True  # This is what's missing in the signature
            )
        except TypeError as e:
            # This is the expected failure on buggy code
            pytest.fail(f"BUG: protect_tests parameter is missing from _safe_run_agentic_fix signature: {e}")
            
        # Verify that protect_tests=True was passed to run_agentic_fix
        args, kwargs = mock_run_agentic.call_args
        assert kwargs.get("protect_tests") is True, "BUG: protect_tests flag was not propagated to run_agentic_fix"

# Reproduction test from Step 5
def test_step5_fix_error_loop_passes_protect_tests_to_fallback():
    """
    Reproduction test from Step 5:
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
        assert kwargs.get("protect_tests") is True, "BUG: fix_error_loop did not pass protect_tests to _safe_run_agentic_fix"
