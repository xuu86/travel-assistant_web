import { createContext, useContext } from "react";
import type { AuthIdentity, LoginInput } from "./api";
import { AuthApiError } from "./api";

export type AuthState = {
  ready: boolean;
  identity: AuthIdentity;
  workspaceOwnerId: string;
  available: boolean;
  error: string | null;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
};

export const guestIdentity: AuthIdentity = {
  identity_type: "guest", owner_id: null, display_name: null,
};

const defaultState: AuthState = {
  ready: true,
  identity: guestIdentity,
  workspaceOwnerId: "guest-test-context",
  available: true,
  error: null,
  login: async () => { throw new AuthApiError("登录服务暂不可用，请稍后重试。", 0); },
  logout: async () => undefined,
};

export const AuthContext = createContext<AuthState>(defaultState);

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
