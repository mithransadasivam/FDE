// Day 8 homework: the e2e run starts with an empty engagement folder, so put the document store's three rows (P8 to P10) in it.
import { copyFileSync, mkdirSync } from "node:fs";

export default function seed() {
  mkdirSync("../.e2e/engagement/integration", { recursive: true });
  copyFileSync("../engagement/integration/permission_rows.json", "../.e2e/engagement/integration/permission_rows.json");
}
