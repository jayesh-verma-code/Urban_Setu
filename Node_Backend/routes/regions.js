import express from "express";
import db from "../db/lowdb.js";
import { REGIONS } from "../config/regions.js";

const router = express.Router();

router.get("/", async (req, res) => {
  await db.read();
  const list = REGIONS.map((r) => ({
    ...r,
    processed: Boolean(db.data.regions[r.id]),
  }));
  res.json(list);
});


router.get("/:regionId", async (req, res) => {
  await db.read();
  const data = db.data.regions[req.params.regionId];
  if (!data) {
    return res.status(404).json({
      error: `Region '${req.params.regionId}' has not been processed yet. Run /api/analyze for it first.`,
    });
  }
  res.json(data);
});

export default router;
