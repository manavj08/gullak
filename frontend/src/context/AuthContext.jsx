import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { getTokens, setTokens } from '../api/client';
import { fetchMe, loginUser, logoutUser, registerUser } from '../api/endpoints';

const AuthContext = createContext(null);

// Tracks whether this specific page load has already been unlocked.
// A hard refresh creates a brand-new module instance, so this resets to false
// every time the app boots — that's what forces MPIN re-entry on every open/reload.
let unlockedThisLoad = false;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const initialCheckDone = useRef(false);

  const loadUser = useCallback(async () => {
    const tokens = getTokens();
    if (!tokens?.access) {
      setUser(null);
      setLoading(false);
      return null;
    }
    try {
      const { data } = await fetchMe();
      setUser(data);
      return data;
    } catch {
      setTokens(null);
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const loadedUser = await loadUser();
      // On first mount (app open/reload): if the user has an MPIN and hasn't
      // unlocked yet this load, require MPIN before showing protected pages.
      if (!initialCheckDone.current) {
        initialCheckDone.current = true;
        if (loadedUser?.has_mpin && !unlockedThisLoad) {
          setLocked(true);
        }
      }
    })();
    const onLogout = () => {
      setUser(null);
      setTokens(null);
    };
    window.addEventListener('gullak:logout', onLogout);
    return () => window.removeEventListener('gullak:logout', onLogout);
  }, [loadUser]);

  const login = async (email, password) => {
    const { data } = await loginUser({ email, password });
    setTokens({ access: data.access, refresh: data.refresh });
    await loadUser();
    unlockedThisLoad = true;
    setLocked(false);
  };

  const register = async (payload) => {
    await registerUser(payload);
    await login(payload.email, payload.password);
  };

  const logout = async () => {
    const tokens = getTokens();
    try {
      if (tokens?.refresh) await logoutUser(tokens.refresh);
    } catch {
      /* ignore — logging out locally regardless */
    }
    setTokens(null);
    setUser(null);
    unlockedThisLoad = false;
    setLocked(false);
  };

  const lock = () => {
    unlockedThisLoad = false;
    setLocked(true);
  };

  const unlock = () => {
    unlockedThisLoad = true;
    setLocked(false);
  };

  return (
    <AuthContext.Provider
      value={{ user, setUser, loading, login, register, logout, locked, lock, unlock, refreshUser: loadUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
