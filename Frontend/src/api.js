import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:4000";

export const api = axios.create({ baseURL: BASE_URL });

export async function fetchRegions() {
  const { data } = await api.get("/api/regions");
  return data;
}

export async function fetchRegionData(regionId) {
  const { data } = await api.get(`/api/regions/${regionId}`);
  return data;
}

export async function simulateClosure(regionId, edgeId) {
  const { data } = await api.post("/api/simulate", { regionId, edgeId });
  return data;
}