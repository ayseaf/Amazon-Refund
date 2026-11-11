import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getCatalog, getInfo, getStats } from "./api";
import type { AppInfo, Catalog, Stats } from "./types";

export type CatalogState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; catalog: Catalog; info: AppInfo; stats: Stats };

const CatalogContext = createContext<CatalogState>({ status: "loading" });

export function useCatalog(): CatalogState {
  return useContext(CatalogContext);
}

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CatalogState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCatalog(), getInfo(), getStats()])
      .then(([catalog, info, stats]) => {
        if (!cancelled) {
          setState({ status: "ready", catalog, info, stats });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "The local API did not respond.";
          setState({ status: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <CatalogContext.Provider value={state}>{children}</CatalogContext.Provider>;
}
