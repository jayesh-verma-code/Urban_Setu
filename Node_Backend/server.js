import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import fs from "fs";

import analyzeRouter from "./routes/analyze.js";
import regionsRouter from "./routes/regions.js";
import simulateRouter from "./routes/simulate.js";

dotenv.config();

fs.mkdirSync("uploads", { recursive: true });

const app = express();
app.use(cors());
app.use(express.json());

app.use("/api/analyze", analyzeRouter);
app.use("/api/regions", regionsRouter);
app.use("/api/simulate", simulateRouter);

app.get("/", (req, res) => {
  res.json({ message: "Road Network Dashboard API running" });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`Node backend running on http://localhost:${PORT}`);
});
