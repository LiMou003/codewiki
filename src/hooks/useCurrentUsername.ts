import { useState, useEffect } from 'react';

/**
 * Returns the username of the currently logged-in user by reading from
 * localStorage.  Returns an empty string when no user is signed in.
 */
export function useCurrentUsername(): string {
  const [username, setUsername] = useState<string>(() => {
    if (typeof window === 'undefined') {
      return '';
    }

    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed.username || '';
      }
    } catch {
      // ignore – treat as unauthenticated
    }

    return '';
  });

  useEffect(() => {
    const syncUsernameFromStorage = () => {
      try {
        const stored = localStorage.getItem('cw_user');
        if (stored) {
          const parsed = JSON.parse(stored);
          setUsername(parsed.username || '');
          return;
        }
      } catch {
        // ignore – treat as unauthenticated
      }

      setUsername('');
    };

    syncUsernameFromStorage();
    window.addEventListener('storage', syncUsernameFromStorage);

    return () => {
      window.removeEventListener('storage', syncUsernameFromStorage);
    };
  }, []);

  return username;
}
