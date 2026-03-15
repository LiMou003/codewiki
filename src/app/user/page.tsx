'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import ThemeToggle from '@/components/theme-toggle';

interface StoredProject {
  owner: string;
  repo: string;
  type: string;
  timestamp?: number;
}

export default function UserPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; email: string } | null>(null);
  const [recentProjects, setRecentProjects] = useState<StoredProject[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) setUser(JSON.parse(stored));
    } catch {
      // ignore
    }

    try {
      const projects = localStorage.getItem('processedProjects');
      if (projects) {
        const parsed = JSON.parse(projects);
        if (Array.isArray(parsed)) {
          setRecentProjects(parsed.slice(0, 5));
        }
      }
    } catch {
      // ignore
    }
  }, []);

  const handleSignOut = () => {
    localStorage.removeItem('cw_user');
    router.push('/');
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-[var(--background)] flex items-center justify-center">
        <div className="text-center">
          <p className="text-[var(--muted)] mb-4">You are not signed in.</p>
          <Link href="/login" className="btn-primary px-6 py-2.5 rounded-lg font-semibold">
            Sign in
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
            Back to Dashboard
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
            Sign out
          </button>
        </div>

        {/* Recent Projects */}
        <div className="card-modern p-6 shadow-custom">
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Recent Projects</h2>
          {recentProjects.length > 0 ? (
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
                    View →
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-[var(--muted)]">No recent projects. <Link href="/dashboard" className="text-[var(--accent-primary)] hover:underline">Generate your first wiki</Link>.</p>
          )}
        </div>

        {/* Account Settings */}
        <div className="card-modern p-6 shadow-custom">
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Account Settings</h2>
          <div className="rounded-lg bg-[var(--accent-secondary)] border border-[var(--border-color)] p-4 flex items-start gap-3">
            <svg className="w-5 h-5 text-[var(--accent-primary)] flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-[var(--foreground)]">Backend integration required</p>
              <p className="text-xs text-[var(--muted)] mt-1">Account settings like password changes and email updates require backend integration. This is a frontend demo using local storage only.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
