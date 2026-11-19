export type ErrorReason =
  | "configuration"
  | "network"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "validation"
  | "conflict"
  | "unsupported"
  | "server"
  | "unknown";

export class DataGatewayError extends Error {
  constructor(
    public reason: ErrorReason,
    public message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "DataGatewayError";
  }
}

export class UnsupportedOperationError extends DataGatewayError {
  constructor(operationName: string) {
    super("unsupported", `Operation '${operationName}' is not supported by the current data mode.`);
    this.name = "UnsupportedOperationError";
  }
}

export class ConfigurationError extends DataGatewayError {
  constructor(message: string) {
    super("configuration", message);
    this.name = "ConfigurationError";
  }
}
