"use client";

import { useCallback, useEffect, useState } from "react";
import {
  addAnalysisTicker,
  getLatestAnalysis,
  getTickerAnalysis,
  runAnalysis,
} from "./api";
import type { AssetAnalysis } from "./types";

type AnalysisStatus = "idle" | "running" | "done" | "error";

interface UseAnalysisReturn {
  results: AssetAnalysis[];
  top5: AssetAnalysis[];
  status: AnalysisStatus;
  lastAnalyzedAt: string | null;
  errorMessage: string | null;
  regimeGateActive: boolean;
  vixValue: number | null;
  triggerRun: () => Promise<void>;
  addTicker: (ticker: string) => Promise<void>;
  getArgument: (ticker: string) => Promise<string | null>;
}

export function useAnalysis(): UseAnalysisReturn {
  const [results, setResults] = useState<AssetAnalysis[]>([]);
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [regimeGateActive, setRegimeGateActive] = useState<boolean>(false);
  const [vixValue, setVixValue] = useState<number | null>(null);

  const top5 = results.filter((a) => a.rank !== null).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

  // Load cached results on mount
  useEffect(() => {
    getLatestAnalysis()
      .then(({ results: rows }) => {
        if (rows.length > 0) {
          setResults(rows);
          setLastAnalyzedAt(rows[0].analyzed_at ?? null);
          setStatus("done");
        }
      })
      .catch(() => {
        // No cached results yet — stay idle
      });
  }, []);

  const triggerRun = useCallback(async () => {
    setStatus("running");
    setErrorMessage(null);
    try {
      const data = await runAnalysis();
      setResults(data.assets);
      setLastAnalyzedAt(data.analyzed_at);
      // Clear the banner when the gate is inactive; show it (with VIX) when active.
      setRegimeGateActive(data.regime_gate_active === true);
      setVixValue(data.vix_value ?? null);
      setStatus("done");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Analysis failed");
    }
  }, []);

  const addTicker = useCallback(async (ticker: string) => {
    await addAnalysisTicker(ticker.toUpperCase());
  }, []);

  const getArgument = useCallback(async (ticker: string): Promise<string | null> => {
    try {
      const data = await getTickerAnalysis(ticker);
      return data.argument;
    } catch {
      return null;
    }
  }, []);

  return { results, top5, status, lastAnalyzedAt, errorMessage, regimeGateActive, vixValue, triggerRun, addTicker, getArgument };
}
