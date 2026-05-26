import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from pdd.server.app import create_app

# --- Step 5 Reproduction Test ---

def test_issue_3_reproduction():
    """
    Step 5 Reproduction Test:
    Test that pdd connect falls back to CWD for frontend assets if not found in package.
    """
    # Create a temporary directory to act as CWD
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        
        # In the repo, it's pdd/frontend/dist
        local_dist = cwd / "pdd" / "frontend" / "dist"
        local_dist.mkdir(parents=True)
        
        # Create a dummy index.html
        index_html = local_dist / "index.html"
        index_html.write_text("<html><body>Local Frontend</body></html>")
        
        # Create a dummy assets directory
        assets_dir = local_dist / "assets"
        assets_dir.mkdir()
        (assets_dir / "test.js").write_text("console.log('test')")

        # Save current CWD and change to tmp_dir
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        
        try:
            # Create the app. It should (but currently doesn't) find the local frontend.
            # Pass cwd as project_root
            app = create_app(project_root=cwd)
            client = TestClient(app)
            
            # Request the root. It should return the local index.html.
            response = client.get("/")
            
            # In the buggy version, it will return 404 or "Frontend not found" 
            # because it only looked in site-packages/pdd/frontend/dist
            assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
            assert "Local Frontend" in response.text
            
            # Also check assets
            response = client.get("/assets/test.js")
            assert response.status_code == 200
            assert "console.log('test')" in response.text
            
        finally:
            os.chdir(old_cwd)

# --- Step 8 Planned Tests ---

@pytest.fixture
def mock_console():
    with patch("pdd.server.app.console") as mock:
        yield mock

def test_local_repo_root_priority(mock_console):
    """
    Test 1: Verify that project_root/pdd/frontend/dist has highest priority.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        
        # 1. Local repo structure: project_root/pdd/frontend/dist
        repo_dist = cwd / "pdd" / "frontend" / "dist"
        repo_dist.mkdir(parents=True)
        (repo_dist / "index.html").write_text("Repo Dist")
        
        # 2. Flat structure: project_root/frontend/dist
        flat_dist = cwd / "frontend" / "dist"
        flat_dist.mkdir(parents=True)
        (flat_dist / "index.html").write_text("Flat Dist")

        # Change to tmp_dir
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        
        try:
            app = create_app(project_root=cwd)
            client = TestClient(app)
            
            response = client.get("/")
            assert response.status_code == 200
            # Should prefer repo_dist over flat_dist
            assert "Repo Dist" in response.text
            
            # Verify logging
            mock_console.print.assert_called()
            log_messages = "".join([str(call.args[0]) for call in mock_console.print.call_args_list])
            assert str(repo_dist) in log_messages
        finally:
            os.chdir(old_cwd)

def test_flat_workspace_fallback(mock_console):
    """
    Test 2: Verify that project_root/frontend/dist is used if repo structure is missing.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        
        # Only flat structure: project_root/frontend/dist
        flat_dist = cwd / "frontend" / "dist"
        flat_dist.mkdir(parents=True)
        (flat_dist / "index.html").write_text("Flat Dist")

        # Change to tmp_dir
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        
        try:
            app = create_app(project_root=cwd)
            client = TestClient(app)
            
            response = client.get("/")
            assert response.status_code == 200
            assert "Flat Dist" in response.text
            
            # Verify logging
            mock_console.print.assert_called()
            log_messages = "".join([str(call.args[0]) for call in mock_console.print.call_args_list])
            assert str(flat_dist) in log_messages
        finally:
            os.chdir(old_cwd)

def test_package_fallback_and_missing_warning(mock_console):
    """
    Test 3: Verify fallback to package path and warning if missing everywhere.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        # No local assets created

        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        
        try:
            # Mock Path.exists to return False for all frontend/dist paths to trigger warning
            with patch.object(Path, "exists") as mock_exists:
                mock_exists.return_value = False
                
                app = create_app(project_root=cwd)
                
                # Check for warning logging
                # Buggy code logs "Frontend not found at ..."
                mock_console.print.assert_called()
                log_messages = "".join([str(call.args[0]) for call in mock_console.print.call_args_list])
                assert "Frontend not found at" in log_messages
        finally:
            os.chdir(old_cwd)

def test_spa_routing_and_asset_serving():
    """
    Test 4: Verify SPA routing and asset serving functionality.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        local_dist = cwd / "frontend" / "dist"
        local_dist.mkdir(parents=True)
        (local_dist / "index.html").write_text("SPA Index")
        assets_dir = local_dist / "assets"
        assets_dir.mkdir()
        (assets_dir / "app.js").write_text("console.log('app')")

        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        
        try:
            app = create_app(project_root=cwd)
            client = TestClient(app)
            
            # 1. Direct asset request
            response = client.get("/assets/app.js")
            assert response.status_code == 200
            assert "console.log('app')" in response.text
            
            # 2. SPA fallback (non-API route)
            response = client.get("/dashboard")
            assert response.status_code == 200
            assert "SPA Index" in response.text
            
            # 3. API route should NOT fallback (should be 404 if not found)
            response = client.get("/api/v1/nonexistent")
            assert response.status_code == 404
            assert "SPA Index" not in response.text
            
        finally:
            os.chdir(old_cwd)

if __name__ == "__main__":
    pytest.main([__file__])
