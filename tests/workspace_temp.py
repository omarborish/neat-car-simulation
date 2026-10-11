"""Use inherited Windows permissions, including restricted test accounts."""
from pathlib import Path
import shutil
from uuid import uuid4


class WorkspaceTemp:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[1] / ".test-tmp"
        self.path = self.root / uuid4().hex
        self.path.mkdir(parents=True)
        self.name = str(self.path)

    def cleanup(self):
        if not self.path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Test cleanup must stay inside the workspace")
        shutil.rmtree(self.path)
