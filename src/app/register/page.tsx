'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username || !email || !password || !confirm) {
      setError('所有字段均为必填项。');
      return;
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致。');
      return;
    }
    if (password.length < 8) {
      setError('密码长度至少为 8 个字符。');
      return;
    }
    setLoading(true);
    const success = await register(username, email, password);
    setLoading(false);
    if (success) {
      router.push('/dashboard');
    } else {
      setError('注册失败，请重试。');
    }
  };

  return (
    <div className="min-h-screen bg-[var(--background)] flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 font-bold text-2xl text-[var(--accent-primary)]">
            <img src="/favicon.ico" alt="CodeWiki logo" className="w-7 h-7" />
            CodeWiki
          </Link>
          <p className="text-[var(--muted)] text-sm mt-2">注册账户</p>
        </div>

        {/* Card */}
        <div className="card-modern p-8 shadow-custom">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                用户名
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名"
                className="input-modern w-full text-[var(--foreground)] bg-[var(--background)]"
                autoComplete="username"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                电子邮箱
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="电子邮箱"
                className="input-modern w-full text-[var(--foreground)] bg-[var(--background)]"
                autoComplete="email"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                密码
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="input-modern w-full text-[var(--foreground)] bg-[var(--background)]"
                autoComplete="new-password"
              />
            </div>
            <div>
              <label htmlFor="confirm" className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                确认密码
              </label>
              <input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                className="input-modern w-full text-[var(--foreground)] bg-[var(--background)]"
                autoComplete="new-password"
              />
            </div>

            {error && (
              <p className="text-sm text-red-500">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2.5 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? '注册中...' : '创建账户'}
            </button>
          </form>

          <p className="text-center text-sm text-[var(--muted)] mt-6">
            已有账户？{' '}
            <Link href="/login" className="text-[var(--accent-primary)] font-medium hover:underline">
              立即登录
            </Link>
          </p>
        </div>

        <p className="text-center text-xs text-[var(--muted)] mt-6">
          <Link href="/" className="hover:underline">← 返回首页</Link>
        </p>
      </div>
    </div>
  );
}
