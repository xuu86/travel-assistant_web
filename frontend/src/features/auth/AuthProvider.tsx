import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AuthApiError, getAuthSession, login as loginRequest, logout as logoutRequest } from "./api";
import type { AuthIdentity, LoginInput } from "./api";
import { getGuestOwnerId } from "../local-storage/repository";
import { WorkspacePersistenceProvider } from "../local-storage/WorkspacePersistenceProvider";
import { AuthContext, guestIdentity } from "./auth-context";
import type { AuthState } from "./auth-context";
import { allowsCredentialSubmission } from "./credential-security";

function publicMessage(reason: unknown): string {
  return reason instanceof AuthApiError
    ? reason.message
    : "登录服务暂不可用，请稍后重试。";
}
export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [identity, setIdentity] = useState<AuthIdentity>(guestIdentity);
  const [workspaceOwnerId, setWorkspaceOwnerId] = useState("guest-loading");
  const [available, setAvailable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const beforeSwitchRef = useRef<(() => Promise<void>) | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      let session = guestIdentity;
      let online = true;
      try {
        session = await getAuthSession(controller.signal);
      } catch {
        online = false;
      }
      if (controller.signal.aborted) return;
      let ownerId = session.owner_id;
      if (session.identity_type !== "account" || !ownerId) {
        try {
          ownerId = await getGuestOwnerId();
        } catch {
          ownerId = `guest-memory-${crypto.randomUUID()}`;
        }
        session = guestIdentity;
      }
      if (controller.signal.aborted) return;
      setIdentity(session);
      setWorkspaceOwnerId(ownerId ?? `guest-memory-${crypto.randomUUID()}`);
      setAvailable(online && allowsCredentialSubmission(window.location.origin, window.isSecureContext));
      setReady(true);
    })();
    return () => controller.abort();
  }, []);

  const login = useCallback(async (input: LoginInput) => {
    setError(null);
    try {
      await beforeSwitchRef.current?.();
      const result = await loginRequest(input);
      setIdentity(result);
      setWorkspaceOwnerId(result.owner_id ?? `guest-memory-${crypto.randomUUID()}`);
      setAvailable(true);
    } catch (reason) {
      const message = publicMessage(reason);
      setError(message);
      throw new Error(message, { cause: reason });
    }
  }, []);

  const logout = useCallback(async () => {
    setError(null);
    try {
      await beforeSwitchRef.current?.();
      await logoutRequest();
      let guestOwnerId: string;
      try {
        guestOwnerId = await getGuestOwnerId();
      } catch {
        guestOwnerId = `guest-memory-${crypto.randomUUID()}`;
      }
      setIdentity(guestIdentity);
      setWorkspaceOwnerId(guestOwnerId);
      setAvailable(true);
    } catch (reason) {
      const message = publicMessage(reason);
      setError(message);
      throw new Error(message, { cause: reason });
    }
  }, []);

  const value = useMemo<AuthState>(() => ({ ready, identity, workspaceOwnerId, available, error, login, logout }), [
    ready, identity, workspaceOwnerId, available, error, login, logout,
  ]);

  if (!ready) {
    return <main className="auth-startup" aria-live="polite"><span className="auth-startup__mark" aria-hidden="true" />正在恢复工作区…</main>;
  }
  return <AuthContext.Provider value={value}>
    <WorkspacePersistenceProvider key={workspaceOwnerId} ownerId={workspaceOwnerId} beforeSwitchRef={beforeSwitchRef}>
      {children}
    </WorkspacePersistenceProvider>
  </AuthContext.Provider>;
}
