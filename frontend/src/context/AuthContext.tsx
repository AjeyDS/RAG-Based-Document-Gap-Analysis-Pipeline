import React, { createContext, useContext, useState, useEffect } from "react";
import { login as apiLogin, logout as apiLogout, getMe, setAuthToken } from "../api/client";

export type UserType = {
  user_id: string;
  username: string;
  role: string;
  token: string;
};

type AuthContextType = {
  user: UserType | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserType | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Attempt to restore session
    const checkAuth = async () => {
      try {
        const me = await getMe();
        if (me) {
          // If we had a token mechanism spanning reloads, we'd hydrate everything here.
          // Since it's purely in memory, on hard reset getMe is null naturally.
        }
      } catch {
      } finally {
        setIsLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (username: string, pass: string) => {
    const data = await apiLogin(username, pass);
    const authedUser = {
      user_id: data.user_id,
      username: data.username,
      role: data.role,
      token: data.token,
    };
    setAuthToken(data.token);
    setUser(authedUser);
  };

  const logout = async () => {
    await apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
