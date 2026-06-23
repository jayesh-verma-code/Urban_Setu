import { useState } from "react";
import { simulateClosure } from "../api.js";

export default function SimulatePanel({ regionId, edge, onClose, onResult }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSimulate() {
    setLoading(true);
    setError(null);
    try {
      const data = await simulateClosure(regionId, edge.edge_id);
      setResult(data);
      onResult(data);
    } catch (err) {
      setError(err.response?.data?.error || "Simulation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="simulate-panel">
      <div className="panel-header">
        <div className="panel-title">Road segment</div>
        <button className="close-btn" onClick={onClose}>
          ✕
        </button>
      </div>

      <div className="edge-meta">
        <div>EDGE_ID: {edge.edge_id}</div>
        <div>LENGTH: {edge.length_m} m</div>
        <div>CENTRALITY: {edge.centrality_score}</div>
        <div>AI_REPAIRED: {edge.is_reconnected ? "yes" : "no"}</div>
        <div>CONFIDENCE: {edge.confidence}</div>
      </div>

      <button className="simulate-btn" onClick={handleSimulate} disabled={loading}>
        {loading ? "Simulating…" : "Simulate closure"}
      </button>

      {error && (
        <div className="result-row">
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="result-block">
          <div className="result-row">
            <span>Route before</span>
            <span>{result.route_before ? `${result.route_before.distance_m} m` : "n/a"}</span>
          </div>
          <div className="result-row">
            <span>Route after</span>
            <span>{result.route_after ? `${result.route_after.distance_m} m` : "no path"}</span>
          </div>
          <div className="result-row">
            <span>Impact</span>
            {result.is_disconnected ? (
              <span className="delay-disconnected">DISCONNECTED</span>
            ) : (
              <span className="delay-positive">+{result.delay_increase_m} m</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
