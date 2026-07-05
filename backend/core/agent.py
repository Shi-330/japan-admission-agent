"""
Backend-compatible Agent wrapper — replaced by agent/orchestrator.py.
Kept as compatibility shim for existing tests.
"""
from agent.orchestrator import ChatOrchestrator
from user.profile_manager import ProfileManager, UserProfile

# Re-export for backward compatibility
HeadlessAgent = ChatOrchestrator
