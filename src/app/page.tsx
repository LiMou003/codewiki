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
      title: 'AI 驱动文档生成',
      desc: '利用智能 AI 分析，自动为任意代码仓库生成全面的 Wiki 文档。',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      ),
      title: '交互式问答',
      desc: '用自然语言提问任意仓库的问题，获取准确、上下文相关的答案。',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
        </svg>
      ),
      title: '可视化图表',
      desc: '自动从代码生成架构图、流程图和时序图。',
    },
    {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
      ),
      title: '强大的 AI 提供商支持',
      desc: 'Qwen系列模型的强大回答能力,支持qwen3.5-plus、qwen3.5-flash等模型。',
    },
  ];

  const steps = [
    { num: '1', title: '输入仓库地址', desc: '粘贴任意 GitHub链接或本地路径。' },
    { num: '2', title: 'AI 分析代码', desc: '我们的 AI 读取整个代码库，深入理解其架构。' },
    { num: '3', title: '获取你的 Wiki', desc: '浏览包含图表和问答功能的交互式、全面的 Wiki。' },
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
              <Link href="#features" className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">功能特性</Link>
              <Link href="#how-it-works" className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">使用流程</Link>
              <ThemeToggle />
              {isLoggedIn ? (
                <>
                  <Link href="/dashboard" className="text-sm font-medium text-[var(--accent-primary)] hover:text-[var(--highlight)] transition-colors">控制台</Link>
                  <button onClick={handleSignOut} className="text-sm text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">退出登录</button>
                </>
              ) : (
                <>
                  <Link href="/login" className="text-sm font-medium text-[var(--foreground)] hover:text-[var(--accent-primary)] transition-colors">登录</Link>
                  <Link href="/register" className="btn-primary text-sm px-4 py-2 rounded-lg">注册</Link>
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
            <Link href="#features" className="text-sm text-[var(--muted)]" onClick={() => setMobileMenuOpen(false)}>功能特性</Link>
            <Link href="#how-it-works" className="text-sm text-[var(--muted)]" onClick={() => setMobileMenuOpen(false)}>使用流程</Link>
            {isLoggedIn ? (
              <>
                <Link href="/dashboard" className="text-sm font-medium text-[var(--accent-primary)]" onClick={() => setMobileMenuOpen(false)}>控制台</Link>
                <button onClick={() => { handleSignOut(); setMobileMenuOpen(false); }} className="text-sm text-left text-[var(--muted)]">退出登录</button>
              </>
            ) : (
              <>
                <Link href="/login" className="text-sm font-medium text-[var(--foreground)]" onClick={() => setMobileMenuOpen(false)}>登录</Link>
                <Link href="/register" className="btn-primary text-sm px-4 py-2 rounded-lg text-center" onClick={() => setMobileMenuOpen(false)}>注册</Link>
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
            AI 驱动 · 开源
          </div>
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight text-[var(--foreground)] mb-6 leading-tight">
            为任意代码仓库<br />
            <span className="text-[var(--accent-primary)]">即时生成 Wiki</span>
          </h1>
          <p className="text-lg md:text-xl text-[var(--muted)] max-w-2xl mx-auto mb-10 leading-relaxed">
            CodeWiki 利用 AI 读取你的整个代码库，在几分钟内生成全面的文档、图表和交互式问答助手。
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={handleGetStarted}
              className="btn-primary px-8 py-3 text-base rounded-lg font-semibold shadow-lg"
            >
              免费开始使用
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 bg-[var(--background)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] mb-4">一切你所需要的</h2>
            <p className="text-[var(--muted)] text-lg max-w-xl mx-auto">强大的功能，让你比以往更快地理解任意代码库。</p>
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
          <h2 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] mb-4">使用流程</h2>
          <p className="text-[var(--muted)] text-lg mb-14">三个简单步骤，将你的仓库转变为活跃的文档。</p>
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
              <a href="https://github.com/LiMou003/codewiki" target="_blank" rel="noopener noreferrer" className="hover:text-[var(--foreground)] transition-colors">GitHub</a>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
