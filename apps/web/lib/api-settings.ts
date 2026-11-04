/** Settings calls (separate module so first-load pages never include them). */
import { api, call } from "@/lib/api";

export const getCookiesStatus = () => call(api.GET("/api/settings/cookies"));

export const putCookies = (content: string) =>
  call(api.PUT("/api/settings/cookies", { body: { content } }));

export async function deleteCookies(): Promise<void> {
  await call(api.DELETE("/api/settings/cookies"));
}
