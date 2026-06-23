# Urban Setu

![Logo](https://res.cloudinary.com/dzhczzqwf/image/upload/v1782177886/urban-setu-favicon_qrnghw.png) 

AI powered road network extraction and resilience analysis for Indian cities.
Satellite imagery is used to detect roads (including roads hidden under trees,
shadows, or buildings), reconstruct a connected road network, and simulate
the impact of road closures for disaster and traffic planning.

![Dashboard](https://res.cloudinary.com/dzhczzqwf/image/upload/v1782214639/Screenshot_2026-06-23_170340_spopdn.png)

The project has three independent services:

- `FastAPI_Server/` — Python service that runs the segmentation model and
  builds the road network graph from a satellite GeoTIFF.
- `Node_Server/` — Express backend that orchestrates requests, caches
  processed results, and runs road-closure simulations.
- `Frontend/` — React + Leaflet dashboard for viewing the road network and
  running simulations.

Areas already pre-processed and included in `Node_Server/db/regions.json`:
Koramangala, Indiranagar / MG Road, Whitefield, Electronic City,
Hebbal / ORR Junction, Jayanagar / Banashankari.

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm

## About the model weights file (best_unetplusplus_b4.pkl)

This file is not included in the repository because of its size. It is
required for `FastAPI_Server` to run.

Download link: [best_unetplusplus_b4.pkl](https://drive.google.com/file/d/1gtmHd-cE90aLgfvEzMPOdNXI3yUVDdQZ/view?usp=sharing)

After downloading, place the file directly inside the `FastAPI_Server/`
folder, at the same level as `app.py`:

```
FastAPI_Server/
  app.py
  requirements.txt
  best_unetplusplus_b4.pkl   <- place it here
```

## 1. Running FastAPI_Server

```bash
cd FastAPI_Server
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Verify it is running by opening `http://localhost:8000` in a browser. You
should see a JSON message confirming the API is up.

## 2. Running Node_Server

```bash
cd Node_Server
npm install
cp .env.example .env
npm run dev
```

Verify it is running by opening `http://localhost:4000` in a browser.

The `.env` file should contain:

```
PORT=4000
FASTAPI_URL=http://127.0.0.1:8000
```

Since the pre-processed areas are already saved in `db/regions.json`, the
dashboard will work even without FastAPI_Server running. FastAPI_Server is
only needed if you want to process a new area.

To process a new area:

```bash
curl -X POST http://localhost:4000/api/analyze \
  -F "file=@/path/to/image.tiff" \
  -F "regionId=your_region_id"
```

## 3. Running Frontend

```bash
cd Frontend
npm install
cp .env.example .env
npm run dev
```

The `.env` file should contain:

```
VITE_API_URL=http://localhost:4000
```

Open `http://localhost:5173` in a browser. Select an area marked READY from
the left panel to load its road network. Click on any road segment to view
its details and simulate closing it.

## Running order

Start the services in this order:

1. Node_Server
2. Frontend
3. FastAPI_Server (only if processing a new area)

Since region data is already cached, FastAPI_Server does not need to be
running just to view the dashboard.

## Dataset source

Satellite imagery used for this project is sourced from the Copernicus
Browser (Sentinel-2, 10m resolution): https://browser.dataspace.copernicus.eu/

A sample GeoTIFF (cropped to one of the test areas) is provided for testing
the FastAPI_Server pipeline without needing to download imagery yourself:

Sample GeoTIFF link: [Bengaluru Sentinel-2 GeoTIFF Images](https://drive.google.com/drive/folders/1tOljH4xWyQrsJzBl8hVewbeCrXftTwti?usp=sharing)