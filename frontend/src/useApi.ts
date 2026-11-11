import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const hasData = useRef(false);
  const reload = useCallback(() => setTick((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    if (!hasData.current) {
      setLoading(true);
    }
    api<T>(path).then(
      (body) => {
        if (!cancelled) {
          hasData.current = true;
          setData(body);
          setError(null);
          setLoading(false);
        }
      },
      (reason: unknown) => {
        if (!cancelled) {
          if (!hasData.current) {
            setData(null);
          }
          setError(reason instanceof Error ? reason.message : "The local service did not respond.");
          setLoading(false);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [path, tick]);

  return { data, error, loading, reload };
}
