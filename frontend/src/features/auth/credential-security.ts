export function allowsCredentialSubmission(origin: string, secureContext?: boolean): boolean {
  if (secureContext !== undefined) return secureContext;
  const hostname = new URL(origin).hostname.toLowerCase();
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}
