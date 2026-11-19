
import { DataGatewayError } from "../errors";

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async fetchApi<T>(path: string, options: RequestInit = {}): Promise<T | null> {
    const url = `${this.baseUrl}${path}`;

    // Using AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorBody: unknown;
        try {
          errorBody = await response.json();
        } catch {
          // ignore
        }

        const errorMessage =
          typeof errorBody === "object" &&
          errorBody !== null &&
          "message" in errorBody &&
          typeof errorBody.message === "string"
            ? errorBody.message
            : `HTTP ${response.status}`;

        switch (response.status) {
          case 401:
            throw new DataGatewayError("unauthorized", "Unauthorized: " + errorMessage);
          case 403:
            throw new DataGatewayError("forbidden", "Forbidden: " + errorMessage);
          case 404:
            throw new DataGatewayError("not_found", "Not found: " + errorMessage);
          case 422:
            throw new DataGatewayError("validation", "Validation error: " + errorMessage);
          case 409:
            throw new DataGatewayError("conflict", "Conflict: " + errorMessage);
          case 500:
          case 502:
          case 503:
          case 504:
            throw new DataGatewayError("server", "Server error: " + errorMessage);
          default:
            throw new DataGatewayError("unknown", "API error: " + errorMessage);
        }
      }

      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error: unknown) {
      clearTimeout(timeoutId);
      if (error instanceof DataGatewayError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new DataGatewayError("network", "Request timeout");
      }
      throw new DataGatewayError("network", "Network error: " + (error instanceof Error ? error.message : String(error)));
    }
  }

  async get<T = unknown>(path: string): Promise<T | null> {
    return this.fetchApi<T>(path, { method: "GET" });
  }

  async post<T = unknown, B = unknown>(path: string, body?: B): Promise<T | null> {
    return this.fetchApi<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T = unknown, B = unknown>(path: string, body?: B): Promise<T | null> {
    return this.fetchApi<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}
