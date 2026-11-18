import { CampusDataGateway } from "./gateway";
import { MockCampusDataGateway } from "./mock/mock-gateway";
import { ApiCampusDataGateway } from "./api/api-gateway";
import { DataConfig } from "./config";
import { ConfigurationError } from "./errors";

export function createGateway(config: DataConfig): CampusDataGateway {
  if (config.mode === "api") {
    if (config.apiBaseUrl === undefined) {
      throw new ConfigurationError("apiBaseUrl is required for API mode");
    }
    return new ApiCampusDataGateway(config.apiBaseUrl);
  } else if (config.mode === "mock") {
    return new MockCampusDataGateway();
  }

  throw new ConfigurationError(`Invalid data mode: ${config.mode}`);
}
