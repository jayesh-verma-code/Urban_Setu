import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import MapView from "./components/MapView.jsx";
import SimulatePanel from "./components/SimulatePanel.jsx";
import { fetchRegions, fetchRegionData } from "./api.js";

export default function App() {
  const [regions, setRegions] = useState([]);
  const [selectedRegionId, setSelectedRegionId] = useState(null);
  const [regionData, setRegionData] = useState(null);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [simulationResult, setSimulationResult] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    fetchRegions()
      .then(setRegions)
      .catch(() => setLoadError("Could not reach the backend. Is the Node server running on port 4000?"));
  }, []);

  async function handleSelectRegion(regionId) {
    setSelectedRegionId(regionId);
    setSelectedEdge(null);
    setSimulationResult(null);

    try {
      const data = await fetchRegionData(regionId);
      setRegionData(data);
      setLoadError(null);
    } catch (err) {
      setRegionData(null);
      setLoadError(err.response?.data?.error || "This region has not been processed yet.");
    }
  }

  function handleEdgeClick(edgeProps) {
    setSelectedEdge(edgeProps);
    setSimulationResult(null);
  }

  return (
    <div className="app-shell">
      <Sidebar
        regions={regions}
        selectedRegionId={selectedRegionId}
        onSelectRegion={handleSelectRegion}
        regionData={regionData}
      />

      <div style={{ position: "relative", height: "100%" }}>
        <MapView
          regionData={regionData}
          onEdgeClick={handleEdgeClick}
          simulationResult={simulationResult}
          errorMessage={loadError}
        />

        {selectedEdge && (
          <SimulatePanel
            regionId={selectedRegionId}
            edge={selectedEdge}
            onClose={() => setSelectedEdge(null)}
            onResult={setSimulationResult}
          />
        )}
      </div>
    </div>
  );
}
