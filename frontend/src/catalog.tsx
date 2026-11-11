import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getAmazonSession, getCatalog, getInfo, getLiveOrders, getOpportunities, getStats } from "./api";
import type { AmazonSession, AppInfo, Catalog, LiveOrders, Opportunities, Stats } from "./types";

export type CatalogState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "ready";
      catalog: Catalog;
      info: AppInfo;
      stats: Stats;
      session: AmazonSession;
      live: LiveOrders;
      opportunities: Opportunities;
    };

const CatalogContext = createContext<CatalogState>({ status: "loading" });

export function useCatalog(): CatalogState {
  return useContext(CatalogContext);
}

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CatalogState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCatalog(), getInfo(), getStats(), getAmazonSession(), getLiveOrders(), getOpportunities()])
      .then(([catalog, info, stats, session, live, opportunities]) => {
        if (!cancelled) {
          setState({ status: "ready", catalog, info, stats, session, live, opportunities });
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
