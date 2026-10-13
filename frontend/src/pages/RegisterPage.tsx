import axios from "axios";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthLayout } from "./LoginPage";
import { useAuth } from "../context/useAuth";
import { supabaseAuthErrorMessage } from "../services/supabaseAuthErrors";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const hasSession = await register(form.name, form.email, form.password);
      if (hasSession) navigate("/dashboard", { replace: true });
      else setNotice("Check your email to confirm your account, then sign in.");
    } catch (requestError) {
      const authMessage = supabaseAuthErrorMessage(requestError, "register");
      if (authMessage) {
        setError(authMessage);
      } else if (axios.isAxiosError(requestError) && !requestError.response) {
        setError("The registration service is unavailable. Please try again shortly.");
      } else if (axios.isAxiosError(requestError) && requestError.response?.status === 409) {
        setError("An account with this email already exists.");
      } else if (axios.isAxiosError(requestError) && requestError.response?.status === 422) {
        setError("Enter a valid name and email, and use a password with at least 8 characters.");
      } else {
        setError("We could not create that account. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  return <AuthLayout title="Create your workspace" subtitle="Start turning your data into clearer decisions."><form className="space-y-5" onSubmit={submit}><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Full name</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" minLength={2} required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Email</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Password</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" minLength={8} required type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label><label className="block text-sm font-medium"><span className="mb-2 block text-ink/70">Confirm password</span><input className="w-full rounded-lg border border-ink/15 bg-white px-3 py-3 outline-none focus:border-moss" minLength={8} required type="password" value={form.confirmPassword} onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })} /></label>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}{notice && <p role="status" className="text-sm text-moss">{notice}</p>}<button className="w-full rounded-lg bg-ink px-4 py-3 text-sm font-semibold text-paper disabled:opacity-60" disabled={submitting} type="submit">{submitting ? "Creating..." : "Create account"}</button></form><p className="mt-6 text-center text-sm text-ink/55">Already registered? <Link className="font-semibold text-moss" to="/login">Sign in</Link></p></AuthLayout>;
}
