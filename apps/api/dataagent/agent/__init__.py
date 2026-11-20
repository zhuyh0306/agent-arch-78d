"""Agent layer: the orchestration that talks only to ports.

This package knows *what* to ask for, never *how* it is done. The test for
whether the layering is real: delete ``dataagent/agent/adapters`` and this
package must still import and its tests must still pass, because a fake can be
substituted for every port.
"""

from dataagent.agent.service import AgentService

__all__ = ["AgentService"]