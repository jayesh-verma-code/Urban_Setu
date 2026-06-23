import io
import os
import math
import pickle
import uuid

import numpy as np
import torch
import cv2
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import xy as transform_xy
from skimage.morphology import skeletonize
import sknw
import networkx as nx
from scipy.spatial import cKDTree

import segmentation_models_pytorch as smp
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse


# config  (tune these based on your actual imagery resolution)


TILE_SIZE = 768            # model's native input size ( do not change unless model is retrained )
TILE_OVERLAP = 64          # pixels of overlap between adjacent tiles (prevents boundary discontinuity)

MIN_IMAGE_DIM = 768        # reject images smaller than this (in pixels, either dimension)
MAX_IMAGE_DIM = 20000      # reject images larger than this (safety limit on processing time/memory)

MASK_THRESHOLD = 0.5       # sigmoid threshold for binary road/no-road decision

NODE_MERGE_THRESHOLD_PX = TILE_OVERLAP // 2

RECONNECT_MAX_GAP_PX = 60

RECONNECT_ANGLE_TOLERANCE_DEG = 25

PREDICTIONS_DIR = "predictions"
os.makedirs(PREDICTIONS_DIR, exist_ok=True)

device = torch.device("cpu")


# model loading


class CPU_Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "torch.storage" and name == "_load_from_bytes":
            return lambda b: torch.load(io.BytesIO(b), map_location="cpu")
        return super().find_class(module, name)


model = smp.UnetPlusPlus(
    encoder_name="timm-efficientnet-b4",
    encoder_weights=None,
    in_channels=3,
    classes=1
)

with open("best_unetplusplus_b4.pkl", "rb") as f:
    state_dict = CPU_Unpickler(f).load()

model.load_state_dict(state_dict)
model.to(device)
model.eval()

print("Model Loaded Successfully!")

app = FastAPI(title="Road Segmentation & Graph Reconstruction API")


# home

@app.get("/")
def home():
    return {
        "message": "Road Segmentation + Graph API Running",
        "requirements": {
            "format": "GeoTIFF (.tif/.tiff) with valid CRS + affine transform",
            "min_dimension_px": MIN_IMAGE_DIM,
            "max_dimension_px": MAX_IMAGE_DIM,
        }
    }


# serve image (mask and overlay preview)

@app.get("/image/{filename}")
def get_image(filename: str):
    path = os.path.join(PREDICTIONS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/png")


# step 1 : validation

def validate_and_open_geotiff(file_bytes: bytes):
    """
    Opens the uploaded bytes with rasterio and validates it is a usable
    GeoTIFF (valid CRS + transform) within acceptable dimensions.
    Raises HTTPException(400, <clear message>) on any failure -- this
    function NEVER lets the server crash on bad input.
    """
    try:
        memfile = rasterio.io.MemoryFile(file_bytes)
        src = memfile.open()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read the uploaded file as a GeoTIFF. "
                "Please upload a valid .tif/.tiff file exported from a GIS/"
                "satellite source (e.g. Sentinel-2, Bhuvan, USGS EarthExplorer)."
            )
        )

    if src.crs is None or src.transform is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded GeoTIFF has no CRS / affine transform. The file "
                "must contain valid geographic metadata so road coordinates "
                "can be mapped to real lat/lng. Plain PNG/JPG cannot be used "
                "for this reason -- please upload a proper GeoTIFF."
            )
        )

    width, height = src.width, src.height

    if width < MIN_IMAGE_DIM or height < MIN_IMAGE_DIM:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Image too small: received {width}x{height} px. "
                f"Minimum required dimension is {MIN_IMAGE_DIM}x{MIN_IMAGE_DIM} px "
                f"(the model's native tile size). Please upload a larger area."
            )
        )

    if width > MAX_IMAGE_DIM or height > MAX_IMAGE_DIM:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Image too large: received {width}x{height} px. "
                f"Maximum allowed dimension is {MAX_IMAGE_DIM}x{MAX_IMAGE_DIM} px. "
                f"Please crop to your area of interest before uploading."
            )
        )

    if src.count < 3:
        src.close()
        raise HTTPException(
            status_code=400,
            detail=(
                f"Image has only {src.count} band(s). At least 3 bands "
                f"(R, G, B) are required."
            )
        )

    return src



# step 2: convert to EPSG:4326


def reproject_to_wgs84(src):
    """
    Returns (image[H,W,3] in ORIGINAL dtype, transform, crs_string) all in
    EPSG:4326, so every downstream pixel -> lat/lng conversion uses ONE
    consistent affine transform for the whole region.

    IMPORTANT: this function intentionally does NOT cast to uint8 here.
    Source imagery (e.g. Sentinel-2) is very often uint16 with values up to
    ~65535. Casting straight to uint8 does not rescale those values, it
    truncates/wraps them, which destroys the image (turns it into noise).
    Proper 0-255 normalization happens separately in normalize_to_uint8(),
    AFTER reprojection, using the real min/max of this specific image.
    """
    dst_crs = "EPSG:4326"
    src_dtype = src.dtypes[0]

    if src.crs.to_string() == dst_crs:
        image = src.read([1, 2, 3])
        return np.transpose(image, (1, 2, 0)), src.transform, dst_crs

    transform, width, height = calculate_default_transform(
        src.crs, dst_crs, src.width, src.height, *src.bounds
    )

    dst_array = np.zeros((3, height, width), dtype=src_dtype)

    for i in range(1, 4):
        reproject(
            source=rasterio.band(src, i),
            destination=dst_array[i - 1],
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear
        )

    return np.transpose(dst_array, (1, 2, 0)), transform, dst_crs


def normalize_to_uint8(image: np.ndarray, low_percentile: float = 2, high_percentile: float = 98):
    """
    Converts a multi-band image of ANY numeric dtype (uint16, int32, etc.)
    into a proper 0-255 uint8 RGB image using a per-band percentile stretch.

    Why percentile (2nd-98th) and not plain min/max: satellite imagery often
    has a few extreme outlier pixels (sensor noise, glare). Stretching from
    true min/max would let those outliers compress all the real detail into
    a tiny range. Percentile stretch clips the extremes first, then scales,
    so roads/buildings/vegetation keep good contrast.
    """
    if image.dtype == np.uint8:
        return image

    out = np.zeros(image.shape, dtype=np.uint8)
    for c in range(image.shape[2]):
        band = image[:, :, c].astype(np.float32)
        lo, hi = np.percentile(band, [low_percentile, high_percentile])
        if hi - lo < 1e-6:
            hi = lo + 1.0
        band = np.clip(band, lo, hi)
        band = (band - lo) / (hi - lo) * 255.0
        out[:, :, c] = band.astype(np.uint8)
    return out


# step 3 : tiling (with ovelapping)

def generate_tiles(image: np.ndarray, tile_size: int, overlap: int):
    """
    Yields (tile_image, row_off, col_off) covering the full image with
    overlapping tiles. Edge tiles are zero-padded up to tile_size so the
    model always receives a consistent input shape; the padded region is
    simply ignored/cropped out when results are stitched back together.
    """
    h, w = image.shape[0], image.shape[1]
    stride = tile_size - overlap

    rows = list(range(0, h, stride))
    cols = list(range(0, w, stride))

    tiles = []
    for r in rows:
        if r >= h:
            continue
        for c in cols:
            if c >= w:
                continue

            tile = image[r:r + tile_size, c:c + tile_size]
            pad_h = tile_size - tile.shape[0]
            pad_w = tile_size - tile.shape[1]

            if pad_h > 0 or pad_w > 0:
                tile = np.pad(
                    tile, ((0, pad_h), (0, pad_w), (0, 0)),
                    mode="constant", constant_values=0
                )

            tiles.append((tile, r, c))

    return tiles



# step 4: model inference (per tile)


def predict_mask(tile_rgb: np.ndarray):
    """
    Runs the model on a single 768x768 RGB tile.
    Returns (binary_mask[H,W] uint8 0/255, probability_map[H,W] float32 0..1)
    """
    image = tile_rgb.astype(np.float32) / 255.0
    image = np.transpose(image, (2, 0, 1))
    tensor = torch.tensor(image).unsqueeze(0).float().to(device)

    with torch.no_grad():
        output = model(tensor)
        prob = torch.sigmoid(output).squeeze().cpu().numpy()

    binary_mask = (prob > MASK_THRESHOLD).astype(np.uint8) * 255
    return binary_mask, prob


# step 5: skeleton into graoh  (per tile, in GLOBAL pixel coordinates)


def _safe_prob(prob_map, y, x):
    yi, xi = int(round(y)), int(round(x))
    if 0 <= yi < prob_map.shape[0] and 0 <= xi < prob_map.shape[1]:
        return float(prob_map[yi, xi])
    return 0.5


def tile_mask_to_graph(mask: np.ndarray, prob_map: np.ndarray, row_off: int, col_off: int):
    """
    Converts one tile's binary mask into a networkx graph. Every node/edge
    coordinate is stored in GLOBAL pixel space (row_off/col_off added in),
    so graphs from different tiles can be composed/merged directly without
    any extra coordinate bookkeeping.
    """
    if mask.sum() == 0:
        return nx.Graph()

    skeleton = skeletonize(mask > 0)
    if skeleton.sum() < 2:
        return nx.Graph()

    raw_graph = sknw.build_sknw(skeleton)
    g = nx.Graph()

    def to_global(local_y, local_x):
        return (float(local_y + row_off), float(local_x + col_off))

    for node_id, node_data in raw_graph.nodes(data=True):
        ly, lx = node_data['o']
        global_coord = to_global(ly, lx)
        g.add_node(global_coord, confidence=_safe_prob(prob_map, ly, lx))

    for u, v, edge_data in raw_graph.edges(data=True):
        uy, ux = raw_graph.nodes[u]['o']
        vy, vx = raw_graph.nodes[v]['o']
        u_global = to_global(uy, ux)
        v_global = to_global(vy, vx)

        local_pts = edge_data.get('pts', [])
        global_pts = [to_global(py, px) for py, px in local_pts] if len(local_pts) else [u_global, v_global]

        confs = [_safe_prob(prob_map, py, px) for py, px in local_pts] if len(local_pts) else []
        edge_confidence = float(np.mean(confs)) if confs else 0.5

        g.add_edge(
            u_global, v_global,
            pts=global_pts,
            confidence=edge_confidence,
            is_reconnected=False
        )

    return g



# step 6: merge tile graph 


def merge_close_nodes(graph: nx.Graph, threshold_px: float):
    """
    Nodes that fall within `threshold_px` of each other (this happens at
    tile overlap zones, where the same junction gets detected twice -- once
    from each neighboring tile) are merged into a single node via a simple
    union-find over a KD-tree proximity query.
    """
    nodes = list(graph.nodes())
    if len(nodes) < 2:
        return graph

    coords = np.array(nodes)
    tree = cKDTree(coords)
    pairs = tree.query_pairs(r=threshold_px)

    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i, j in pairs:
        union(nodes[i], nodes[j])

    mapping = {n: find(n) for n in nodes}

    merged = nx.Graph()
    for n in nodes:
        rep = mapping[n]
        if rep not in merged:
            merged.add_node(rep, confidence=graph.nodes[n].get('confidence', 0.5))

    for u, v, data in graph.edges(data=True):
        ru, rv = mapping[u], mapping[v]
        if ru == rv:
            continue  # would create a self-loop from merging -- drop it
        merged.add_edge(ru, rv, **data)

    return merged



# step 7: reconnect occluation gaps (like trees / shadows / buildings)


def get_tangent_vector(graph: nx.Graph, node, look_back: int = 6):
    """
    Estimates the direction a dangling road-end is "pointing" by looking
    at a handful of points near the node along its only edge. Used to
    check whether two dangling ends plausibly continue the same road.
    """
    edges = list(graph.edges(node, data=True))
    if not edges:
        return None

    _, _, data = edges[0]
    pts = data.get('pts')
    if not pts or len(pts) < 2:
        return None

    node_arr = np.array(node)
    p_start, p_end = np.array(pts[0]), np.array(pts[-1])

    if np.linalg.norm(p_start - node_arr) < np.linalg.norm(p_end - node_arr):
        ref = np.array(pts[min(look_back, len(pts) - 1)])
    else:
        ref = np.array(pts[max(0, len(pts) - 1 - look_back)])

    direction = node_arr - ref
    norm = np.linalg.norm(direction)
    if norm == 0:
        return None
    return direction / norm


def reconnect_dangling_ends(graph: nx.Graph, max_gap_px: float, angle_tolerance_deg: float):
    """
    Finds degree-1 nodes (dead ends), and for each one, looks for the
    closest OTHER dead end within max_gap_px whose direction roughly
    continues the same line (within angle_tolerance_deg). If found, adds
    a new edge marked is_reconnected=True -- this is the "repair the
    occlusion gap" step.

    NOTE: This is a simple, explainable heuristic (distance + direction),
    not a learned model. Good enough to demonstrate the concept; tune
    RECONNECT_MAX_GAP_PX / RECONNECT_ANGLE_TOLERANCE_DEG against your
    actual imagery before relying on it heavily.
    """
    dangling = [n for n in graph.nodes() if graph.degree(n) == 1]
    if len(dangling) < 2:
        return graph

    coords = np.array(dangling)
    tree = cKDTree(coords)
    used = set()

    for idx, node in enumerate(dangling):
        if node in used:
            continue

        direction_a = get_tangent_vector(graph, node)
        if direction_a is None:
            continue

        nearby_idx = tree.query_ball_point(coords[idx], r=max_gap_px)
        best_candidate, best_dist = None, float("inf")

        for j in nearby_idx:
            candidate = dangling[j]
            if candidate == node or candidate in used:
                continue

            gap_vec = np.array(candidate) - np.array(node)
            gap_dist = float(np.linalg.norm(gap_vec))
            if gap_dist == 0 or gap_dist > max_gap_px:
                continue

            gap_dir = gap_vec / gap_dist
            angle = math.degrees(math.acos(np.clip(np.dot(direction_a, gap_dir), -1.0, 1.0)))

            if angle <= angle_tolerance_deg and gap_dist < best_dist:
                best_dist = gap_dist
                best_candidate = candidate

        if best_candidate is not None:
            graph.add_edge(
                node, best_candidate,
                pts=[node, best_candidate],
                confidence=0.4,        # lower confidence -- this is a guessed connection, not a direct detection
                is_reconnected=True
            )
            used.add(node)
            used.add(best_candidate)

    return graph


# step 8 : centrality

def compute_edge_centrality(graph: nx.Graph):
    if graph.number_of_edges() == 0:
        return {}
    return nx.edge_betweenness_centrality(graph, normalized=True)


# step 9: graph into GeoJSON  (basically pixel into real lon/lat)


def pixel_to_lonlat(transform, row, col):
    lon, lat = transform_xy(transform, row, col, offset="center")
    return lon, lat


def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def line_length_m(coords_lonlat):
    total = 0.0
    for i in range(len(coords_lonlat) - 1):
        lon1, lat1 = coords_lonlat[i]
        lon2, lat2 = coords_lonlat[i + 1]
        total += haversine_m(lon1, lat1, lon2, lat2)
    return total


def graph_to_geojson(graph: nx.Graph, transform):
    centrality = compute_edge_centrality(graph)
    features = []

    for u, v, data in graph.edges(data=True):
        pts = data.get('pts') or [u, v]

        coords_lonlat = [list(pixel_to_lonlat(transform, py, px)) for py, px in pts]
        length_m = line_length_m(coords_lonlat)
        score = centrality.get((u, v), centrality.get((v, u), 0.0))

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords_lonlat
            },
            "properties": {
                "edge_id": f"e_{uuid.uuid4().hex[:8]}",
                "length_m": round(length_m, 2),
                "centrality_score": round(float(score), 4),
                "is_reconnected": bool(data.get("is_reconnected", False)),
                "confidence": round(float(data.get("confidence", 0.5)), 3)
            }
        })

    return {"type": "FeatureCollection", "features": features}


def compute_stats(geojson):
    features = geojson["features"]
    total_length_km = sum(f["properties"]["length_m"] for f in features) / 1000.0
    reconnected = sum(1 for f in features if f["properties"]["is_reconnected"])
    return {
        "total_road_length_km": round(total_length_km, 2),
        "total_segments": len(features),
        "reconnected_segments": reconnected
    }


def compute_bounds(transform, width, height):
    corners = [(0, 0), (0, width), (height, 0), (height, width)]
    lons, lats = [], []
    for r, c in corners:
        lon, lat = pixel_to_lonlat(transform, r, c)
        lons.append(lon)
        lats.append(lat)
    return {"north": max(lats), "south": min(lats), "east": max(lons), "west": min(lons)}


# main endpoint /predict

@app.post("/predict")
async def predict(file: UploadFile = File(...), region_id: str = Form(...)):
    """
    Expects multipart/form-data with:
      - file: the GeoTIFF (.tif/.tiff)
      - region_id: string identifying this area (e.g. "bengaluru_koramangala")
    Returns the full JSON contract: status, region_id, bounds, crs,
    mask_url, overlay_url, road_network (GeoJSON), stats.
    On invalid input, returns HTTP 400 with a clear, specific message --
    never crashes.
    """
    contents = await file.read()

    src = validate_and_open_geotiff(contents)

    try:
        image, transform, crs = reproject_to_wgs84(src)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to reproject image: {str(e)}")
    finally:
        src.close()

    # CRITICAL: normalize to 0-255 uint8 here, using THIS image's real value
    # range. Skipping this (or doing a naive dtype cast) turns uint16 source
    # imagery into noise and the model will detect zero roads.
    image = normalize_to_uint8(image)

    height, width = image.shape[0], image.shape[1]
    tiles = generate_tiles(image, TILE_SIZE, TILE_OVERLAP)

    if len(tiles) == 0:
        raise HTTPException(status_code=400, detail="No valid tiles could be generated from this image.")

    combined_graph = nx.Graph()
    full_mask_preview = np.zeros((height, width), dtype=np.uint8)

    for tile_img, row_off, col_off in tiles:
        rgb_tile = tile_img[:, :, :3]
        mask, prob = predict_mask(rgb_tile)

        th, tw = mask.shape
        end_row, end_col = min(row_off + th, height), min(col_off + tw, width)
        full_mask_preview[row_off:end_row, col_off:end_col] = np.maximum(
            full_mask_preview[row_off:end_row, col_off:end_col],
            mask[:end_row - row_off, :end_col - col_off]
        )

        tile_graph = tile_mask_to_graph(mask, prob, row_off, col_off)
        combined_graph = nx.compose(combined_graph, tile_graph)

    combined_graph = merge_close_nodes(combined_graph, threshold_px=NODE_MERGE_THRESHOLD_PX)
    combined_graph = reconnect_dangling_ends(
        combined_graph,
        max_gap_px=RECONNECT_MAX_GAP_PX,
        angle_tolerance_deg=RECONNECT_ANGLE_TOLERANCE_DEG
    )

    road_network = graph_to_geojson(combined_graph, transform)
    stats = compute_stats(road_network)
    bounds = compute_bounds(transform, width, height)

    uid = uuid.uuid4().hex

    mask_filename = f"{uid}_mask.png"
    cv2.imwrite(os.path.join(PREDICTIONS_DIR, mask_filename), full_mask_preview)

    overlay_base = cv2.cvtColor(image[:, :, :3].copy(), cv2.COLOR_RGB2BGR)
    red_overlay = overlay_base.copy()
    red_overlay[full_mask_preview > 0] = [0, 0, 255]
    blended = cv2.addWeighted(overlay_base, 0.7, red_overlay, 0.3, 0)
    overlay_filename = f"{uid}_overlay.png"
    cv2.imwrite(os.path.join(PREDICTIONS_DIR, overlay_filename), blended)

    return JSONResponse(content={
        "status": "success",
        "region_id": region_id,
        "bounds": bounds,
        "crs": "EPSG:4326",
        "mask_url": f"/image/{mask_filename}",
        "overlay_url": f"/image/{overlay_filename}",
        "road_network": road_network,
        "stats": stats
    })