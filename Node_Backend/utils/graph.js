import Graph from "graphology";

function nodeKey(coord) {
  // coord is [lon, lat]
  return `${coord[0]},${coord[1]}`;
}

export function buildGraphFromGeoJSON(geojson) {
  const graph = new Graph({ type: "undirected", allowSelfLoops: false });

  for (const feature of geojson.features) {
    const coords = feature.geometry.coordinates;
    if (!coords || coords.length < 2) continue;

    const sourceCoord = coords[0];
    const targetCoord = coords[coords.length - 1];
    const sourceKey = nodeKey(sourceCoord);
    const targetKey = nodeKey(targetCoord);

    if (!graph.hasNode(sourceKey)) {
      graph.addNode(sourceKey, { lon: sourceCoord[0], lat: sourceCoord[1] });
    }
    if (!graph.hasNode(targetKey)) {
      graph.addNode(targetKey, { lon: targetCoord[0], lat: targetCoord[1] });
    }

    if (sourceKey === targetKey) continue;
    if (graph.hasEdge(sourceKey, targetKey)) continue; // skip parallel duplicates for simplicity

    graph.addEdge(sourceKey, targetKey, {
      edgeId: feature.properties.edge_id,
      weight: feature.properties.length_m || 1,
      coordinates: coords,
      centrality: feature.properties.centrality_score,
      isReconnected: feature.properties.is_reconnected,
    });
  }

  return graph;
}

export function pickAnchorNodes(graph) {
  const nodes = graph.nodes();
  if (nodes.length < 2) return [null, null];

  const sorted = [...nodes].sort((a, b) => graph.degree(b) - graph.degree(a));
  return [sorted[0], sorted[1]];
}

export function pathDistance(graph, path) {
  let total = 0;
  for (let i = 0; i < path.length - 1; i++) {
    const edge = graph.edge(path[i], path[i + 1]);
    if (edge) total += graph.getEdgeAttribute(edge, "weight");
  }
  return total;
}

export function pathToCoordinates(graph, path) {
  return path.map((nodeId) => {
    const attrs = graph.getNodeAttributes(nodeId);
    return [attrs.lon, attrs.lat];
  });
}

export function findEdgeByEdgeId(graph, edgeId) {
  let found = null;
  graph.forEachEdge((edge, attrs, source, target) => {
    if (attrs.edgeId === edgeId) {
      found = { edge, source, target };
    }
  });
  return found;
}
