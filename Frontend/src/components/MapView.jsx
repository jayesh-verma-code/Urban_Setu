import { useMemo, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, Polyline, useMapEvents } from "react-leaflet";

function centralityColor(feature) {
  if (feature.properties.is_reconnected) return "#7c8cff";
  const score = feature.properties.centrality_score;
  if (score > 0.6) return "#e63946";
  if (score > 0.3) return "#ffb703";
  return "#000000";
}

function CursorTracker({ onMove }) {
  useMapEvents({
    mousemove: (e) => onMove(e.latlng),
  });
  return null;
}

export default function MapView({ regionData, onEdgeClick, simulationResult, errorMessage }) {
  const [cursor, setCursor] = useState(null);

  const geoJsonStyle = useMemo(
    () => (feature) => ({
      color: centralityColor(feature),
      weight: feature.properties.is_reconnected ? 3 : 2.5,
      dashArray: feature.properties.is_reconnected ? "6 4" : null,
      opacity: 0.9,
    }),
    []
  );

  if (errorMessage) {
    return <div className="empty-state">{errorMessage}</div>;
  }

  if (!regionData) {
    return (
      <div className="empty-state">
        Select a processed area from the left to load its road network.
      </div>
    );
  }

  const center = [
    (regionData.bounds.north + regionData.bounds.south) / 2,
    (regionData.bounds.east + regionData.bounds.west) / 2,
  ];

  return (
    <div className="map-area">
      <MapContainer center={center} zoom={15} className="map-container">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <GeoJSON
          key={regionData.region_id}
          data={regionData.road_network}
          style={geoJsonStyle}
          onEachFeature={(feature, layer) => {
            layer.on("click", () => onEdgeClick(feature.properties));
            layer.bindTooltip(
              `Length: ${feature.properties.length_m}m · Centrality: ${feature.properties.centrality_score}`
            );
          }}
        />

        {simulationResult?.route_before && (
          <Polyline
            positions={simulationResult.route_before.coordinates.map(([lon, lat]) => [lat, lon])}
            pathOptions={{ color: "#8295b8", weight: 4, dashArray: "2 6" }}
          />
        )}

        {simulationResult?.route_after && (
          <Polyline
            positions={simulationResult.route_after.coordinates.map(([lon, lat]) => [lat, lon])}
            pathOptions={{ color: "#5ad160", weight: 5 }}
          />
        )}

        <CursorTracker onMove={setCursor} />
      </MapContainer>

      <div className="hud-readout">
        {cursor ? `${cursor.lat.toFixed(5)}, ${cursor.lng.toFixed(5)}` : "move cursor over map"}
      </div>
    </div>
  );
}
