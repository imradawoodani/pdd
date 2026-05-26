
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from pdd.server.app import create_app

@pytest.fixture
def mock_dirs(tmp_path):
    # CWD root
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # Fake site-packages
    site_packages = tmp_path / "site-packages"
    package_pdd = site_packages / "pdd"
    package_app_file = package_pdd / "server" / "app.py"
    package_app_file.parent.mkdir(parents=True)
    
    # Frontend in package
    package_dist = package_pdd / "frontend" / "dist"
    
    # Frontend candidates in local CWD
    local_pdd_dist = project_root / "pdd" / "frontend" / "dist"
    local_frontend_dist = project_root / "frontend" / "dist"
    local_just_dist = project_root / "dist"
    
    return {
        "project_root": project_root,
        "package_app_file": package_app_file,
        "package_dist": package_dist,
        "local_pdd_dist": local_pdd_dist,
        "local_frontend_dist": local_frontend_dist,
        "local_just_dist": local_just_dist
    }

def test_frontend_path_resolution_local_fallback_pdd_dist(mock_dirs, monkeypatch):
    """Test fallback to CWD pdd/frontend/dist."""
    monkeypatch.chdir(mock_dirs["project_root"])
    mock_dirs["local_pdd_dist"].mkdir(parents=True)
    (mock_dirs["local_pdd_dist"] / "index.html").write_text("LOCAL")
    (mock_dirs["local_pdd_dist"] / "assets").mkdir()
    
    with patch("pdd.server.app.__file__", str(mock_dirs["package_app_file"])), \
         patch("pdd.server.app.console.print") as mock_print:
        create_app(mock_dirs["project_root"])
        assert any("Serving frontend from local workspace" in str(call[0][0]) for call in mock_print.call_args_list)
        assert any(str(mock_dirs["local_pdd_dist"]) in str(call[0][0]) for call in mock_print.call_args_list)

def test_frontend_path_resolution_local_fallback_frontend_dist(mock_dirs, monkeypatch):
    """Test fallback to CWD frontend/dist."""
    monkeypatch.chdir(mock_dirs["project_root"])
    mock_dirs["local_frontend_dist"].mkdir(parents=True)
    (mock_dirs["local_frontend_dist"] / "index.html").write_text("LOCAL")
    (mock_dirs["local_frontend_dist"] / "assets").mkdir()
    
    with patch("pdd.server.app.__file__", str(mock_dirs["package_app_file"])), \
         patch("pdd.server.app.console.print") as mock_print:
        create_app(mock_dirs["project_root"])
        assert any("Serving frontend from local workspace" in str(call[0][0]) for call in mock_print.call_args_list)
        assert any(str(mock_dirs["local_frontend_dist"]) in str(call[0][0]) for call in mock_print.call_args_list)

def test_frontend_path_resolution_local_fallback_just_dist(mock_dirs, monkeypatch):
    """Test fallback to CWD dist/."""
    monkeypatch.chdir(mock_dirs["project_root"])
    mock_dirs["local_just_dist"].mkdir(parents=True)
    (mock_dirs["local_just_dist"] / "index.html").write_text("LOCAL")
    (mock_dirs["local_just_dist"] / "assets").mkdir()
    
    with patch("pdd.server.app.__file__", str(mock_dirs["package_app_file"])), \
         patch("pdd.server.app.console.print") as mock_print:
        create_app(mock_dirs["project_root"])
        assert any("Serving frontend from local workspace" in str(call[0][0]) for call in mock_print.call_args_list)
        assert any(str(mock_dirs["local_just_dist"]) in str(call[0][0]) for call in mock_print.call_args_list)

def test_frontend_path_resolution_package_primary(mock_dirs, monkeypatch):
    """Test that package dist is used if no local exists."""
    monkeypatch.chdir(mock_dirs["project_root"])
    mock_dirs["package_dist"].mkdir(parents=True)
    (mock_dirs["package_dist"] / "index.html").write_text("PACKAGE")
    (mock_dirs["package_dist"] / "assets").mkdir()
    
    with patch("pdd.server.app.__file__", str(mock_dirs["package_app_file"])), \
         patch("pdd.server.app.console.print") as mock_print:
        create_app(mock_dirs["project_root"])
        assert any("Serving frontend from package directory" in str(call[0][0]) for call in mock_print.call_args_list)
        assert any(str(mock_dirs["package_dist"]) in str(call[0][0]) for call in mock_print.call_args_list)

def test_frontend_path_resolution_preference(mock_dirs, monkeypatch):
    """Test that local CWD dist is preferred over package dist even if package exists."""
    monkeypatch.chdir(mock_dirs["project_root"])
    mock_dirs["local_pdd_dist"].mkdir(parents=True)
    (mock_dirs["local_pdd_dist"] / "index.html").write_text("LOCAL")
    (mock_dirs["local_pdd_dist"] / "assets").mkdir()
    
    mock_dirs["package_dist"].mkdir(parents=True)
    (mock_dirs["package_dist"] / "index.html").write_text("PACKAGE")
    (mock_dirs["package_dist"] / "assets").mkdir()
    
    with patch("pdd.server.app.__file__", str(mock_dirs["package_app_file"])), \
         patch("pdd.server.app.console.print") as mock_print:
        create_app(mock_dirs["project_root"])
        assert any("Serving frontend from local workspace" in str(call[0][0]) for call in mock_print.call_args_list)
        assert any(str(mock_dirs["local_pdd_dist"]) in str(call[0][0]) for call in mock_print.call_args_list)
