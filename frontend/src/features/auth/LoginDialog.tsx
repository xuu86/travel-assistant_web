import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "./auth-context";
import "./auth.css";

export function LoginDialog() {
  const { identity, available, error, login, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    if (!open && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [open]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(null);
    try {
      await login({ username, password });
      setPassword("");
      setOpen(false);
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "登录失败，请检查账号和密码。 ");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setFormError(null);
    try {
      await logout();
      setUsername("");
      setPassword("");
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "退出失败，请重试。 ");
    } finally {
      setBusy(false);
    }
  }

  return <div className="auth-controls">
    <span className="auth-controls__identity" aria-live="polite">
      <span className={`auth-controls__dot${identity.identity_type === "account" ? " is-account" : ""}`} aria-hidden="true" />
      {identity.identity_type === "account" ? identity.display_name : "游客模式"}
    </span>
    {identity.identity_type === "account" ? (
      <button className="auth-controls__button" type="button" onClick={() => void signOut()} disabled={busy}>
        {busy ? "请稍候…" : "退出登录"}
      </button>
    ) : (
      <>
        {!available && <span className="auth-controls__unavailable" role="status">登录服务暂不可用，当前以游客身份使用</span>}
        <button className="auth-controls__button" type="button" onClick={() => { setFormError(null); setOpen(true); }} disabled={!available || busy}>
          登录
        </button>
      </>
    )}
    <dialog ref={dialogRef} className="auth-dialog" aria-labelledby="auth-dialog-title" onCancel={() => setOpen(false)} onClose={() => setOpen(false)}>
      <form className="auth-dialog__form" onSubmit={(event) => void submit(event)}>
        <div className="auth-dialog__heading">
          <div><p className="eyebrow">ACCOUNT / SIGN IN</p><h2 id="auth-dialog-title">登录测试账号</h2></div>
          <button className="auth-dialog__close" type="button" onClick={() => setOpen(false)} aria-label="关闭登录">×</button>
        </div>
        <label className="field">
          <span className="field__label">用户名</span>
          <input name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required maxLength={32} disabled={busy} />
        </label>
        <label className="field">
          <span className="field__label">密码</span>
          <input name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={1024} disabled={busy} />
        </label>
        {(formError ?? error) && <p className="auth-dialog__error" role="alert">{formError ?? error}</p>}
        {!available && <p className="auth-dialog__error" role="status">登录服务暂不可用；仍可继续以游客身份使用。</p>}
        <div className="auth-dialog__actions">
          <button className="auth-dialog__cancel" type="button" onClick={() => setOpen(false)} disabled={busy}>取消</button>
          <button className="auth-dialog__submit" type="submit" disabled={busy || !available}>{busy ? "正在验证…" : "登录"}</button>
        </div>
      </form>
    </dialog>
  </div>;
}
