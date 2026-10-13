import axios from "axios";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { useAuth } from "../context/useAuth";
import { supabaseAuthErrorMessage } from "../services/supabaseAuthErrors";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      const authMessage = supabaseAuthErrorMessage(requestError, "login");
      if (authMessage) {
        setError(authMessage);
      } else if (axios.isAxiosError(requestError) && !requestError.response) {
        setError("The sign-in service is unavailable. Please try again shortly.");
      } else if (axios.isAxiosError(requestError) && requestError.response?.status === 401) {
        setError("Invalid email or password.");
      } else {
        setError("We could not sign you in. Please check your details and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Your workspace is ready when you are.">
      <form className="space-y-5" onSubmit={submit}>
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword} />
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="w-full rounded-lg bg-ink px-4 py-3 text-sm font-semibold text-paper disabled:opacity-60" disabled={submitting} type="submit">
          {submitting ? "Signing in..." : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-ink/55">New here? <Link className="font-semibold text-moss" to="/register">Create an account</Link></p>
    </AuthLayout>
  );
}

function Field({ label, type, value, onChange }: { label: string; type: string; value: string; onChange: (value: string) => void }) {
  return <label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">{label}</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" required type={type} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <main className="flex min-h-screen items-center justify-center bg-paper px-6 py-10"><section className="w-full max-w-md"><div className="mb-10 flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink text-lime"><BarChart3 size={21} /></div><span className="font-display text-xl">AI Data Analyst Platform</span></div><div className="rounded-2xl border border-ink/10 bg-white p-7 shadow-sm"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss"></p><h1 className="mt-3 font-display text-4xl">{title}</h1><p className="mt-2 mb-8 text-ink/60">{subtitle}</p>{children}</div></section></main>;
}
