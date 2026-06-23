export default function Sidebar({ regions, selectedRegionId, onSelectRegion, regionData }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <img 
          className="logo-img"
          src="https://res.cloudinary.com/dzhczzqwf/image/upload/v1782176968/urban-setu-logo_jrtwpa.png" 
          alt="logo" 
        />
        <div>
          <div className="brand-title">Urban Setu</div>
          <div className="brand-subtitle">Occlusion Aware Resilience Mapping</div>
        </div>
      </div>

      <div>
        <div className="section-label">Bengaluru Area</div>
        <div className="region-list">
          {regions.map((r) => (
            <div
              key={r.id}
              className={`region-item ${r.id === selectedRegionId ? "active" : ""}`}
              onClick={() => onSelectRegion(r.id)}
            >
              <span>{r.name}</span>
              <span className={`region-status ${r.processed ? "processed" : "pending"}`}>
                {r.processed ? "READY" : "PENDING"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {regionData && (
        <>
          <div>
            <div className="section-label">Network stats</div>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{regionData.stats.total_road_length_km}</div>
                <div className="stat-label">km of road</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{regionData.stats.total_segments}</div>
                <div className="stat-label">segments</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{regionData.stats.reconnected_segments}</div>
                <div className="stat-label">occlusion repairs</div>
              </div>
            </div>
          </div>

          <div>
            <div className="section-label">Legend</div>
            <div className="legend">
              <div className="legend-row">
                <span className="legend-swatch" style={{ background: "var(--road-normal)" }} />
                Normal road
              </div>
              <div className="legend-row">
                <span className="legend-swatch" style={{ background: "var(--road-important)" }} />
                Important road
              </div>
              <div className="legend-row">
                <span className="legend-swatch" style={{ background: "var(--road-critical)" }} />
                Critical / bottleneck
              </div>
              <div className="legend-row">
                <span className="legend-swatch" style={{ background: "var(--road-reconnected)" }} />
                AI-repaired (occlusion)
              </div>
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
