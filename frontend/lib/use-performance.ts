"use client";

import { useEffect, useRef, useState } from "react";
import { getPerformanceSummary } from "./api";
import type { PerformanceSummary } from "./types";

type AnalysisStatus = "idle" | "running" | "done" | "error";

interface UsePerformanceReturn {
  performance: PerformanceSummary | null;
  isLoading: boolean;
}

export function usePerformance(status: AnalysisStatus): UsePerformanceReturn {
  const [performance, setPerformance] = useState<PerformanceSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const prevStatus = useRef<AnalysisStatus>(status);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    getPerformanceSummary()
      .then((data) => {
        if (!cancelled) {
          setPerformance(data);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (prevStatus.current === "running" && status === "done") {
      let cancelled = false;
      getPerformanceSummary()
        .then((data) => {
          if (!cancelled) setPerformance(data);
        })
        .catch(() => {});
      return () => {
        cancelled = true;
      };
    }
    prevStatus.current = status;
  }, [status]);

  return { performance, isLoading };
}
