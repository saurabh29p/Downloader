/** Conversions (own module: the Downloads convert menu loads only this). */
import { api, call } from "@/lib/api";

export type ConvertTarget = "pdf" | "ocr" | "mp3" | "m4a";

export const convertJob = (job_id: string, to: ConvertTarget, lang?: string) =>
  call(api.POST("/api/convert", { body: { job_id, to, lang: lang || null } }));
