import os
import tempfile

# must be set before app modules are imported: the engine is created at import time
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "import.db"))
