import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AuthProvider } from "./features/auth/AuthProvider";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Missing application root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <AuthProvider><App /></AuthProvider>
  </StrictMode>,
);
