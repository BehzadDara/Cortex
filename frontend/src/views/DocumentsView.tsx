import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteDocument,
  getCollections,
  getDocuments,
  indexRepository,
  indexWebsite,
  uploadDocument,
  waitForJob,
} from "../api";
import type { Collection, Doc } from "../types";

export default function DocumentsView() {
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [url, setUrl] = useState("");
  const [repository, setRepository] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    getDocuments().then(setDocuments).catch(() => {});
    getCollections().then(setCollections).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  async function run(label: string, action: () => Promise<string>) {
    setBusy(label);
    setError(null);
    setNotice(null);
    try {
      setNotice(await action());
      refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(null);
    }
  }

  function upload() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    run("upload", async () => {
      const document = await uploadDocument(file, collectionId);
      if (fileInput.current) fileInput.current.value = "";
      return `Ingested ${document.filename} (${document.chunk_count} chunks)`;
    });
  }

  function crawl() {
    if (!url.trim()) return;
    run("url", async () => {
      const job = await indexWebsite(url.trim(), collectionId);
      setUrl("");
      const finished = await waitForJob(job.id);
      if (finished.status === "failed") throw new Error(finished.detail ?? "Job failed");
      return `Website job #${job.id}: ${finished.detail}`;
    });
  }

  function cloneRepository() {
    if (!repository.trim()) return;
    run("repository", async () => {
      const job = await indexRepository(repository.trim(), collectionId);
      setRepository("");
      const finished = await waitForJob(job.id);
      if (finished.status === "failed") throw new Error(finished.detail ?? "Job failed");
      return `Repository job #${job.id}: ${finished.detail}`;
    });
  }

  function collectionName(id: number | null): string {
    return collections.find((collection) => collection.id === id)?.name ?? "—";
  }

  return (
    <div>
      <div className="panel">
        <h2>Add content</h2>
        <div className="row" style={{ marginBottom: 10 }}>
          <span className="hint">Target collection:</span>
          <select
            value={collectionId ?? ""}
            onChange={(event) =>
              setCollectionId(event.target.value ? Number(event.target.value) : null)
            }
          >
            <option value="">No collection</option>
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
              </option>
            ))}
          </select>
        </div>
        <div className="row" style={{ marginBottom: 10 }}>
          <input ref={fileInput} type="file" accept=".txt,.md,.pdf,.docx,.png,.jpg,.jpeg" />
          <button className="primary" onClick={upload} disabled={busy !== null}>
            {busy === "upload" ? "Ingesting…" : "Upload file"}
          </button>
        </div>
        <div className="row" style={{ marginBottom: 10 }}>
          <input
            className="grow"
            placeholder="https://example.com"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
          <button className="primary" onClick={crawl} disabled={busy !== null}>
            {busy === "url" ? "Crawling…" : "Index website"}
          </button>
        </div>
        <div className="row">
          <input
            className="grow"
            placeholder="https://github.com/user/repo"
            value={repository}
            onChange={(event) => setRepository(event.target.value)}
          />
          <button className="primary" onClick={cloneRepository} disabled={busy !== null}>
            {busy === "repository" ? "Cloning…" : "Index repository"}
          </button>
        </div>
        {notice && <p className="hint" style={{ marginTop: 10, color: "var(--ok)" }}>{notice}</p>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="panel">
        <h2>Documents ({documents.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Collection</th>
              <th>Chunks</th>
              <th>Added</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {documents.map((document) => (
              <tr key={document.id}>
                <td style={{ wordBreak: "break-all" }}>{document.filename}</td>
                <td>{collectionName(document.collection_id)}</td>
                <td>{document.chunk_count}</td>
                <td className="hint">
                  {new Date(document.created_at).toLocaleDateString()}
                </td>
                <td>
                  <button
                    className="danger"
                    onClick={() =>
                      run("delete", async () => {
                        await deleteDocument(document.id);
                        return `Deleted ${document.filename}`;
                      })
                    }
                  >
                    delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
