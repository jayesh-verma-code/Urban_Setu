import express from "express";
import db from "../db/lowdb.js";
import { dijkstra } from "graphology-shortest-path";
import {
  buildGraphFromGeoJSON,
  pickAnchorNodes,
  pathDistance,
  pathToCoordinates,
  findEdgeByEdgeId,
} from "../utils/graph.js";

const router = express.Router();

router.post("/", async (req, res) => {
  const { regionId, edgeId } = req.body;

  if (!regionId || !edgeId) {
    return res.status(400).json({ error: "regionId and edgeId are required" });
  }

  await db.read();
  const regionData = db.data.regions[regionId];
  if (!regionData) {
    return res.status(404).json({ error: `Region '${regionId}' has not been processed yet.` });
  }

  const graph = buildGraphFromGeoJSON(regionData.road_network);
  const [source, target] = pickAnchorNodes(graph);

  if (!source || !target) {
    return res.status(400).json({ error: "Not enough connected roads in this region to simulate." });
  }

  const beforePath = dijkstra.bidirectional(graph, source, target, "weight");
  const beforeDistance = beforePath ? pathDistance(graph, beforePath) : null;

  const edgeMatch = findEdgeByEdgeId(graph, edgeId);
  if (!edgeMatch) {
    return res.status(404).json({ error: `Edge '${edgeId}' not found in this region's road network.` });
  }
  graph.dropEdge(edgeMatch.edge);

  const afterPath = dijkstra.bidirectional(graph, source, target, "weight");
  const afterDistance = afterPath ? pathDistance(graph, afterPath) : null;

  res.json({
    blocked_edge_id: edgeId,
    route_before: beforePath
      ? { coordinates: pathToCoordinates(graph, beforePath), distance_m: Math.round(beforeDistance) }
      : null,
    route_after: afterPath
      ? { coordinates: pathToCoordinates(graph, afterPath), distance_m: Math.round(afterDistance) }
      : null,
    is_disconnected: !afterPath,
    delay_increase_m:
      afterDistance != null && beforeDistance != null ? Math.round(afterDistance - beforeDistance) : null,
  });
});

export default router;
