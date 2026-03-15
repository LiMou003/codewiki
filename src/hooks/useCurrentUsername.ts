import { useState, useEffect } from 'react';

/**
 * Returns the username of the currently logged-in user by reading from
 * localStorage.  Returns an empty string when no user is signed in.
 */
export function useCurrentUsername(): string {
  const [username, setUsername] = useState<string>('');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) {
        const parsed = JSON.parse(stored);
        setUsername(parsed.username || '');
      }
    } catch {
      // ignore – treat as unauthenticated
    }
  }, []);

  return username;
}
