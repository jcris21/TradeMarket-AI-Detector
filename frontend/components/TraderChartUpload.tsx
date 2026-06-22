"use client";

import { useRef, useState } from "react";
import type { ExtractedLevel, LevelConfirmResult } from "@/lib/types";
import { enrichTraderChart, confirmLevels } from "@/lib/api";

const MAX_SIZE_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = ["image/png", "image/jpeg"];

type Phase = "upload" | "extracting" | "review" | "confirming" | "result";

interface TraderChartUploadProps {
  ticker: string;
  onConfirmed: (result: LevelConfirmResult) => void;
}

function parseHttpStatus(err: unknown): number | null {
  if (err instanceof Error) {
    const m = err.message.match(/^(\d{3}):/);
    if (m) return parseInt(m[1], 10);
  }
  return null;
}

function parseErrorDetail(err: unknown, fallback: string): string {
  if (err instanceof Error) {
    const colonIdx = err.message.indexOf(": ");
    if (colonIdx !== -1) {
      const body = err.message.slice(colonIdx + 2);
      try {
        const parsed = JSON.parse(body) as { detail?: string; message?: string };
        return parsed.detail ?? parsed.message ?? body;
      } catch {
        return body || fallback;
      }
    }
    return err.message || fallback;
  }
  return fallback;
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-3.5 w-3.5 inline-block mr-1.5"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}

export default function TraderChartUpload({ ticker, onConfirmed }: TraderChartUploadProps) {
  const [phase, setPhase] = useState<Phase>("upload");
  const [error, setError] = useState<string | null>(null);
  const [enrichmentId, setEnrichmentId] = useState<string | null>(null);
  const [levels, setLevels] = useState<ExtractedLevel[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [result, setResult] = useState<LevelConfirmResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setPhase("upload");
    setError(null);
    setEnrichmentId(null);
    setLevels([]);
    setSelectedIndices([]);
    setResult(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function handleFileClick() {
    setError(null);
    fileInputRef.current?.click();
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ALLOWED_TYPES.includes(file.type)) {
      setError("Only PNG and JPEG images are supported");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError("File must be under 10 MB");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const b64 = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        resolve(dataUrl.split(",")[1]);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });

    setPhase("extracting");
    setError(null);

    try {
      const response = await enrichTraderChart(ticker, b64);
      setEnrichmentId(response.enrichment_id);
      if (response.extracted_levels.length === 0) {
        setPhase("upload");
        setError("No levels detected in this chart. Try a clearer image.");
      } else {
        setLevels(response.extracted_levels);
        setSelectedIndices([]);
        setPhase("review");
      }
    } catch (err: unknown) {
      const status = parseHttpStatus(err);
      if (status === 400) {
        setError(parseErrorDetail(err, "Invalid image"));
      } else {
        setError("Could not reach server. Please try again.");
      }
      setPhase("upload");
    }
  }

  function toggleIndex(idx: number) {
    setSelectedIndices((prev) => {
      if (prev.includes(idx)) return prev.filter((i) => i !== idx);
      if (prev.length >= 2) return prev;
      return [...prev, idx];
    });
  }

  async function handleConfirm() {
    if (!enrichmentId || selectedIndices.length === 0) return;
    setPhase("confirming");
    setError(null);

    try {
      const res = await confirmLevels(ticker, enrichmentId, selectedIndices);
      setResult(res);
      onConfirmed(res);
      setPhase("result");
    } catch (err: unknown) {
      const status = parseHttpStatus(err);
      if (status === 404) {
        setError("Session expired. Please re-upload your chart.");
      } else if (status === 422) {
        setError("Invalid level selection. Please re-upload and try again.");
      } else {
        setError("Could not reach server. Please try again.");
      }
      setPhase("review");
    }
  }

  // Result card
  if (phase === "result" && result !== null) {
    const deltaSign = result.enrichment_delta >= 0 ? "+" : "";
    return (
      <div className="mt-2 px-3 py-2 rounded border border-amber-700 bg-amber-950/30 text-xs font-mono flex flex-col gap-1.5">
        <div className="flex items-center gap-3">
          <span className="text-text-muted uppercase tracking-wide text-[10px]">Enrichment Result</span>
          <span className="text-amber-400 font-bold" style={{ textShadow: "0 0 6px rgba(251,191,36,0.5)" }}>
            {deltaSign}{result.enrichment_delta.toFixed(1)} pts
          </span>
          <span className="text-white">Score: {result.score_enriched.toFixed(1)}</span>
          <span className="text-text-muted">{result.custom_levels_applied} level{result.custom_levels_applied !== 1 ? "s" : ""} applied</span>
        </div>
        <button
          onClick={reset}
          className="self-start text-[10px] text-text-muted hover:text-white underline underline-offset-2"
        >
          Re-upload
        </button>
      </div>
    );
  }

  // Level review / confirming
  if (phase === "review" || phase === "confirming") {
    const isConfirming = phase === "confirming";
    return (
      <div className="mt-2 px-3 py-2 rounded border border-border bg-bg-hover text-xs font-mono flex flex-col gap-2">
        <span className="text-text-muted uppercase tracking-wide text-[10px]">Review Extracted Levels</span>

        {error && (
          <p className="text-red-400 text-[11px]">{error}</p>
        )}

        <ul className="flex flex-col gap-1">
          {levels.map((level, idx) => {
            const isSelected = selectedIndices.includes(idx);
            const isDisabled = isConfirming || (!isSelected && selectedIndices.length >= 2);
            return (
              <li key={idx} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={isSelected}
                  disabled={isDisabled}
                  onChange={() => toggleIndex(idx)}
                  className="accent-amber-400 cursor-pointer disabled:cursor-not-allowed"
                  data-testid={`level-checkbox-${idx}`}
                />
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    level.type === "support"
                      ? "bg-green-900 text-green-400 border border-green-700"
                      : "bg-red-900 text-red-400 border border-red-700"
                  }`}
                >
                  {level.type === "support" ? "Support" : "Resistance"}
                </span>
                <span className="text-white tabular-nums">${level.price.toFixed(2)}</span>
                <span className="text-text-muted tabular-nums">{Math.round(level.confidence * 100)}%</span>
                <div className="flex-1 h-1 bg-gray-700 rounded overflow-hidden max-w-16">
                  <div
                    className="h-full bg-amber-400/60 rounded"
                    style={{ width: `${level.confidence * 100}%` }}
                  />
                </div>
              </li>
            );
          })}
        </ul>

        <div className="flex items-center gap-2 mt-0.5">
          <button
            onClick={() => void handleConfirm()}
            disabled={selectedIndices.length === 0 || isConfirming}
            className="px-2 py-0.5 rounded text-xs font-mono border border-amber-700 text-amber-300 bg-amber-900/40 hover:bg-amber-900/70 disabled:opacity-40 disabled:cursor-not-allowed flex items-center"
            data-testid="confirm-levels-btn"
          >
            {isConfirming && <Spinner />}
            {isConfirming ? "Confirming…" : "Confirm Levels"}
          </button>
          <button
            onClick={reset}
            disabled={isConfirming}
            className="text-[10px] text-text-muted hover:text-white underline underline-offset-2 disabled:opacity-40"
          >
            Re-upload
          </button>
        </div>
      </div>
    );
  }

  // Upload / extracting
  return (
    <div className="mt-2 flex flex-col gap-1">
      {error && (
        <p className="text-red-400 text-[11px] font-mono px-1" data-testid="upload-error">
          {error}
        </p>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => void handleFileChange(e)}
        data-testid="chart-file-input"
      />
      <button
        onClick={handleFileClick}
        disabled={phase === "extracting"}
        className="self-start px-2 py-0.5 rounded text-xs font-mono border border-border text-text-muted hover:border-accent-yellow hover:text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
        data-testid="upload-chart-btn"
      >
        {phase === "extracting" ? (
          <>
            <Spinner />
            Extracting levels…
          </>
        ) : (
          "Upload Chart"
        )}
      </button>
    </div>
  );
}
