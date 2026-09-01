"""Tests never call the real model. MODEL=off is set before any app module is imported."""

import os

os.environ["MODEL"] = "off"
