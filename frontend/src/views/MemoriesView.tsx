import { useCallback, useEffect, useState } from "react";
import { deleteMemory, getMemories } from "../api";
import type { Memory } from "../types";

export default function MemoriesView() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getMemories().then(setMemories).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  async function forget(memory: Memory) {
    setError(null);
    try {
      await deleteMemory(memory.id);
      refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <div className="page">
      <div className="page-inner">
        <div className="panel">
          <h2>What Cortex remembers ({memories.length})</h2>
          <p className="panel-note">
            Durable facts picked out of your own messages — your name, where you
            work, the tools you prefer. They are recalled in every later
            conversation, so anything wrong or out of date is worth forgetting.
          </p>
          {memories.length === 0 ? (
            <p className="empty">
              Nothing remembered yet. Mention something about yourself in a chat
              and it will show up here.
            </p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Fact</th>
                  <th>Remembered</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {memories.map((memory) => (
                  <tr key={memory.id}>
                    <td>{memory.text}</td>
                    <td className="hint">
                      {memory.created_at
                        ? new Date(memory.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td>
                      <button
                        className="danger"
                        onClick={() => forget(memory)}
                        aria-label={`Forget: ${memory.text}`}
                      >
                        forget
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </div>
  );
}
