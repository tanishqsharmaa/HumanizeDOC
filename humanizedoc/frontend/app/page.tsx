"use client";

import { useState, useRef, DragEvent, ChangeEvent } from "react";
import { useRouter } from "next/navigation";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Style = "academic" | "essay" | "report";

const STYLES: { value: Style; label: string }[] = [
  { value: "academic", label: "Academic" },
  { value: "essay", label: "Essay" },
  { value: "report", label: "Report" },
];

const MAX_FILE_SIZE = 15 * 1024 * 1024; // 15 MB

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [style, setStyle] = useState<Style>("academic");
  const [dragOver, setDragOver] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function validateFile(f: File): string | null {
    if (!f.name.endsWith(".docx")) return "Only .docx files are supported.";
    if (f.size > MAX_FILE_SIZE) return "File must be smaller than 15 MB.";
    return null;
  }

  function handleFile(f: File) {
    const err = validateFile(f);
    setFileError(err);
    setFile(err ? null : f);
    setSubmitError(null);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0];
    if (chosen) handleFile(chosen);
  }

  async function handleSubmit() {
    if (!file || uploading) return;
    setUploading(true);
    setSubmitError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(
        `${API_URL}/api/upload?style=${style}`,
        { method: "POST", body: formData }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Upload failed (${res.status})`);
      }
      const data = await res.json();
      router.push(`/processing/${data.job_id}`);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  }

  const dropZoneBorder = fileError
    ? "border-red-500"
    : dragOver
    ? "border-blue-500 bg-blue-50"
    : file
    ? "border-emerald-500"
    : "border-gray-300 hover:border-blue-500";

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Brand */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-600">HumanizeDOC</h1>
          <p className="text-gray-500 mt-2">
            Make your AI-written documents pass Turnitin
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-md p-8">
          {/* Drop Zone */}
          <div
            className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center cursor-pointer transition-colors ${dropZoneBorder}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".docx"
              className="hidden"
              onChange={handleChange}
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <span className="text-4xl">✅</span>
                <p className="font-medium text-gray-900">{file.name}</p>
                <p className="text-sm text-gray-500">{formatBytes(file.size)}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-center">
                <span className="text-5xl">📄</span>
                <p className="text-gray-600 font-medium">Drop your .docx here</p>
                <p className="text-sm text-gray-400">or click to browse</p>
              </div>
            )}
          </div>
          {fileError && (
            <p className="mt-2 text-sm text-red-600">{fileError}</p>
          )}

          {/* Style Selector */}
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Writing Style
            </label>
            <div className="flex gap-3">
              {STYLES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setStyle(s.value)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors border ${
                    style === s.value
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white border-gray-200 text-gray-500 hover:border-blue-400"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!file || uploading}
            className={`mt-6 w-full h-12 rounded-lg font-semibold text-white transition-colors flex items-center justify-center gap-2 ${
              !file || uploading
                ? "bg-gray-300 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 shadow-md"
            }`}
          >
            {uploading ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Uploading...
              </>
            ) : (
              "✨ Humanize My Document"
            )}
          </button>

          {submitError && (
            <p className="mt-2 text-sm text-red-600 text-center">{submitError}</p>
          )}

          {/* Trust Badges */}
          <div className="mt-6 grid grid-cols-2 gap-2">
            {[
              "✓ Formatting preserved",
              "✓ Headings untouched",
              "✓ References untouched",
              "✓ No account needed",
            ].map((badge) => (
              <p key={badge} className="text-xs text-gray-500 text-center py-1">
                {badge}
              </p>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
