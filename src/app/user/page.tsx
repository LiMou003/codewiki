'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import ThemeToggle from '@/components/theme-toggle';
import {
  getUserSettings,
  updateUserSettings,
  getDefaultConfig,
  UserConfig,
} from '@/services/userSettingsApi';
import { useAuth } from '@/contexts/AuthContext';

interface StoredProject {
  owner: string;
  repo: string;
  type: string;
  timestamp?: number;
}

const DIMENSION_OPTIONS = [
  { value: 64, label: '64' },
  { value: 128, label: '128' },
  { value: 256, label: '256（轻量）' },
  { value: 512, label: '512' },
  { value: 1024, label: '1024（默认）' },
  { value: 1152, label: '1152（高精度）' },
];

export default function UserPage() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [recentProjects, setRecentProjects] = useState<StoredProject[]>([]);

  // Settings state
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Form state
  const [topK, setTopK] = useState(20);
  const [embeddingDimension, setEmbeddingDimension] = useState(1024);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(60);

  const loadSettings = useCallback(async () => {
    try {
      const s = await getUserSettings();
      const cfg = s.config || getDefaultConfig();
      setTopK(cfg.retrieval?.top_k ?? 20);
      setEmbeddingDimension(cfg.embedding?.dimension ?? 1024);
      setAutoRefreshEnabled(cfg.auto_refresh?.enabled ?? true);
      setAutoRefreshInterval(cfg.auto_refresh?.interval_minutes ?? 60);
    } catch {
      // use defaults
      const d = getDefaultConfig();
      setTopK(d.retrieval?.top_k ?? 20);
      setEmbeddingDimension(d.embedding?.dimension ?? 1024);
      setAutoRefreshEnabled(d.auto_refresh?.enabled ?? true);
      setAutoRefreshInterval(d.auto_refresh?.interval_minutes ?? 60);
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    try {
      const projects = localStorage.getItem('processedProjects');
      if (projects) {
        const parsed = JSON.parse(projects);
        if (Array.isArray(parsed)) setRecentProjects(parsed.slice(0, 5));
      }
    } catch { /* ignore */ }

    loadSettings();
  }, [loadSettings]);

  const handleSignOut = () => {
    logout();
    router.push('/login');
  };

  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const config: UserConfig = {
        embedding: { dimension: embeddingDimension },
        retrieval: { top_k: topK },
        auto_refresh: {
          enabled: autoRefreshEnabled,
          interval_minutes: autoRefreshInterval,
        },
      };
      await updateUserSettings({ config });
      setSettingsMsg({ type: 'success', text: '设置已保存' });
    } catch {
      setSettingsMsg({ type: 'error', text: '保存失败，请重试' });
    } finally {
      setSettingsSaving(false);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-[var(--background)] flex items-center justify-center">
        <div className="text-center">
          <p className="text-[var(--muted)] mb-4">您尚未登录。</p>
          <Link href="/login" className="btn-primary px-6 py-2.5 rounded-lg font-semibold">
            登录
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-[var(--background)] border-b border-[var(--border-color)] shadow-custom">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
          <Link href="/dashboard" className="flex items-center gap-2 text-sm font-medium text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            返回控制台
          </Link>
          <div className="flex items-center gap-4">
            <ThemeToggle />
          </div>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-8">
        {/* Profile Card */}
        <div className="card-modern p-6 shadow-custom">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-full bg-[var(--accent-primary)] text-white flex items-center justify-center text-2xl font-bold">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div>
              <h1 className="text-xl font-bold text-[var(--foreground)]">{user.username}</h1>
              <p className="text-sm text-[var(--muted)]">{user.email}</p>
            </div>
          </div>
          <button
            onClick={handleSignOut}
            className="w-full sm:w-auto px-6 py-2 rounded-lg border border-red-300 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 text-sm font-medium transition-colors"
          >
            退出登录
          </button>
        </div>

        {recentProjects.length > 0 && (
          <div className="card-modern p-6 shadow-custom">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">最近项目</h2>
            <ul className="space-y-2">
              {recentProjects.map((p, i) => (
                <li key={i} className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)] border border-[var(--border-color)]">
                  <div>
                    <span className="text-sm font-medium text-[var(--foreground)]">{p.owner}/{p.repo}</span>
                    <span className="ml-2 text-xs text-[var(--muted)] capitalize">{p.type}</span>
                  </div>
                  <Link
                    href={`/${p.owner}/${p.repo}`}
                    className="text-xs text-[var(--accent-primary)] hover:underline"
                  >
                    查看 →
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* RAG / Index Settings */}
        <div className="card-modern p-6 shadow-custom">
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-5">检索与索引设置</h2>

          {settingsLoading ? (
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="w-3 h-3 rounded-full border-2 border-[var(--accent-primary)] border-t-transparent animate-spin" />
              加载设置中...
            </div>
          ) : (
            <div className="space-y-6">
              {/* Top-K */}
              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                  向量检索 Top-K
                </label>
                <p className="text-xs text-[var(--muted)] mb-2">
                  控制 RAG 检索时返回的代码片段数量。值越大上下文越丰富，但会增加 token 消耗。建议 10–30。
                </p>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={100}
                    value={topK}
                    onChange={e => setTopK(Number(e.target.value))}
                    className="flex-1 h-1.5 rounded-full appearance-none bg-[var(--border-color)] cursor-pointer accent-[var(--accent-primary)]"
                  />
                  <span className="text-sm font-mono font-semibold text-[var(--foreground)] w-8 text-center">
                    {topK}
                  </span>
                </div>
              </div>

              {/* Vector Dimension */}
              <div>
                <label className="block text-sm font-medium text-[var(--foreground)] mb-1.5">
                  向量维度
                </label>
                <p className="text-xs text-[var(--muted)] mb-2">
                  指定 DashScope Embedding API 返回的向量维度。
                  维度越小索引越节省空间，但精度会有所下降。
                  <strong>更改后需删除并重新索引仓库才能生效。</strong>
                </p>
                <select
                  value={embeddingDimension}
                  onChange={e => setEmbeddingDimension(Number(e.target.value))}
                  className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/20"
                >
                  {DIMENSION_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Auto Refresh */}
              {/* <div>
                <label className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)] mb-1.5">
                  <input
                    type="checkbox"
                    checked={autoRefreshEnabled}
                    onChange={e => setAutoRefreshEnabled(e.target.checked)}
                    className="rounded accent-[var(--accent-primary)]"
                  />
                  启用仓库自动增量更新
                </label>
                <p className="text-xs text-[var(--muted)] mb-2">
                  定时对远程仓库执行 git pull，自动将变更的文件重新向量化。
                </p>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-[var(--muted)] whitespace-nowrap">更新间隔：</label>
                  <input
                    type="number"
                    min={5}
                    max={1440}
                    value={autoRefreshInterval}
                    onChange={e => setAutoRefreshInterval(Number(e.target.value))}
                    disabled={!autoRefreshEnabled}
                    className="w-24 rounded-lg border border-[var(--border-color)] bg-[var(--background)] px-2 py-1.5 text-sm text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/20 disabled:opacity-40"
                  />
                  <span className="text-xs text-[var(--muted)]">分钟</span>
                </div>
              </div> */}

              {/* Save button + feedback */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={handleSaveSettings}
                  disabled={settingsSaving}
                  className="px-5 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {settingsSaving ? '保存中...' : '保存设置'}
                </button>
                {settingsMsg && (
                  <span className={`text-xs ${settingsMsg.type === 'success' ? 'text-green-500' : 'text-red-500'}`}>
                    {settingsMsg.text}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
