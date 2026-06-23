import { Low } from "lowdb";
import { JSONFile } from "lowdb/node";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const file = path.join(__dirname, "regions.json");

const adapter = new JSONFile(file);
const db = new Low(adapter, { regions: {} });

await db.read();
db.data ||= { regions: {} };
await db.write();

export default db;
