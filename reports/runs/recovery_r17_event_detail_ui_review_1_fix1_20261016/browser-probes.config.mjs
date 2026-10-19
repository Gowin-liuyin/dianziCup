import { fileURLToPath } from "node:url";
import base from "./browser.config.mjs";

export default {
  ...base,
  testDir: fileURLToPath(new URL(".", import.meta.url)),
  testMatch: ["review-fixture-probes.spec.ts"],
  grep: /independent (loading|revision|narrow)/,
  outputDir: fileURLToPath(new URL("./browser_probe_artifacts", import.meta.url)),
  reporter: [["json", { outputFile: fileURLToPath(new URL("./browser-probes.json", import.meta.url)) }]],
};
