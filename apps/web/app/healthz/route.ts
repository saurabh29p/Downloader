/** Liveness check for the web container (does not depend on the API). */
export function GET() {
  return Response.json({ status: "ok" });
}
