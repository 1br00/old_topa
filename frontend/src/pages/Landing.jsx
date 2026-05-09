import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { useEffect, useState } from "react";
import axios from "axios";
import {
  ShieldCheck, Lightning, Key, Cpu, Code, Terminal,
  Bug, GitBranch, Lock, ArrowRight, CheckCircle, ListChecks
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Landing() {
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    axios.get(`${API}/plans`).then((r) => setPlans(r.data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f2f5]">
      {/* Header */}
      <header className="glass fixed top-0 left-0 right-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="header-logo">
            <ShieldCheck size={22} weight="duotone" className="text-[#4da3ff]" />
            <span className="font-mono font-bold text-lg tracking-tight">xss0r</span>
            <span className="label-tech ml-2 text-[#737373] hidden sm:inline">v1.4.2</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm text-[#a0a6ad]">
            <a href="#features" className="hover:text-white transition-colors" data-testid="link-features">Features</a>
            <a href="#pricing" className="hover:text-white transition-colors" data-testid="link-pricing">Pricing</a>
            <a href="#docs" className="hover:text-white transition-colors" data-testid="link-docs">Docs</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="header-login-btn">
              <Button variant="ghost" size="sm" className="rounded-none text-[#a0a6ad] hover:text-white hover:bg-white/5">Sign in</Button>
            </Link>
            <Link to="/register" data-testid="header-register-btn">
              <Button size="sm" className="rounded-none btn-primary px-4">Get access <ArrowRight size={14} className="ml-1" /></Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative pt-40 pb-24 overflow-hidden">
        <div className="absolute inset-0 bg-grid bg-grid-fade opacity-60" aria-hidden />
        <div
          className="absolute inset-0 opacity-30 mix-blend-screen"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1737505599162-d9932323a889?crop=entropy&cs=srgb&fm=jpg&q=85')",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
          aria-hidden
        />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#0a0a0a]/80 to-[#0a0a0a]" aria-hidden />

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 fade-up">
            <div className="inline-flex items-center gap-2 px-3 py-1 border border-white/10 bg-white/5 mb-6 text-xs font-mono">
              <span className="w-1.5 h-1.5 bg-[#00d4aa] rounded-full animate-pulse" />
              <span className="text-[#a0a6ad]">v1.4.2 · DOM-aware engine shipped</span>
            </div>
            <h1 className="font-mono font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tighter leading-[1.05] mb-6">
              The XSS scanner<br />
              <span className="text-[#4da3ff]">offensive teams</span><br />
              ship with.
            </h1>
            <p className="text-lg text-[#a0a6ad] max-w-xl leading-relaxed mb-8">
              xss0r is a precision scanner for reflected, stored and DOM-based XSS — purpose-built for bug bounty hunters,
              red teams and AppSec engineers. License, activate, scan.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/register" data-testid="hero-cta-register">
                <Button size="lg" className="rounded-none btn-primary px-7 h-12">
                  Start 14-day trial <ArrowRight size={16} className="ml-2" />
                </Button>
              </Link>
              <a href="#pricing" data-testid="hero-cta-pricing">
                <Button size="lg" variant="outline" className="rounded-none h-12 border-white/20 hover:bg-white/5 hover:text-white">
                  See pricing
                </Button>
              </a>
            </div>
            <div className="flex flex-wrap gap-6 mt-10 text-xs font-mono text-[#737373]">
              <span className="flex items-center gap-2"><CheckCircle size={14} className="text-[#00d4aa]" /> CLI + GUI</span>
              <span className="flex items-center gap-2"><CheckCircle size={14} className="text-[#00d4aa]" /> CI/CD ready</span>
              <span className="flex items-center gap-2"><CheckCircle size={14} className="text-[#00d4aa]" /> HWID locked licensing</span>
            </div>
          </div>

          <div className="lg:col-span-5">
            <div className="card-tech p-1 fade-up" style={{ animationDelay: "0.15s" }}>
              <div className="bg-[#0a0a0a] p-4 font-mono text-xs space-y-1.5">
                <div className="flex items-center gap-2 pb-2 border-b border-white/10 mb-2">
                  <span className="w-2.5 h-2.5 bg-[#ff4757] rounded-full" />
                  <span className="w-2.5 h-2.5 bg-[#ffab00] rounded-full" />
                  <span className="w-2.5 h-2.5 bg-[#00d4aa] rounded-full" />
                  <span className="ml-2 text-[#737373]">~/xss0r — terminal</span>
                </div>
                <div className="text-[#a0a6ad]"><span className="text-[#4da3ff]">$</span> xss0r --target https://shop.example.com --depth 3</div>
                <div className="text-[#737373]">[+] License OK · plan=pro · expires 2026-03-09</div>
                <div className="text-[#737373]">[+] Crawling 184 endpoints …</div>
                <div className="text-[#00d4aa]">[✓] DOM XSS at /search?q= via location.hash</div>
                <div className="text-[#ffab00]">[!] Reflected XSS at /profile?ref= (filtered)</div>
                <div className="text-[#00d4aa]">[✓] Stored XSS at /comments (review-form.body)</div>
                <div className="text-[#737373]">[i] 3 vulns · 1.4 MB report saved</div>
                <div className="cursor-blink text-[#4da3ff]"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16 max-w-2xl">
            <span className="label-tech">/ capabilities</span>
            <h2 className="font-mono font-bold text-3xl lg:text-4xl mt-3 mb-4 tracking-tight">
              Built for the way modern apps actually break.
            </h2>
            <p className="text-[#a0a6ad]">No theatrics. No false positives buffet. Just the payload classes that actually land.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-px bg-white/10">
            {[
              { icon: Bug, title: "DOM, Reflected, Stored", desc: "All three payload classes covered with context-aware analysis (HTML, JS, attribute, URL)." },
              { icon: Cpu, title: "DOM engine", desc: "Headless Chromium evaluates sinks (innerHTML, eval, Function, document.write) live." },
              { icon: Code, title: "Custom payloads", desc: "Drop in your own payloads & templates. Fuzz with mutation strategies." },
              { icon: GitBranch, title: "CI/CD integration", desc: "Run on every PR. Fail builds on critical findings. SARIF + JUnit output." },
              { icon: Key, title: "HWID licensing", desc: "Per-device activation, instant reset from your dashboard. No sketchy keygens." },
              { icon: Terminal, title: "CLI-first", desc: "Scriptable, headless, JSON output. Plays nicely with Burp & ZAP." },
            ].map((f, i) => (
              <div key={i} className="bg-[#0a0a0a] p-8 hover:bg-[#121212] transition-colors fade-up" style={{ animationDelay: `${i * 0.05}s` }}>
                <f.icon size={28} weight="duotone" className="text-[#4da3ff] mb-4" />
                <h3 className="font-mono font-semibold text-lg mb-2">{f.title}</h3>
                <p className="text-sm text-[#a0a6ad] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 border-t border-white/10 relative">
        <div className="absolute inset-0 bg-grid opacity-30 bg-grid-fade" aria-hidden />
        <div className="relative max-w-7xl mx-auto px-6">
          <div className="mb-16 text-center">
            <span className="label-tech">/ pricing</span>
            <h2 className="font-mono font-bold text-3xl lg:text-4xl mt-3 mb-3 tracking-tight">Simple, license-locked.</h2>
            <p className="text-[#a0a6ad]">One license. Multiple devices. Reset HWID anytime.</p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {plans.map((p, idx) => (
              <div
                key={p.id}
                data-testid={`plan-${p.id}`}
                className={`card-tech p-8 relative ${p.id === "pro" ? "border-[#4da3ff]/40 lg:scale-105 lg:-mt-2" : ""}`}
              >
                {p.id === "pro" && (
                  <span className="absolute top-0 right-0 bg-[#4da3ff] text-[#0a0a0a] text-xs font-mono px-3 py-1 font-bold">RECOMMENDED</span>
                )}
                <h3 className="font-mono font-bold text-2xl mb-1">{p.name}</h3>
                <p className="text-xs label-tech mb-6">/ {p.id}</p>
                <div className="mb-8">
                  <span className="text-5xl font-mono font-bold">${p.price}</span>
                  <span className="text-[#a0a6ad] text-sm ml-2">/ {p.period}</span>
                </div>
                <ul className="space-y-3 mb-8">
                  {p.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[#a0a6ad]">
                      <CheckCircle size={16} className="text-[#00d4aa] mt-0.5 flex-shrink-0" weight="fill" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <Link to="/register" data-testid={`plan-${p.id}-cta`}>
                  <Button
                    className={`w-full rounded-none h-11 ${
                      p.id === "pro" ? "btn-primary" : "bg-white/5 hover:bg-white/10 text-white border border-white/20"
                    }`}
                  >
                    {p.price === 0 ? "Start trial" : "Subscribe to " + p.name}
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA strip */}
      <section className="py-20 border-t border-white/10">
        <div className="max-w-5xl mx-auto px-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <div>
            <h2 className="font-mono font-bold text-3xl tracking-tight mb-3">Ready to scan?</h2>
            <p className="text-[#a0a6ad]">14-day Pro trial. No card. Activate on Windows, Linux or macOS.</p>
          </div>
          <Link to="/register" data-testid="cta-final">
            <Button size="lg" className="btn-primary rounded-none h-12 px-8">Create account <ArrowRight size={16} className="ml-2" /></Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-white/10 py-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4 text-xs font-mono text-[#737373]">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} weight="duotone" className="text-[#4da3ff]" />
            <span>xss0r © 2026 — All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-white">Terms</a>
            <a href="#" className="hover:text-white">Privacy</a>
            <a href="#" className="hover:text-white">Status</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
