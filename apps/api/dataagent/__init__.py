"""DataAgent API: a modular monolith, layered by responsibility.

Dependency direction (enforced by tests/test_layering.py):

    api  ->  agent  ->  ports
                    \\->  domain
    infra ->  everything (composition root only)

App-internal layering only. The repository-level five layers are decided by
docs/adr/0002-repo-layout.md; this package is the inside of ``apps/api``.
"""

__version__ = "0.1.0"
