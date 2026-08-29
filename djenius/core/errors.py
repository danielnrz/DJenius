"""Core exceptions for the DJenius project."""


class DecodeError(Exception):
    """Raised when an audio file cannot be decoded by any backend."""
    pass