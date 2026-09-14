"""Exceptions that callers may translate into UI messages; no UI dependencies here."""


class IntegrityError(Exception):
    """Base exception for a controlled analysis or repair failure."""


class InvalidGeometry(IntegrityError, ValueError):
    """Malformed data, rather than a merely open or non-manifold surface."""


class InvalidChainComplex(IntegrityError, ValueError):
    """Dimensions disagree or the boundary-of-boundary identity fails."""


class ResourceLimitExceeded(IntegrityError):
    """An explicit work or storage budget was exceeded."""


class RepairRejected(IntegrityError):
    """A proposed repair violates its policy; the input remains unchanged."""


class MissingOptionalDependency(IntegrityError, ImportError):
    """Install the documented extra before using this adapter."""


class KernelOperationFailed(IntegrityError):
    """The native CAD kernel could not complete an operation."""


class ExportRejected(IntegrityError):
    """Pre-export or round-trip checks failed; no new target is published."""
