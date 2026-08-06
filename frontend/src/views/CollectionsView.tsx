import { useCallback, useEffect, useState } from "react";
import { createCollection, deleteCollection, getCollections } from "../api";
import type { Collection } from "../types";

export default function CollectionsView() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getCollections().then(setCollections).catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);

  async function create() {
    if (!name.trim()) return;
    setError(null);
    try {
      await createCollection(name.trim());
      setName("");
      refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function remove(collection: Collection) {
    const confirmed = window.confirm(
      `Delete "${collection.name}" and its ${collection.document_count} documents?`,
    );
    if (!confirmed) return;
    try {
      await deleteCollection(collection.id);
      refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <div>
      <div className="panel">
        <h2>New collection</h2>
        <div className="row">
          <input
            className="grow"
            placeholder="Collection name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && create()}
          />
          <button className="primary" onClick={create}>
            Create
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="panel">
        <h2>Collections ({collections.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Documents</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {collections.map((collection) => (
              <tr key={collection.id}>
                <td>{collection.name}</td>
                <td>{collection.document_count}</td>
                <td className="hint">
                  {new Date(collection.created_at).toLocaleDateString()}
                </td>
                <td>
                  <button className="danger" onClick={() => remove(collection)}>
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
