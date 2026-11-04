/**
 * Typed client for the AnyGet API.
 * `schema.ts` is generated from the FastAPI OpenAPI schema: run `make gen` after API changes.
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };
export type Health = components["schemas"]["Health"];
export type VersionInfo = components["schemas"]["VersionInfo"];

export function createApiClient(baseUrl = "", init?: { fetch?: typeof fetch }) {
  return createClient<paths>({ baseUrl, ...init });
}

export type ApiClient = ReturnType<typeof createApiClient>;
