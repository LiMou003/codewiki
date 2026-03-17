import { useState, useEffect } from 'react';
import { useCurrentUsername } from './useCurrentUsername';

interface ProcessedProject {
  id: string;
  owner: string;
  repo: string;
  name: string;
  repo_type: string;
  submittedAt: number;
  language: string;
}

export function useProcessedProjects(enabled: boolean = true) {
  const [projects, setProjects] = useState<ProcessedProject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const username = useCurrentUsername();

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }

    const fetchProjects = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const url = username
          ? `/api/wiki/projects?username=${encodeURIComponent(username)}`
          : '/api/wiki/projects';

        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch projects: ${response.statusText}`);
        }
        const data = await response.json();
        if (data.error) {
          throw new Error(data.error);
        }
        setProjects(data as ProcessedProject[]);
      } catch (e: unknown) {
        console.error("Failed to load projects from API:", e);
        const message = e instanceof Error ? e.message : "An unknown error occurred.";
        setError(message);
        setProjects([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjects();
  }, [username, enabled]);

  return { projects, isLoading, error };
}
