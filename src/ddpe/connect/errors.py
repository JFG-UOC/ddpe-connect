"""Public exception hierarchy for ddpe-connect."""


class DDPEError(Exception):
    """Base exception raised by ddpe-connect."""


class DDPEConfigurationError(DDPEError):
    """Raised when client configuration is invalid."""


class DDPEAuthenticationError(DDPEError):
    """Raised when Keycloak authentication fails."""


class DDPEConnectionError(DDPEError):
    """Raised when a Spark Connect session cannot be created."""


class DDPEDependencyError(DDPEError):
    """Raised when a required runtime dependency is unavailable."""
