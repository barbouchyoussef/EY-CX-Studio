import { useEffect, useState } from "react";
import { authFetch } from "../../lib/api";


type MessageItem = {
  id: number;
  role: "assistant" | "user";
  content: string;
  created_at: string;
};

type Props = {
  assessmentId: number;
  onBack: () => void;
};

export default function AdminAssessmentDetail({ assessmentId, onBack }: Props) {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [roleFilter, setRoleFilter] = useState<"all" | "assistant" | "user">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    authFetch(`/assessments/${assessmentId}/messages?limit=1000&offset=0`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load assessment messages");
        return res.json();
      })
      .then((payload) => {
        if (!mounted) return;
        setMessages(payload.items ?? []);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load messages");
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [assessmentId]);

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Assessment #{assessmentId} history</h1>
              <p className="text-sm text-slate-500">Question/answer timeline</p>
            </div>
            <button onClick={onBack} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Back to admin
            </button>
          </div>
        </div>

        {loading ? <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">Loading...</div> : null}
        {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div> : null}

        {!loading && !error ? (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-4 flex items-center gap-2">
              <span className="text-sm text-slate-600">View:</span>
              <button
                onClick={() => setRoleFilter("all")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                  roleFilter === "all" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setRoleFilter("assistant")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                  roleFilter === "assistant" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                Assistant only
              </button>
              <button
                onClick={() => setRoleFilter("user")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                  roleFilter === "user" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                User only
              </button>
            </div>
            <div className="space-y-4">
              {messages
                .filter((msg) => roleFilter === "all" || msg.role === roleFilter)
                .map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                      msg.role === "user"
                        ? "rounded-tr-none bg-slate-900 text-white"
                        : "rounded-tl-none border border-slate-200 bg-slate-50 text-slate-800"
                    }`}
                  >
                    <p>{msg.content}</p>
                    <p className={`mt-2 text-[11px] ${msg.role === "user" ? "text-slate-300" : "text-slate-500"}`}>
                      {msg.created_at?.slice(0, 19).replace("T", " ")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
