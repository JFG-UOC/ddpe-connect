"""Authenticated Spark Connect sessions for Dell Data Processing Engine."""

from .auth import TokenCache
from .errors import (
    DDPEAuthenticationError,
    DDPEConfigurationError,
    DDPEConnectionError,
    DDPEDependencyError,
    DDPEError,
)
from .session import DDPEBuilder, DDPESession

__version__ = "0.1.0"

__all__ = [
    "DDPEAuthenticationError",
    "DDPEBuilder",
    "DDPEConfigurationError",
    "DDPEConnectionError",
    "DDPEDependencyError",
    "DDPEError",
    "DDPESession",
    "TokenCache",
    "__version__",
]
