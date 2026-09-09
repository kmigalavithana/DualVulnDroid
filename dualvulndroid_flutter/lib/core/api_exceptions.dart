/// Typed exceptions the API client raises, so callers (repositories,
/// then screens) can react to specific real failure modes instead of
/// pattern-matching on strings or status codes scattered through the UI
/// layer. Never carries a raw stack trace or exception object out to the
/// UI (Phase 9, Part 4/18) - `message` is always a short, safe,
/// human-readable string.
sealed class ApiException implements Exception {
  final String message;
  const ApiException(this.message);

  @override
  String toString() => message;
}

/// No response at all - DNS failure, connection refused, timeout. Covers
/// "server unavailable" (Part 18).
class NetworkException extends ApiException {
  const NetworkException([super.message = 'Could not reach the security service. Check your connection and try again.']);
}

/// HTTP 401 - missing/expired/invalid JWT.
class UnauthorizedException extends ApiException {
  const UnauthorizedException([super.message = 'Your session has expired. Please log in again.']);
}

/// HTTP 404.
class NotFoundException extends ApiException {
  const NotFoundException([super.message = 'The requested item could not be found.']);
}

/// HTTP 400/422 - the request itself was rejected (validation error).
class ValidationException extends ApiException {
  const ValidationException([super.message = 'The request could not be processed.']);
}

/// HTTP 5xx or any other unexpected status.
class ServerException extends ApiException {
  const ServerException([super.message = 'The security service is currently unavailable. Please try again later.']);
}

/// HTTP 413 - the uploaded file exceeded the backend's size limit.
class PayloadTooLargeException extends ApiException {
  const PayloadTooLargeException([super.message = 'This file is too large to scan.']);
}
