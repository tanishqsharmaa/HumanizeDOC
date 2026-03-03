"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DownloadResponse {
  download_url: string;
  original_word_count: number;
  humanized_word_count: number;
  processing_time_seconds: number;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

export default function DownloadPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params?.jobId as string;

  const [data, setData] = useState<DownloadResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!jobId) return;

    async function fetchDownload() {
      try {
        const res = await fetch(`${API_URL}/api/download/${jobId}`);
        if (!res.ok) {
          router.push("/");
          return;
        }
        const json: DownloadResponse = await res.json();
        setData(json);
      } catch {
        router.push("/");
      } finally {
        setLoading(false);
      }
    }

    fetchDownload();
  }, [jobId, router]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <span className="inline-block w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin-slow" />
      </main>
    );
  }

  if (!data) return null;

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Brand */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">HumanizeDOC</h1>
        </div>

        <div className="bg-white rounded-xl shadow-md p-8">
          {/* Success Icon */}
          <div className="flex flex-col items-center mb-6">
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mb-3">
              <svg
                className="w-8 h-8 text-emerald-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900">
              Your document is ready.
            </h2>
          </div>

          {/* File Card */}
          <div className="border border-gray-200 border-l-4 border-l-emerald-500 bg-white rounded-lg p-4 mb-6">
            <div className="flex items-center gap-3">
              <span className="text-2xl">📄</span>
              <div>
                <p className="font-medium text-gray-900">
                  document_humanized.docx
                </p>
                <p className="text-sm text-gray-500">
                  {data.humanized_word_count} words • processed in{" "}
                  {formatTime(data.processing_time_seconds)}
                </p>
              </div>
            </div>
          </div>

          {/* Download Button */}
          <a
            href={data.download_url}
            download
            className="w-full h-14 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold text-lg flex items-center justify-center gap-2 transition-colors shadow-md"
          >
            ⬇️ Download Humanized DOCX
          </a>

          {/* Stats Row */}
          <div className="grid grid-cols-3 gap-3 mt-6">
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Original</p>
              <p className="font-semibold text-gray-900">
                {data.original_word_count}
              </p>
              <p className="text-xs text-gray-400">words</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Humanized</p>
              <p className="font-semibold text-gray-900">
                {data.humanized_word_count}
              </p>
              <p className="text-xs text-gray-400">words</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Time</p>
              <p className="font-semibold text-gray-900">
                {data.processing_time_seconds}s
              </p>
              <p className="text-xs text-gray-400">total</p>
            </div>
          </div>

          {/* Review Checklist */}
          <div className="mt-6 border-l-4 border-amber-500 bg-amber-50 rounded-lg p-4">
            <p className="font-semibold text-amber-800 mb-3">
              ⚠️ Before you submit:
            </p>
            <ul className="space-y-2">
              {[
                "Read through your document once",
                "Check your argument still flows naturally",
                "Verify your data and statistics are unchanged",
              ].map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm text-amber-700">
                  <span className="mt-0.5">□</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Secondary Actions */}
          <div className="mt-6 flex flex-col items-center gap-2">
            <button
              onClick={() => router.push("/")}
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              🔄 Humanize another document
            </button>
            <p className="text-xs text-gray-400">
              🗑 File deleted automatically in 60 minutes
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
