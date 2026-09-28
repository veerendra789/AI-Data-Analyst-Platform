import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import ProtectedRoute from "./ProtectedRoute";
import { AuthProvider } from "../context/AuthContext";

function renderRoute() {
  return render(<AuthProvider><MemoryRouter initialEntries={["/dashboard"]}><Routes><Route element={<ProtectedRoute />}><Route path="/dashboard" element={<p>Dashboard</p>} /></Route><Route path="/login" element={<p>Login</p>} /></Routes></MemoryRouter></AuthProvider>);
}

describe("ProtectedRoute", () => {
  beforeEach(() => localStorage.clear());

  it("redirects an anonymous visitor", () => {
    renderRoute();
    expect(screen.getByText("Login")).toBeInTheDocument();
  });

  it("allows a stored authenticated session", () => {
    localStorage.setItem("current_user", JSON.stringify({ id: 1, name: "Analyst", email: "analyst@example.com", role: "ANALYST", created_at: "2026-01-01T00:00:00Z" }));
    renderRoute();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });
});
