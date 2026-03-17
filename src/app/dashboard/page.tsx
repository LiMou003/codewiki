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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <nav className="sticky top-0 z-50 bg-[var(--background)] border-b border-[var(--border-color)] shadow-custom">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14">
          <Link href="/" className="flex items-center gap-2 font-bold text-lg text-[var(--accent-primary)]">
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
            </svg>
            CodeWiki
          </Link>
          <div className="flex items-center gap-4">
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

      <div className="flex-1 p-4 md:p-8 flex flex-col max-w-6xl mx-auto w-full">
        <header className="mb-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-[var(--card-bg)] rounded-lg shadow-custom border border-[var(--border-color)] p-4">
            <div className="flex items-center">
              <div className="bg-[var(--accent-primary)] p-2 rounded-lg mr-3">
                <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                </svg>
              </div>
              <div className="mr-6">
                <h1 className="text-xl md:text-2xl font-bold text-[var(--accent-primary)]">控制台</h1>
                <p className="text-xs text-[var(--muted)]">为任意仓库生成 Wiki</p>
              </div>
            </div>

            <form onSubmit={handleFormSubmit} className="flex flex-col gap-3 w-full max-w-3xl">
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={repositoryInput}
                    onChange={handleRepositoryInputChange}
                    placeholder={t('form.repoPlaceholder') || 'owner/repo, GitHub/GitLab/BitBucket URL, or local folder path'}
                    className="input-modern block w-full pl-10 pr-3 py-2.5 text-[var(--foreground)] bg-[var(--background)] focus:outline-none"
                  />
                  {error && (
                    <div className="text-red-500 text-xs mt-1">{error}</div>
                  )}
                </div>
                <button
                  type="submit"
                  className="btn-primary px-6 py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? t('common.processing') : t('common.generateWiki')}
                </button>
              </div>
            </form>

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
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="min-h-full flex flex-col items-center p-8 pt-10 bg-[var(--card-bg)] rounded-lg shadow-custom card-modern">
            {!projectsLoading && projects.length > 0 ? (
              <div className="w-full">
                <div className="flex flex-col items-center w-full max-w-2xl mb-8 mx-auto">
                  <div className="flex flex-col sm:flex-row items-center mb-6 gap-4">
                    <div className="relative">
                      <div className="absolute -inset-1 bg-[var(--accent-primary)]/20 rounded-full blur-md"></div>
                      <svg className="w-12 h-12 text-[var(--accent-primary)] relative z-10" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                      </svg>
                    </div>
                    <div className="text-center sm:text-left">
                      <h2 className="text-2xl font-bold text-[var(--foreground)] mb-1">{t('projects.existingProjects')}</h2>
                      <p className="text-[var(--accent-primary)] text-sm max-w-md">{t('projects.browseExisting')}</p>
                    </div>
                  </div>
                </div>
                <ProcessedProjects
                  showHeader={false}
                  maxItems={6}
                  messages={messages}
                  projects={projects}
                  isLoading={projectsLoading}
                  error={projectsError}
                  className="w-full"
                />
              </div>
            ) : (
              <>
                <div className="flex flex-col items-center w-full max-w-2xl mb-8">
                  <div className="flex flex-col sm:flex-row items-center mb-6 gap-4">
                    <div className="relative">
                      <div className="absolute -inset-1 bg-[var(--accent-primary)]/20 rounded-full blur-md"></div>
                      <svg className="w-12 h-12 text-[var(--accent-primary)] relative z-10" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
                      </svg>
                    </div>
                    <div className="text-center sm:text-left">
                      <h2 className="text-2xl font-bold text-[var(--foreground)] mb-1">{t('home.welcome')}</h2>
                      <p className="text-[var(--accent-primary)] text-sm max-w-md">{t('home.welcomeTagline')}</p>
                    </div>
                  </div>
                  <p className="text-[var(--foreground)] text-center mb-8 text-lg leading-relaxed">
                    {t('home.description')}
                  </p>
                </div>

                <div className="w-full max-w-2xl mb-10 bg-[var(--accent-primary)]/5 border border-[var(--accent-primary)]/20 rounded-lg p-5">
                  <h3 className="text-sm font-semibold text-[var(--accent-primary)] mb-3 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {t('home.quickStart')}
                  </h3>
                  <p className="text-sm text-[var(--foreground)] mb-3">{t('home.enterRepoUrl')}</p>
                  <div className="grid grid-cols-1 gap-3 text-xs text-[var(--muted)]">
                    {[
                      'https://github.com/AsyncFuncAI/deepwiki-open',
                      'https://gitlab.com/gitlab-org/gitlab',
                      'AsyncFuncAI/deepwiki-open',
                      'https://bitbucket.org/atlassian/atlaskit',
                    ].map((url) => (
                      <div key={url} className="bg-[var(--background)]/70 p-3 rounded border border-[var(--border-color)] font-mono overflow-x-hidden whitespace-nowrap">
                        {url}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="w-full max-w-2xl mb-8 bg-[var(--background)]/70 rounded-lg p-6 border border-[var(--border-color)]">
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-[var(--accent-primary)] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    <h3 className="text-base font-semibold text-[var(--foreground)]">{t('home.advancedVisualization')}</h3>
                  </div>
                  <p className="text-sm text-[var(--foreground)] mb-5 leading-relaxed">{t('home.diagramDescription')}</p>
                  <div className="grid grid-cols-1 gap-6">
                    <div className="bg-[var(--card-bg)] p-4 rounded-lg border border-[var(--border-color)] shadow-custom">
                      <h4 className="text-sm font-medium text-[var(--foreground)] mb-3">{t('home.flowDiagram')}</h4>
                      <Mermaid chart={DEMO_FLOW_CHART} />
                    </div>
                    <div className="bg-[var(--card-bg)] p-4 rounded-lg border border-[var(--border-color)] shadow-custom">
                      <h4 className="text-sm font-medium text-[var(--foreground)] mb-3">{t('home.sequenceDiagram')}</h4>
                      <Mermaid chart={DEMO_SEQUENCE_CHART} />
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </main>

        {/* <footer className="mt-8">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-[var(--card-bg)] rounded-lg p-4 border border-[var(--border-color)] shadow-custom">
            <p className="text-[var(--muted)] text-sm">{t('footer.copyright')}</p>
            <div className="flex items-center gap-6">
              <div className="flex items-center space-x-5">
                <a href="https://github.com/AsyncFuncAI/deepwiki-open" target="_blank" rel="noopener noreferrer" className="text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors">
                  <FaGithub className="text-xl" />
                </a>
                <a href="https://buymeacoffee.com/sheing" target="_blank" rel="noopener noreferrer" className="text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors">
                  <FaCoffee className="text-xl" />
                </a>
                <a href="https://x.com/sashimikun_void" target="_blank" rel="noopener noreferrer" className="text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors">
                  <FaTwitter className="text-xl" />
                </a>
              </div>
              <ThemeToggle />
            </div>
          </div>
        </footer> */}
      </div>
    </div>
  );
}
