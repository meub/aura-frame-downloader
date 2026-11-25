"""Custom exceptions for Aura Frame Downloader."""


class AuraError(Exception):
    """Base exception for Aura Frame Downloader."""
    pass


class ConfigError(AuraError):
    """Raised when there's an error with the configuration file."""
    pass


class LoginError(AuraError):
    """Raised when login to the Aura API fails."""
    pass


class NetworkError(AuraError):
    """Raised when Aura's servers can't be reached (no connection, DNS failure, timeout)."""
    pass


class NoAssetsError(AuraError):
    """Raised when no assets are found in the frame."""
    pass


class DownloadError(AuraError):
    """Raised when a download operation fails."""
    pass


class DownloadCancelledError(AuraError):
    """Raised when the download is cancelled by the user."""
    pass
