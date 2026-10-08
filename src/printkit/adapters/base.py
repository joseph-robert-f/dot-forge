"""Adapter failures are retained by the outer orchestrator."""
from ..common import ForgeError

class AdapterError(ForgeError):
    def __init__(self,message):
        super().__init__(message, 4, "adapter_failure")

class RuntimeUnavailable(AdapterError):
    def __init__(self,message):
        ForgeError.__init__(self,message, 3, "runtime_unavailable")
