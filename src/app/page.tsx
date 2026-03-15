'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import ThemeToggle from '@/components/theme-toggle';

export default function LandingPage() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.username) setIsLoggedIn(true);
      }
    } catch {
      // ignore
    }
  }, []);

  const handleGetStarted = () => {
    if (isLoggedIn) {
      router.push('/dashboard');
    } else {
      router.push('/register');
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem('cw_user');
    setIsLoggedIn(false);
  };

  const features = [
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      title: 'AI-Powered Documentation',
      desc: 'Auto-generate comprehensive wikis from any code repository with intelligent AI analysis.',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      ),
      title: 'Interactive Q&A',
      desc: 'Ask natural language questions about any repository and get accurate, context-aware answers.',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
      ),
      title: 'Visual Diagrams',
      desc: 'Automatically generate architecture diagrams, flow charts, and sequence diagrams from code.',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
      title: 'Multi-Provider AI',
      desc: 'Support for OpenAI, Google Gemini, Anthropic Claude, and local models via Ollama.',
    },
  ];

  const steps = [
    { num: '1', title: 'Enter Repository URL', desc: 'Paste any GitHub, GitLab, Bitbucket URL or local path.' },
    { num: '2', title: 'AI Analyzes Code', desc: 'Our AI reads through the entire codebase and understands the architecture.' },
    { num: '3', title: 'Get Your Wiki', desc: 'Browse an interactive, comprehensive wiki with diagrams and Q&A.' },
  ];

  const stats = [
    { label: 'AI Providers', value: '4+' },
    { label: 'Open Source', value: '100%' },
    { label: 'Git Platforms', value: '3+' },
    { label: 'Languages', value: '10+' },
  ];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-[var(--background)] border-b border-[var(--border-color)] shadow-custom">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 font-bold text-xl text-[var(--accent-primary)]">
              <svg className="w-7 h-7" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
              </svg>
              CodeWiki
            </Link>

            {/* Desktop nav */}
            <div className="hidden md:flex items-center gap-6">
              <Link href="#features" className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">Features</Link>
              <Link href="#how-it-works" className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">How it works</Link>
              <ThemeToggle />
              {isLoggedIn ? (
                <>
                  <Link href="/dashboard" className="text-sm font-medium text-[var(--accent-primary)] hover:text-[var(--highlight)] transition-colors">Dashboard</Link>
                  <button onClick={handleSignOut} className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">Sign out</button>
                </>
              ) : (
                <>
                  <Link href="/login" className="text-sm font-medium text-[var(--foreground)] hover:text-[var(--accent-primary)] transition-colors">Sign in</Link>
                  <Link href="/register" className="btn-primary text-sm px-4 py-2 rounded-lg">Sign up</Link>
                </>
              )}
            </div>

            {/* Mobile menu button */}
            <button
              className="md:hidden p-2 rounded-md text-[var(--muted)] hover:text-[var(--foreground)]"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileMenuOpen
                  ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-[var(--border-color)] bg-[var(--background)] px-4 py-3 flex flex-col gap-3">
            <Link href="#features" className="text-sm text-[var(--muted)]" onClick={() => setMobileMenuOpen(false)}>Features</Link>
            <Link href="#how-it-works" className="text-sm text-[var(--muted)]" onClick={() => setMobileMenuOpen(false)}>How it works</Link>
            {isLoggedIn ? (
              <>
                <Link href="/dashboard" className="text-sm font-medium text-[var(--accent-primary)]" onClick={() => setMobileMenuOpen(false)}>Dashboard</Link>
                <button onClick={() => { handleSignOut(); setMobileMenuOpen(false); }} className="text-sm text-left text-[var(--muted)]">Sign out</button>
              </>
            ) : (
              <>
                <Link href="/login" className="text-sm font-medium text-[var(--foreground)]" onClick={() => setMobileMenuOpen(false)}>Sign in</Link>
                <Link href="/register" className="btn-primary text-sm px-4 py-2 rounded-lg text-center" onClick={() => setMobileMenuOpen(false)}>Sign up</Link>
              </>
            )}
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-[var(--background)] to-[var(--card-bg)] py-20 md:py-32">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--accent-secondary),_transparent_60%)] opacity-40 pointer-events-none" />
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 text-center">
          <div className="inline-flex items-center gap-2 bg-[var(--accent-secondary)] text-[var(--accent-primary)] text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" /></svg>
            AI-Powered · Open Source
          </div>
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-[var(--foreground)] mb-6 leading-tight">
            Instant wikis for<br />
            <span className="text-[var(--accent-primary)]">any code repository</span>
          </h1>
          <p className="text-lg md:text-xl text-[var(--muted)] max-w-2xl mx-auto mb-10 leading-relaxed">
            CodeWiki uses AI to read your entire codebase and generate comprehensive documentation, diagrams, and an interactive Q&amp;A assistant — in minutes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleGetStarted}
              className="btn-primary px-8 py-3 text-base rounded-lg font-semibold shadow-lg"
            >
              Get started free
            </button>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 px-8 py-3 text-base rounded-lg font-semibold border border-[var(--border-color)] text-[var(--foreground)] hover:bg-[var(--card-bg)] transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              See how it works
            </Link>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="border-y border-[var(--border-color)] bg-[var(--card-bg)]">
        <div className="max-w-5xl mx-auto px-4 py-10 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {stats.map((s) => (
            <div key={s.label}>
              <div className="text-3xl font-bold text-[var(--accent-primary)]">{s.value}</div>
              <div className="text-sm text-[var(--muted)] mt-1">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-[var(--background)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] mb-4">Everything you need</h2>
            <p className="text-[var(--muted)] text-lg max-w-xl mx-auto">Powerful features to understand any codebase faster than ever before.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {features.map((f) => (
              <div key={f.title} className="card-modern p-6 hover:shadow-md transition-shadow">
                <div className="w-11 h-11 bg-[var(--accent-secondary)] text-[var(--accent-primary)] rounded-lg flex items-center justify-center mb-4">
                  {f.icon}
                </div>
                <h3 className="font-semibold text-[var(--foreground)] mb-2">{f.title}</h3>
                <p className="text-sm text-[var(--muted)] leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="py-20 bg-[var(--card-bg)] border-y border-[var(--border-color)]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] mb-4">How it works</h2>
          <p className="text-[var(--muted)] text-lg mb-14">Three simple steps to transform your repository into living documentation.</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((step, i) => (
              <div key={step.num} className="relative flex flex-col items-center">
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-5 left-[calc(50%+2rem)] w-[calc(100%-4rem)] h-px bg-[var(--border-color)]" />
                )}
                <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)] text-white font-bold text-lg flex items-center justify-center mb-4 relative z-10">
                  {step.num}
                </div>
                <h3 className="font-semibold text-[var(--foreground)] mb-2">{step.title}</h3>
                <p className="text-sm text-[var(--muted)] leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-[var(--accent-primary)]">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Ready to document your code?</h2>
          <p className="text-blue-100 text-lg mb-8">Join developers using CodeWiki to understand codebases faster.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleGetStarted}
              className="px-8 py-3 bg-white text-[var(--accent-primary)] font-semibold rounded-lg hover:bg-blue-50 transition-colors shadow-lg"
            >
              Get started free
            </button>
            <Link
              href="/dashboard"
              className="px-8 py-3 border border-white/40 text-white font-semibold rounded-lg hover:bg-white/10 transition-colors"
            >
              Open Demo
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[var(--card-bg)] border-t border-[var(--border-color)] py-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-2 font-bold text-lg text-[var(--accent-primary)]">
              <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
              </svg>
              CodeWiki
            </div>
            <div className="flex items-center gap-6 text-sm text-[var(--muted)]">
              <Link href="/dashboard" className="hover:text-[var(--foreground)] transition-colors">App</Link>
              <a href="https://github.com/AsyncFuncAI/deepwiki-open" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--foreground)] transition-colors">GitHub</a>
              <ThemeToggle />
            </div>
          </div>
          <p className="text-center text-sm text-[var(--muted)] mt-6">
            © {new Date().getFullYear()} CodeWiki. Open source under MIT License.
          </p>
        </div>
      </footer>
    </div>
  );
}
