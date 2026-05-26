import os
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pdd.server.app import create_app

def test_issue_3_reproduction():
    """
    Test that pdd connect falls back to CWD for frontend assets if not found in package.
    """
    # Create a temporary directory to act as CWD
    with tempfile.TemporaryDirectory() as tmp_dir:
        cwd = Path(tmp_dir)
        
        # Create a dummy frontend/dist in the CWD
        # The app looks for 'frontend/dist' relative to the package OR CWD
        # Based on the issue, it should look in pdd/frontend/dist relative to CWD if we are at repo root
        # Or just frontend/dist? Let's check what the issue implies.
        # "search the current working directory context (os.getcwd())"
        
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
            # We pass cwd as project_root
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

if __name__ == "__main__":
    # If run directly, try to run the test
    try:
        test_issue_3_reproduction()
        print("Test PASSED (Unexpected - bug might be fixed or test is wrong)")
    except AssertionError as e:
        print(f"Test FAILED as expected: {e}")
    except Exception as e:
        print(f"Test errored: {e}")
