"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  addAnalysisTicker,
  getLatestAnalysis,
  getLatestPartial,
  getRunStatus,
  getTickerAnalysis,
  RunInProgressError,
  startAnalysisRun,
} from "./api";
import type { AssetAnalysis, RunStatus } from "./types";

type AnalysisStatus = "idle" | "running" | "done" | "error";

const POLL_INTERVAL_MS = 3000;

interface UseAnalysisReturn {
  results: AssetAnalysis[];
  top5: AssetAnalysis[];
  status: AnalysisStatus;
  runStatus: RunStatus | null;
  previewResults: AssetAnalysis[];
  lastAnalyzedAt: string | null;
  errorMessage: string | null;
  regimeGateActive: boolean;
  vixValue: number | null;
  triggerRun: () => Promise<void>;
  loadPreview: () => Promise<void>;
  addTicker: (ticker: string) => Promise<void>;
  getArgument: (ticker: string) => Promise<string | null>;
}

export function useAnalysis(): UseAnalysisReturn {
  const [results, setResults] = useState<AssetAnalysis[]>([]);
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [previewResults, setPreviewResults] = useState<AssetAnalysis[]>([]);
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [regimeGateActive, setRegimeGateActive] = useState<boolean>(false);
  const [vixValue, setVixValue] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const top5 = results.filter((a) => a.rank !== null).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

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
    return stopPolling;
  }, [stopPolling]);

  const finishRun = useCallback(async () => {
    try {
      const { results: rows } = await getLatestAnalysis();
      setResults(rows);
      setLastAnalyzedAt(rows[0]?.analyzed_at ?? null);
    } catch {
      // Ignore — keep whatever results we already have
    }
    setStatus("done");
  }, []);

  const poll = useCallback(
    async (runId: string) => {
      try {
        const s = await getRunStatus(runId);
        setRunStatus(s);
        if (s.stage === "complete") {
          stopPolling();
          await finishRun();
        } else if (s.stage === "failed") {
          stopPolling();
          setStatus("error");
          setErrorMessage(
            s.errors_so_far.map((e) => e.error_message).join("; ") || "Analysis failed"
          );
        }
      } catch {
        // 404 (run expired) or transient error — stop polling
        stopPolling();
        setStatus("error");
        setErrorMessage("Run expired or unavailable — re-trigger if needed");
      }
    },
    [stopPolling, finishRun]
  );

  const triggerRun = useCallback(async () => {
    setStatus("running");
    setErrorMessage(null);
    setRunStatus(null);
    setPreviewResults([]);
    try {
      const { run_id } = await startAnalysisRun([]);
      stopPolling();
      void poll(run_id);
      pollRef.current = setInterval(() => void poll(run_id), POLL_INTERVAL_MS);
    } catch (err: unknown) {
      setStatus("error");
      if (err instanceof RunInProgressError) {
        setErrorMessage("A run is already in progress");
      } else {
        setErrorMessage(err instanceof Error ? err.message : "Analysis failed");
      }
    }
  }, [stopPolling, poll]);

  const loadPreview = useCallback(async () => {
    try {
      const { results: rows } = await getLatestPartial();
      setPreviewResults(rows);
    } catch {
      setPreviewResults([]);
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

  return {
    results,
    top5,
    status,
    runStatus,
    previewResults,
    lastAnalyzedAt,
    errorMessage,
    regimeGateActive,
    vixValue,
    triggerRun,
    loadPreview,
    addTicker,
    getArgument,
  };
}
