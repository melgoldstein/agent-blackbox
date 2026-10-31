"""Verify the distributable contains its CLI and all browser assets."""

import os
import subprocess
import sys
import tempfile
from importlib.resources import files

for asset in ("index.html", "style.css", "app.js"):
    assert files("agent_blackbox").joinpath("web", asset).is_file(), asset
with tempfile.TemporaryDirectory() as directory:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    subprocess.run(
        [sys.executable, "-m", "agent_blackbox.cli", "demo"],
        cwd=directory,
        env=environment,
        check=True,
        stdout=subprocess.DEVNULL,
    )
print("Installed wheel: CLI and browser assets verified")
