import express from "express";
import multer from "multer";
import FormData from "form-data";
import axios from "axios";
import fs from "fs";
import db from "../db/lowdb.js";

const upload = multer({ dest: "uploads/" });
const router = express.Router();

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

router.post("/", upload.single("file"), async (req, res) => {
  const { regionId } = req.body;

  if (!regionId) {
    return res.status(400).json({ error: "regionId is required" });
  }
  if (!req.file) {
    return res.status(400).json({ error: "file (GeoTIFF) is required" });
  }

  try {
    const formData = new FormData();
    formData.append("file", fs.createReadStream(req.file.path), req.file.originalname);
    formData.append("region_id", regionId);

    const response = await axios.post(`${FASTAPI_URL}/predict`, formData, {
      headers: formData.getHeaders(),
      maxContentLength: Infinity,
      maxBodyLength: Infinity,
    });

    await db.read();
    db.data.regions[regionId] = response.data;
    await db.write();

    res.json(response.data);
  } catch (err) {
    const detail = err.response?.data?.detail || err.message;
    res.status(err.response?.status || 500).json({ error: "Analysis failed", detail });
  } finally {
    if (req.file) fs.unlink(req.file.path, () => {});
  }
});

export default router;
