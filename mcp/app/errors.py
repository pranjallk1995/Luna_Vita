"""Domain errors shared by services and their transport adapters."""


class NotFoundError(LookupError):
    """Raised when a requested food entry, measurement, or profile is absent."""
