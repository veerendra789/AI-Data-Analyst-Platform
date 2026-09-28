import { useState } from "react";
import { ArrowLeft, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [signedOut, setSignedOut] = useState(false);

  if (!user) return null;

  const signOut = () => {
    logout();
    setSignedOut(true);
    navigate("/login", { replace: true });
  };

  return <main className="min-h-screen bg-paper px-6 py-8 text-ink sm:px-10"><div className="mx-auto max-w-4xl"><Link className="inline-flex items-center gap-2 text-sm font-semibold text-moss" to="/dashboard"><ArrowLeft size={16} />Back to dashboard</Link><header className="mt-8 border-b border-ink/10 pb-7"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-moss">Account</p><h1 className="mt-2 font-display text-4xl">Profile</h1><p className="mt-2 text-ink/60">Your identity and workspace access.</p></header><section className="mt-8 grid gap-5 md:grid-cols-[180px_1fr]"><div className="flex h-36 w-36 items-center justify-center rounded-2xl bg-ink text-4xl font-semibold text-lime"><UserRound size={52} strokeWidth={1.5} /></div><div className="rounded-xl border border-ink/10 bg-white p-6"><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-moss">Signed-in user</p><h2 className="mt-2 font-display text-3xl">{user.name}</h2><p className="mt-2 text-ink/60">{user.email}</p></div><span className="inline-flex items-center gap-2 rounded-full bg-moss/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-moss"><ShieldCheck size={14} />{user.role}</span></div><dl className="mt-8 grid gap-5 border-t border-ink/10 pt-5 sm:grid-cols-2"><div><dt className="text-xs uppercase tracking-[0.12em] text-ink/45">Member since</dt><dd className="mt-1 text-sm font-medium">{new Date(user.created_at).toLocaleDateString()}</dd></div><div><dt className="text-xs uppercase tracking-[0.12em] text-ink/45">Access</dt><dd className="mt-1 text-sm font-medium">Private workspace</dd></div></dl><button className="mt-8 inline-flex items-center gap-2 rounded-lg border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-700 transition hover:bg-red-50" onClick={signOut} type="button"><LogOut size={16} />Sign out</button>{signedOut && <p className="mt-3 text-sm text-ink/55">Your session has ended.</p>}</div></section></div></main>;
}
