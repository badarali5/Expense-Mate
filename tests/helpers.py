"""helpers.py — shared test setup (path + temp database wiring)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bootstrap import build_controller
from database import Database


def make_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp.name, Database(tmp.name)


def make_controller():
    path, db = make_db()
    return path, db, build_controller(db)
