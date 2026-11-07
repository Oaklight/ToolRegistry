"""Public error types.

These are the exceptions raised while checking tool arguments and results
against their schemas, and while reading a tool response through the vendored
HTTP client.  They are re-exported from the vendored modules so that callers —
a server mapping failures to an HTTP status, a client validating before
dispatch — can catch them without importing a private ``toolregistry._vendor``
path.

The classes themselves are the vendored ones: ``except`` clauses are
interchangeable, and an upstream vendor update cannot silently change the
type raised, because :mod:`tests.test_validation_errors` pins the identity.
"""

from ._vendor.httpclient import ResponseTooLargeError
from ._vendor.jsonschema import SchemaErrorDetail, SchemaValidationError
from ._vendor.validate import ErrorDetail, ValidationError

#: Both validation failures, for callers that map either one to a single
#: outcome (a server answering 422, a client rejecting the call).  The two
#: classes share no base — they come from different vendored modules and
#: neither can be edited — so ``except VALIDATION_ERRORS`` is the way to
#: catch both without enumerating them.
VALIDATION_ERRORS = (ValidationError, SchemaValidationError)

__all__ = [
    "ErrorDetail",
    "ResponseTooLargeError",
    "SchemaErrorDetail",
    "SchemaValidationError",
    "VALIDATION_ERRORS",
    "ValidationError",
]
