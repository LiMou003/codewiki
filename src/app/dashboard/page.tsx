'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { FaGithub, FaCoffee, FaTwitter } from 'react-icons/fa';
import ThemeToggle from '@/components/theme-toggle';
import Mermaid from '../../components/Mermaid';
import ConfigurationModal from '@/components/ConfigurationModal';
import ProcessedProjects from '@/components/ProcessedProjects';
import { extractUrlPath, extractUrlDomain } from '@/utils/urlDecoder';
import { useProcessedProjects } from '@/hooks/useProcessedProjects';
import { useLanguage } from '@/contexts/LanguageContext';
import { useAuth } from '@/contexts/AuthContext';

// Define the demo mermaid charts outside the component
const DEMO_FLOW_CHART = `graph TD
  A[代码仓库] --> B[CodeWiki]
  B --> C[架构图]
  B --> D[组件关系]
  B --> E[数据流]
  B --> F[流程图]

  style A fill:#dbeafe,stroke:#2563eb
  style B fill:#eff6ff,stroke:#2563eb
  style C fill:#dbeafe,stroke:#1d4ed8
  style D fill:#bfdbfe,stroke:#1d4ed8
  style E fill:#93c5fd,stroke:#1d4ed8
  style F fill:#60a5fa,stroke:#1d4ed8`;

const DEMO_SEQUENCE_CHART = `sequenceDiagram
  participant 用户
  participant CodeWiki
  participant GitHub

  用户->>CodeWiki: 输入仓库地址
  CodeWiki->>GitHub: 请求仓库数据
  GitHub-->>CodeWiki: 返回仓库数据
  CodeWiki->>CodeWiki: 处理并分析代码
  CodeWiki-->>用户: 展示包含图表的 Wiki

  Note over 用户,GitHub: CodeWiki 支持时序图以可视化交互流程`;

export default function Dashboard() {
  const router = useRouter();
  const { language, setLanguage, messages, supportedLanguages } = useLanguage();
  const { projects, isLoading: projectsLoading, error: projectsError } = useProcessedProjects();
  const { logout } = useAuth();

  // User state from localStorage
  const [user, setUser] = useState<{ username: string; email: string } | null>(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) setUser(JSON.parse(stored));
    } catch {
      // ignore
    }
  }, []);

  const handleSignOut = () => {
    logout();
    setUser(null);
    router.push('/');
  };

  // Create a simple translation function
  const t = (key: string, params: Record<string, string | number> = {}): string => {
    const keys = key.split('.');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let value: any = messages;
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        return key;
      }
    }
    if (typeof value === 'string') {
      return Object.entries(params).reduce((acc: string, [paramKey, paramValue]) => {
        return acc.replace(`{${paramKey}}`, String(paramValue));
      }, value);
    }
    return key;
  };

  const [repositoryInput, setRepositoryInput] = useState('https://github.com/AsyncFuncAI/deepwiki-open');

  const REPO_CONFIG_CACHE_KEY = 'deepwikiRepoConfigCache';

  const loadConfigFromCache = useCallback((repoUrl: string) => {
    if (!repoUrl) return;
    try {
      const cachedConfigs = localStorage.getItem(REPO_CONFIG_CACHE_KEY);
      if (cachedConfigs) {
        const configs = JSON.parse(cachedConfigs);
        const config = configs[repoUrl.trim()];
        if (config) {
          setSelectedLanguage(config.selectedLanguage || language);
          setIsComprehensiveView(config.isComprehensiveView === undefined ? true : config.isComprehensiveView);
          setProvider(config.provider || '');
          setModel(config.model || '');
          setIsCustomModel(config.isCustomModel || false);
          setCustomModel(config.customModel || '');
          setSelectedPlatform(config.selectedPlatform || 'github');
          setExcludedDirs(config.excludedDirs || '');
          setExcludedFiles(config.excludedFiles || '');
          setIncludedDirs(config.includedDirs || '');
          setIncludedFiles(config.includedFiles || '');
        }
      }
    } catch (error) {
      console.error('Error loading config from localStorage:', error);
    }
  }, [language]);

  const handleRepositoryInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newRepoUrl = e.target.value;
    setRepositoryInput(newRepoUrl);
    if (newRepoUrl.trim() !== '') {
      loadConfigFromCache(newRepoUrl);
    }
  };

  useEffect(() => {
    if (repositoryInput) {
      loadConfigFromCache(repositoryInput);
    }
  }, [repositoryInput, loadConfigFromCache]);

  const [provider, setProvider] = useState<string>('');
  const [model, setModel] = useState<string>('');
  const [isCustomModel, setIsCustomModel] = useState<boolean>(false);
  const [customModel, setCustomModel] = useState<string>('');
  const [isComprehensiveView, setIsComprehensiveView] = useState<boolean>(true);
  const [excludedDirs, setExcludedDirs] = useState('');
  const [excludedFiles, setExcludedFiles] = useState('');
  const [includedDirs, setIncludedDirs] = useState('');
  const [includedFiles, setIncludedFiles] = useState('');
  const [selectedPlatform, setSelectedPlatform] = useState<'github' | 'gitlab' | 'bitbucket'>('github');
  const [accessToken, setAccessToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<string>(language);
  const [authRequired, setAuthRequired] = useState<boolean>(false);
  const [authCode, setAuthCode] = useState<string>('');
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true);
  const hasProjects = !projectsLoading && projects.length > 0;

  useEffect(() => {
    setLanguage(selectedLanguage);
  }, [selectedLanguage, setLanguage]);

  useEffect(() => {
    const fetchAuthStatus = async () => {
      try {
        setIsAuthLoading(true);
        const response = await fetch('/api/auth/status');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        setAuthRequired(data.auth_required);
      } catch (err) {
        console.error('Failed to fetch auth status:', err);
        setAuthRequired(true);
      } finally {
        setIsAuthLoading(false);
      }
    };
    fetchAuthStatus();
  }, []);

  const parseRepositoryInput = (input: string): {
    owner: string;
    repo: string;
    type: string;
    fullPath?: string;
    localPath?: string;
  } | null => {
    input = input.trim();
    let owner = '', repo = '', type = 'github', fullPath;
    let localPath: string | undefined;

    const windowsPathRegex = /^[a-zA-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$/;
    const customGitRegex = /^(?:https?:\/\/)?([^\/]+)\/(.+?)\/([^\/]+)(?:\.git)?\/?$/;

    if (windowsPathRegex.test(input)) {
      type = 'local';
      localPath = input;
      repo = input.split('\\').pop() || 'local-repo';
      owner = 'local';
    } else if (input.startsWith('/')) {
      type = 'local';
      localPath = input;
      repo = input.split('/').filter(Boolean).pop() || 'local-repo';
      owner = 'local';
    } else if (customGitRegex.test(input)) {
      const domain = extractUrlDomain(input);
      if (domain?.includes('github.com')) {
        type = 'github';
      } else if (domain?.includes('gitlab.com') || domain?.includes('gitlab.')) {
        type = 'gitlab';
      } else if (domain?.includes('bitbucket.org') || domain?.includes('bitbucket.')) {
        type = 'bitbucket';
      } else {
        type = 'web';
      }
      fullPath = extractUrlPath(input)?.replace(/\.git$/, '');
      const parts = fullPath?.split('/') ?? [];
      if (parts.length >= 2) {
        repo = parts[parts.length - 1] || '';
        owner = parts[parts.length - 2] || '';
      }
    } else {
      console.error('Unsupported URL format:', input);
      return null;
    }

    if (!owner || !repo) return null;
    owner = owner.trim();
    repo = repo.trim();
    if (repo.endsWith('.git')) repo = repo.slice(0, -4);
    return { owner, repo, type, fullPath, localPath };
  };

  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedRepo = parseRepositoryInput(repositoryInput);
    if (!parsedRepo) {
      setError('Invalid repository format. Please use a GitHub/GitLab/Bitbucket URL, owner/repo, or local path.');
      return;
    }
    setError(null);
    setIsConfigModalOpen(true);
  };

  const validateAuthCode = async () => {
    try {
      if (authRequired) {
        if (!authCode) return false;
        const response = await fetch('/api/auth/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: authCode }),
        });
        if (!response.ok) return false;
        const data = await response.json();
        return data.success || false;
      }
    } catch {
      return false;
    }
    return true;
  };

  const handleGenerateWiki = async () => {
    const validation = await validateAuthCode();
    if (!validation) {
      setError('Authorization code validation failed.');
      setIsConfigModalOpen(false);
      return;
    }

    if (isSubmitting) return;

    try {
      const currentRepoUrl = repositoryInput.trim();
      if (currentRepoUrl) {
        const existingConfigs = JSON.parse(localStorage.getItem(REPO_CONFIG_CACHE_KEY) || '{}');
        existingConfigs[currentRepoUrl] = {
          selectedLanguage, isComprehensiveView, provider, model,
          isCustomModel, customModel, selectedPlatform,
          excludedDirs, excludedFiles, includedDirs, includedFiles,
        };
        localStorage.setItem(REPO_CONFIG_CACHE_KEY, JSON.stringify(existingConfigs));
      }
    } catch (error) {
      console.error('Error saving config to localStorage:', error);
    }

    setIsSubmitting(true);

    const parsedRepo = parseRepositoryInput(repositoryInput);
    if (!parsedRepo) {
      setError('Invalid repository format.');
      setIsSubmitting(false);
      return;
    }

    const { owner, repo, type, localPath } = parsedRepo;
    const params = new URLSearchParams();
    if (accessToken) params.append('token', accessToken);
    params.append('type', (type === 'local' ? type : selectedPlatform) || 'github');
    if (localPath) {
      params.append('local_path', encodeURIComponent(localPath));
    } else {
      params.append('repo_url', encodeURIComponent(repositoryInput));
    }
    params.append('provider', provider);
    params.append('model', model);
    if (isCustomModel && customModel) params.append('custom_model', customModel);
    if (excludedDirs) params.append('excluded_dirs', excludedDirs);
    if (excludedFiles) params.append('excluded_files', excludedFiles);
    if (includedDirs) params.append('included_dirs', includedDirs);
    if (includedFiles) params.append('included_files', includedFiles);
    params.append('language', selectedLanguage);
    params.append('comprehensive', isComprehensiveView.toString());

    const queryString = params.toString() ? `?${params.toString()}` : '';
    router.push(`/${owner}/${repo}${queryString}`);
  };

  return (
    <div className="min-h-screen paper-texture flex flex-col">
      {/* Top Navbar */}
      <nav className="sticky top-0 z-50 bg-[var(--background)]/95 backdrop-blur border-b border-[var(--border-color)] shadow-custom">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
          <Link href="/" className="flex items-center gap-2 font-bold text-lg text-[var(--accent-primary)]">
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
            </svg>
            CodeWiki
          </Link>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3 text-[var(--muted)]">
              <a href="https://github.com/AsyncFuncAI/deepwiki-open" target="_blank" rel="noreferrer" className="hover:text-[var(--accent-primary)] transition-colors">
                <FaGithub />
              </a>
              <a href="https://buymeacoffee.com/sheing" target="_blank" rel="noreferrer" className="hover:text-[var(--accent-primary)] transition-colors">
                <FaCoffee />
              </a>
              <a href="https://x.com/sashimikun_void" target="_blank" rel="noreferrer" className="hover:text-[var(--accent-primary)] transition-colors">
                <FaTwitter />
              </a>
            </div>
            <ThemeToggle />
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 text-sm font-medium text-[var(--foreground)] hover:text-[var(--accent-primary)] transition-colors"
                >
                  <div className="w-7 h-7 rounded-full bg-[var(--accent-primary)] text-white flex items-center justify-center text-xs font-bold">
                    {user.username.charAt(0).toUpperCase()}
                  </div>
                  {user.username}
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-44 bg-[var(--card-bg)] border border-[var(--border-color)] rounded-lg shadow-lg py-1 z-50">
                    <Link href="/user" className="block px-4 py-2 text-sm text-[var(--foreground)] hover:bg-[var(--accent-secondary)] transition-colors" onClick={() => setUserMenuOpen(false)}>
                      个人中心
                    </Link>
                    <button onClick={() => { setUserMenuOpen(false); handleSignOut(); }} className="w-full text-left px-4 py-2 text-sm text-[var(--foreground)] hover:bg-[var(--accent-secondary)] transition-colors">
                      退出登录
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link href="/login" className="text-sm font-medium text-[var(--accent-primary)] hover:underline">
                登录
              </Link>
            )}
          </div>
        </div>
      </nav>

      <div className="flex-1 p-4 md:p-8 flex flex-col gap-6 max-w-7xl mx-auto w-full">
        <header className="relative overflow-hidden rounded-2xl border border-[var(--border-color)] bg-gradient-to-br from-[var(--accent-primary)]/10 via-[var(--background)] to-[var(--background)] shadow-custom">
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute -top-16 -right-12 w-64 h-64 bg-[var(--accent-primary)]/10 rounded-full blur-3xl" />
            <div className="absolute -bottom-10 -left-6 w-56 h-56 bg-[var(--accent-primary)]/15 rounded-full blur-3xl" />
          </div>
          <div className="relative grid lg:grid-cols-[1.15fr,1fr] gap-8 p-6 md:p-8 items-start">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] text-xs font-semibold border border-[var(--accent-primary)]/30">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2a10 10 0 00-3.162 19.478c.5.09.684-.216.684-.48 0-.236-.008-.864-.013-1.696-2.782.604-3.369-1.343-3.369-1.343-.454-1.153-1.109-1.46-1.109-1.46-.907-.62.069-.607.069-.607 1.003.07 1.532 1.031 1.532 1.031.892 1.53 2.341 1.088 2.91.833.091-.647.35-1.088.636-1.338-2.22-.252-4.555-1.112-4.555-4.944 0-1.091.39-1.985 1.029-2.684-.103-.253-.446-1.272.098-2.65 0 0 .84-.269 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.295 2.748-1.026 2.748-1.026.546 1.378.203 2.397.1 2.65.64.699 1.028 1.593 1.028 2.684 0 3.842-2.338 4.688-4.566 4.936.359.309.679.919.679 1.852 0 1.337-.012 2.417-.012 2.747 0 .266.18.574.688.476A10.002 10.002 0 0012 2z" />
                </svg>
                控制台 · Dashboard
              </div>
              <div className="space-y-2">
                <h1 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] leading-tight">
                  {t('home.welcome')}
                </h1>
                <p className="text-[var(--muted)] text-sm md:text-base max-w-3xl leading-relaxed">
                  {t('home.description')}
                </p>
              </div>
              <div className="grid sm:grid-cols-3 gap-3">
                {[
                  { title: t('projects.existingProjects'), desc: t('projects.browseExisting'), tone: 'from-[var(--accent-primary)]/15 to-[var(--accent-primary)]/5' },
                  { title: t('home.quickStart'), desc: t('home.enterRepoUrl'), tone: 'from-emerald-500/10 to-emerald-500/5' },
                  { title: t('home.advancedVisualization'), desc: t('home.diagramDescription'), tone: 'from-indigo-500/10 to-indigo-500/5' },
                ].map((item) => (
                  <div key={item.title} className={`rounded-xl bg-gradient-to-br ${item.tone} border border-[var(--border-color)] shadow-custom p-3 text-sm text-[var(--foreground)]`}>
                    <p className="font-semibold text-[var(--accent-primary)]">{item.title}</p>
                    <p className="text-xs text-[var(--muted)] mt-1 leading-relaxed">{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-[var(--card-bg)]/90 backdrop-blur rounded-2xl border border-[var(--border-color)] shadow-custom p-6 space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[var(--muted)] text-xs font-medium uppercase tracking-wide">Repository</p>
                  <h2 className="text-xl font-semibold text-[var(--foreground)]">生成你的 Wiki</h2>
                  <p className="text-[var(--muted)] text-xs mt-1">支持 GitHub / GitLab / BitBucket 或本地路径</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsConfigModalOpen(true)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border-color)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] transition-colors"
                >
                  高级配置
                </button>
              </div>
              <form onSubmit={handleFormSubmit} className="space-y-3">
                <label className="text-xs font-medium text-[var(--muted)]" htmlFor="repositoryInput">
                  {t('form.repoPlaceholder') || 'owner/repo, GitHub/GitLab/BitBucket URL, or local folder path'}
                </label>
                <div className="relative">
                  <input
                    id="repositoryInput"
                    type="text"
                    value={repositoryInput}
                    onChange={handleRepositoryInputChange}
                    placeholder={t('home.enterRepoUrl')}
                    className="input-modern block w-full pl-3 pr-3 py-3 text-[var(--foreground)] bg-[var(--background)] border border-[var(--border-color)] rounded-xl focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/30 transition"
                  />
                  {error && <div className="text-red-500 text-xs mt-1">{error}</div>}
                </div>
                <div className="flex flex-wrap gap-3 items-center">
                  <button
                    type="submit"
                    className="btn-primary px-6 py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? t('common.processing') : t('common.generateWiki')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsConfigModalOpen(true)}
                    className="text-[var(--accent-primary)] text-sm font-medium hover:underline"
                  >
                    {t('common.generateWiki')}前先调整配置
                  </button>
                </div>
              </form>
              <div className="grid sm:grid-cols-2 gap-3 text-xs text-[var(--muted)]">
                <div className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 mt-1.5" />
                  <div>
                    <p className="font-semibold text-[var(--foreground)]">{t('home.quickStart')}</p>
                    <p className="leading-relaxed">{t('home.enterRepoUrl')}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--accent-primary)] mt-1.5" />
                  <div>
                    <p className="font-semibold text-[var(--foreground)]">{t('home.advancedVisualization')}</p>
                    <p className="leading-relaxed">{t('home.diagramDescription')}</p>
                  </div>
                </div>
              </div>

              <ConfigurationModal
                isOpen={isConfigModalOpen}
                onClose={() => setIsConfigModalOpen(false)}
                repositoryInput={repositoryInput}
                selectedLanguage={selectedLanguage}
                setSelectedLanguage={setSelectedLanguage}
                supportedLanguages={supportedLanguages}
                isComprehensiveView={isComprehensiveView}
                setIsComprehensiveView={setIsComprehensiveView}
                provider={provider}
                setProvider={setProvider}
                model={model}
                setModel={setModel}
                isCustomModel={isCustomModel}
                setIsCustomModel={setIsCustomModel}
                customModel={customModel}
                setCustomModel={setCustomModel}
                selectedPlatform={selectedPlatform}
                setSelectedPlatform={setSelectedPlatform}
                accessToken={accessToken}
                setAccessToken={setAccessToken}
                excludedDirs={excludedDirs}
                setExcludedDirs={setExcludedDirs}
                excludedFiles={excludedFiles}
                setExcludedFiles={setExcludedFiles}
                includedDirs={includedDirs}
                setIncludedDirs={setIncludedDirs}
                includedFiles={includedFiles}
                setIncludedFiles={setIncludedFiles}
                onSubmit={handleGenerateWiki}
                isSubmitting={isSubmitting}
                authRequired={authRequired}
                authCode={authCode}
                setAuthCode={setAuthCode}
                isAuthLoading={isAuthLoading}
              />
            </div>
          </div>
        </header>

        <main className="grid lg:grid-cols-3 gap-6 items-start">
          <section className="lg:col-span-2 space-y-4">
            <div className="card-modern p-6 shadow-custom">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{hasProjects ? t('projects.browseExisting') : t('home.welcomeTagline')}</p>
                  <h2 className="text-xl md:text-2xl font-bold text-[var(--foreground)]">
                    {hasProjects ? t('projects.existingProjects') : t('home.welcome')}
                  </h2>
                </div>
                <div className="flex items-center gap-2 text-[var(--muted)] text-xs">
                  <span className="px-2 py-1 rounded-full bg-[var(--accent-secondary)] border border-[var(--border-color)]">GitHub</span>
                  <span className="px-2 py-1 rounded-full bg-[var(--accent-secondary)] border border-[var(--border-color)]">GitLab</span>
                  <span className="px-2 py-1 rounded-full bg-[var(--accent-secondary)] border border-[var(--border-color)]">BitBucket</span>
                </div>
              </div>
              {hasProjects ? (
                <ProcessedProjects
                  showHeader={false}
                  maxItems={6}
                  messages={messages}
                  projects={projects}
                  isLoading={projectsLoading}
                  error={projectsError}
                  className="w-full"
                />
              ) : (
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)]/15 flex items-center justify-center text-[var(--accent-primary)]">
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                          <path d="M12 3l3 3-3 3-3-3 3-3zm0 12l3 3-3 3-3-3 3-3zm9-6l-3 3-3-3 3-3 3 3zM6 9l-3 3 3 3 3-3-3-3z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm text-[var(--muted)]">{t('home.welcomeTagline')}</p>
                        <p className="text-lg font-semibold text-[var(--foreground)]">{t('home.quickStart')}</p>
                      </div>
                    </div>
                    <p className="text-sm text-[var(--foreground)] leading-relaxed">
                      {t('home.description')}
                    </p>
                    <div className="grid sm:grid-cols-2 gap-3">
                      {[
                        { title: '步骤 1', desc: t('home.enterRepoUrl') },
                        { title: '步骤 2', desc: t('home.diagramDescription') },
                        { title: '步骤 3', desc: t('projects.browseExisting') },
                        { title: '步骤 4', desc: t('home.advancedVisualization') },
                      ].map((item) => (
                        <div key={item.title} className="rounded-xl border border-[var(--border-color)] bg-[var(--background)] p-3 text-sm">
                          <p className="text-[var(--accent-primary)] font-semibold">{item.title}</p>
                          <p className="text-[var(--muted)] mt-1 leading-relaxed">{item.desc}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-xl border border-[var(--border-color)] bg-[var(--background)] p-4 space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-500/15 text-emerald-500 flex items-center justify-center">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[var(--foreground)]">{t('home.advancedVisualization')}</p>
                        <p className="text-xs text-[var(--muted)]">{t('home.diagramDescription')}</p>
                      </div>
                    </div>
                    <div className="bg-[var(--card-bg)] rounded-lg p-3 border border-[var(--border-color)]">
                      <p className="text-xs font-semibold text-[var(--foreground)] mb-2">{t('home.flowDiagram')}</p>
                      <Mermaid chart={DEMO_FLOW_CHART} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="space-y-4">
            <div className="bg-[var(--card-bg)] rounded-2xl border border-[var(--border-color)] shadow-custom p-5 space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-[var(--accent-primary)]/15 text-[var(--accent-primary)] flex items-center justify-center">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-[var(--foreground)]">{t('home.quickStart')}</p>
                  <p className="text-xs text-[var(--muted)]">{t('home.enterRepoUrl')}</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-2 text-xs text-[var(--muted)]">
                {[
                  'https://github.com/AsyncFuncAI/deepwiki-open',
                  'https://gitlab.com/gitlab-org/gitlab',
                  'AsyncFuncAI/deepwiki-open',
                  'https://bitbucket.org/atlassian/atlaskit',
                ].map((url) => (
                  <div key={url} className="bg-[var(--background)]/80 p-3 rounded-lg border border-[var(--border-color)] font-mono overflow-x-hidden whitespace-nowrap">
                    {url}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-[var(--card-bg)] rounded-2xl border border-[var(--border-color)] shadow-custom p-5 space-y-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-indigo-500/15 text-indigo-500 flex items-center justify-center">
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-[var(--foreground)]">{t('home.advancedVisualization')}</p>
                  <p className="text-xs text-[var(--muted)]">{t('home.diagramDescription')}</p>
                </div>
              </div>
              <div className="space-y-4">
                <div className="bg-[var(--background)] rounded-lg p-3 border border-[var(--border-color)]">
                  <p className="text-xs font-semibold text-[var(--foreground)] mb-2">{t('home.flowDiagram')}</p>
                  <Mermaid chart={DEMO_FLOW_CHART} />
                </div>
                <div className="bg-[var(--background)] rounded-lg p-3 border border-[var(--border-color)]">
                  <p className="text-xs font-semibold text-[var(--foreground)] mb-2">{t('home.sequenceDiagram')}</p>
                  <Mermaid chart={DEMO_SEQUENCE_CHART} />
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
