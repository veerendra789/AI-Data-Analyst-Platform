import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthLayout } from "./LoginPage";
import { useAuth } from "../context/useAuth";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await register(form.name, form.email, form.password);
      navigate("/dashboard", { replace: true });
    } catch {
      setError("We could not create that account. Check the details and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return <AuthLayout title="Create your workspace" subtitle="Start turning your data into clearer decisions."><form className="space-y-5" onSubmit={submit}><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Name</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" minLength={2} required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Email</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Password</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" minLength={8} required type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>{error && <p className="text-sm text-red-700">{error}</p>}<button className="w-full rounded-lg bg-ink px-4 py-3 text-sm font-semibold text-paper disabled:opacity-60" disabled={submitting} type="submit">{submitting ? "Creating..." : "Create account"}</button></form><p className="mt-6 text-center text-sm text-ink/55">Already registered? <Link className="font-semibold text-moss" to="/login">Sign in</Link></p></AuthLayout>;
}
