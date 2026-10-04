export interface ErrorEnvelope {
  error: { code: string; message: string; request_id?: string | null; details?: Record<string, unknown> };
}

export class DSHError extends Error {
  readonly statusCode: number;
  readonly code: string;
  readonly requestId?: string;
  readonly details: Record<string, unknown>;

  constructor(statusCode: number, code: string, message: string, requestId?: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'DSHError';
    this.statusCode = statusCode;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export class AuthenticationError extends DSHError { name = 'AuthenticationError'; }
export class PermissionError extends DSHError { name = 'PermissionError'; }
export class NotFoundError extends DSHError { name = 'NotFoundError'; }
export class ConflictError extends DSHError { name = 'ConflictError'; }
export class ValidationError extends DSHError { name = 'ValidationError'; }
export class ServerError extends DSHError { name = 'ServerError'; }

export function errorForStatus(status: number, code: string, message: string, requestId?: string, details: Record<string, unknown> = {}): DSHError {
  const Type = status === 401 ? AuthenticationError : status === 403 ? PermissionError : status === 404 ? NotFoundError : status === 409 ? ConflictError : status === 422 ? ValidationError : status >= 500 ? ServerError : DSHError;
  return new Type(status, code, message, requestId, details);
}
