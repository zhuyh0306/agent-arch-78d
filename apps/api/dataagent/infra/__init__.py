"""Infra layer: process concerns only -- settings, logging, the composition root.

The composition root (``dataagent.infra.container``) is the single place that
names a concrete adapter. Everything above it depends on ports. If you find
yourself importing an adapter from ``api`` or ``agent``, the wiring has leaked
and a test in ``tests/test_layering.py`` will fail.
"""

from dataagent.infra.container import Container, build_container
from dataagent.infra.settings import Settings

__all__ = ["Container", "Settings", "build_container"]