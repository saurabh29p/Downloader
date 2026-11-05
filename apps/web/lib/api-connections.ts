/** Connections: the user's own cookies and keys per site (own module: one page loads it). */
import type { components } from "@anyget/shared";

import { api, call } from "@/lib/api";

export type ConnectionsView = components["schemas"]["ConnectionsView"];
export type Connection = components["schemas"]["ConnectionView"];
export type TestResult = components["schemas"]["TestResult"];

export const listConnections = () => call(api.GET("/api/connections"));

export const saveConnection = (
  site: string,
  body: { cookies?: string; fields?: Record<string, string>; proxy?: string | null },
) => call(api.PUT("/api/connections/{site_id}", { params: { path: { site_id: site } }, body }));

export const importCookies = (cookies: string) =>
  call(api.POST("/api/connections/import", { body: { cookies } }));

export const testConnection = (site: string) =>
  call(api.POST("/api/connections/{site_id}/test", { params: { path: { site_id: site } } }));

export async function removeConnection(site: string): Promise<void> {
  await call(api.DELETE("/api/connections/{site_id}", { params: { path: { site_id: site } } }));
}
