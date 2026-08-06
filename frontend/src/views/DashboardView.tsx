import { useCallback, useEffect, useState } from "react";
import { getLogs, getStats } from "../api";
import type { PromptLog, Stats } from "../types";

export default function DashboardView() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [logs, setLogs] = useState<PromptLog[]>([]);

  const refresh = useCallback(() => {
    getStats().then(setStats).catch(() => {});
    getLogs(20).then(setLogs).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  const cards = stats
    ? [
        { label: "Documents", value: stats.documents },
        { label: "Chunks", value: stats.chunks },
        { label: "Collections", value: stats.collections },
        { label: "Conversations", value: stats.conversations },
        { label: "Prompts", value: stats.prompts },
        {
          label: "Avg latency",
          value: stats.average_latency_ms
            ? `${(stats.average_latency_ms / 1000).toFixed(1)}s`
            : "—",
        },
        { label: "Prompt tokens", value: stats.total_prompt_tokens },
        { label: "Response tokens", value: stats.total_response_tokens },
      ]
    : [];

  return (
    <div>
      <div className="row" style={{ marginBottom: 14, justifyContent: "space-between" }}>
        <h2>Dashboard</h2>
        <button className="ghost" onClick={refresh}>
          Refresh
        </button>
      </div>

      <div className="stat-grid">
        {cards.map((card) => (
          <div key={card.label} className="stat">
            <div className="value">{card.value}</div>
            <div className="label">{card.label}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>Recent prompts</h2>
        <table>
          <thead>
            <tr>
              <th>Question</th>
              <th>Answer</th>
              <th>Latency</th>
              <th>Tokens</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}>
                <td>{log.question}</td>
                <td className="hint">
                  {log.response.length > 120
                    ? `${log.response.slice(0, 120)}…`
                    : log.response}
                </td>
                <td>{(log.latency_ms / 1000).toFixed(1)}s</td>
                <td className="hint">
                  {log.prompt_tokens ?? "—"} / {log.response_tokens ?? "—"}
                </td>
                <td className="hint">
                  {new Date(log.created_at).toLocaleTimeString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
