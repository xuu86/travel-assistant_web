import { describe, expect, it } from "vitest";
import { allowsCredentialSubmission } from "./credential-security";

describe("allowsCredentialSubmission", () => {
  it("requires a secure context unless running on loopback", () => {
    expect(allowsCredentialSubmission("http://43.143.125.176:18080", false)).toBe(false);
    expect(allowsCredentialSubmission("https://travel.example", true)).toBe(true);
    expect(allowsCredentialSubmission("http://localhost:5173")).toBe(true);
    expect(allowsCredentialSubmission("http://127.0.0.1:5173")).toBe(true);
    expect(allowsCredentialSubmission("http://travel.example")).toBe(false);
  });
});
