import { createContext, useContext, useMemo, useState, useEffect } from "react";
import { STRINGS } from "./strings";

const LangContext = createContext(null);

const STORAGE_KEY = "lattice.lang";

export function LangProvider({ children }) {
  const [lang, setLang] = useState(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    return stored === "en" || stored === "it" ? stored : "it";
  });

  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem(STORAGE_KEY, lang);
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t: STRINGS[lang] }), [lang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error("useLang must be used inside LangProvider");
  return ctx;
}
