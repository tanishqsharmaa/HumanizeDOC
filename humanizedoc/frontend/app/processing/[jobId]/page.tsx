"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ChunkStatus = "PENDING" | "PROCESSING" | "DONE" | "FAILED";
type JobStatus =
  | "UPLOADING"
  | "PARSING"
  | "CHUNKING"
  | "HUMANIZING"
  | "RECONSTRUCTING"
  | "DONE"
  | "FAILED";

interface Chunk {
  index: number;
  status: ChunkStatus;
  word_count: number;
}

interface StatusResponse {
  job_id: string;
  status: JobStatus;
  total_chunks: number;
  completed_chunks: number;
  failed_chunks: number;
  chunks: Chunk[];
  estimated_seconds_remaining: number | null;
}

const STATUS_LABELS: Record<JobStatus, string> = {
  UPLOADING: "Uploading your document...",
  PARSING: "Reading document structure...",
  CHUNKING: "Preparing text sections...",
  HUMANIZING: "Rewriting for human authenticity...",
  RECONSTRUCTING: "Rebuilding your formatted document...",
  DONE: "Complete!",
  FAILED: "Something went wrong",
};

function chunkIcon(status: ChunkStatus) {
  switch (status) {
    case "DONE":
      return "✅";
    case "PROCESSING":
      return (
        <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      );
    case "FAILED":
      return "❌";
    default:
      return <span className="text-gray-400">○</span>;
  }
}

export default function ProcessingPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params?.jobId as string;

  const [data, setData] = useState<StatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) return;

    async function poll() {
      try {
        const res = await fetch(`${API_URL}/api/status/${jobId}`);
        if (!res.ok) throw new Error(`Status check failed (${res.status})`);
        const json: StatusResponse = await res.json();
        setData(json);

        if (json.status === "DONE") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          router.push(`/download/${jobId}`);
        } else if (json.status === "FAILED") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to get status.");
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId, router]);

  const progress =
    data && data.total_chunks > 0
      ? Math.round((data.completed_chunks / data.total_chunks) * 100)
      : 0;

  const isFailed = data?.status === "FAILED";
  const showEta =
    data?.estimated_seconds_remaining != null &&
    data.estimated_seconds_remaining >= 5;

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Brand */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">HumanizeDOC</h1>
        </div>

        {isFailed ? (
          /* Error State */
          <div className="bg-white rounded-xl shadow-md p-8 text-center">
            <p className="text-5xl mb-4">❌</p>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Processing Failed
            </h2>
            <p className="text-gray-500 mb-6">
              We couldn&apos;t process your document. Please try again.
            </p>
            <button
              onClick={() => router.push("/")}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
            >
              ← Try again
            </button>
          </div>
        ) : error ? (
          <div className="bg-white rounded-xl shadow-md p-8 text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={() => router.push("/")}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
            >
              ← Try again
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-md p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">
              Humanizing your document...
            </h2>
            <p className="text-gray-500 mb-6">
              {data ? STATUS_LABELS[data.status] : "Starting..."}
            </p>

            {/* Progress Bar */}
            <div className="mb-2">
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
            <p className="text-sm text-gray-500 mb-2">
              {data
                ? `${data.completed_chunks} of ${data.total_chunks} sections complete`
                : "Loading..."}
            </p>

            {/* ETA */}
            {showEta && (
              <p className="text-sm text-gray-500 mb-4">
                ⏱ ~{data!.estimated_seconds_remaining} seconds remaining
              </p>
            )}

            {/* Chunk List */}
            {data && data.chunks && data.chunks.length > 0 && (
              <div
                className={`mt-4 space-y-2 ${
                  data.chunks.length > 8 ? "max-h-80 overflow-y-auto" : ""
                }`}
              >
                {data.chunks.map((chunk) => (
                  <div
                    key={chunk.index}
                    className="flex items-center gap-3 py-2 px-3 rounded-lg bg-gray-50"
                  >
                    <span className="text-lg flex-shrink-0">
                      {chunkIcon(chunk.status)}
                    </span>
                    <span className="text-sm font-medium text-gray-700 flex-1">
                      Section {chunk.index + 1}
                    </span>
                    <span className="text-xs text-gray-400">
                      ({chunk.word_count} words)
                    </span>
                  </div>
                ))}
              </div>
            )}

            {!data && (
              <div className="flex justify-center mt-6">
                <span className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin-slow" />
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
