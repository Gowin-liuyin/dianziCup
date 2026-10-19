/** Enumerate parsed TypeScript inputs without checking types or emitting files. */
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const v8 = require("node:v8");
const ts = require("D:/dianzi/frontend/node_modules/typescript");
const run = __dirname;
const roots = { root: "D:/dianzi/frontend", reviewer: "D:/wt/r17-fix3-review/frontend" };
const hash = (content) => crypto.createHash("sha256").update(content).digest("hex");
const protectedHash = hash(fs.readFileSync(roots.root + "/tsconfig.tsbuildinfo"));
const startedUtc = new Date().toISOString();
const normalizePath = (name, frontend) => {
  const absolute = path.resolve(name).replaceAll("\\", "/");
  const dependency = absolute.toLowerCase().indexOf("/node_modules/");
  return dependency >= 0 ? absolute.slice(dependency + 1) : path.relative(frontend, absolute).replaceAll("\\", "/");
};
const fingerprints = {};
for (const [label, frontend] of Object.entries(roots)) {
  const parsed = ts.getParsedCommandLineOfConfigFile(frontend + "/tsconfig.json", { noEmit: true, ...(label === "reviewer" ? { incremental: false } : {}) }, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic: (diagnostic) => { throw new Error(ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")); },
  });
  if (!parsed || parsed.errors.length) throw new Error("TypeScript config parse failed: " + label);
  let program = ts.createProgram({ rootNames: parsed.fileNames, options: parsed.options, projectReferences: parsed.projectReferences });
  const sourceFiles = program.getSourceFiles().map((source) => ({
    path: normalizePath(source.fileName, frontend),
    resolvedPath: fs.realpathSync(source.fileName).replaceAll("\\", "/"),
    textBytes: Buffer.byteLength(source.text),
    normalizedLfSha256: hash(source.text.replaceAll("\r\n", "\n")),
    declaration: source.isDeclarationFile,
  })).sort((left, right) => left.path.localeCompare(right.path));
  const packageNames = new Set(sourceFiles.filter((source) => source.path.startsWith("node_modules/")).map((source) => {
    const pieces = source.path.split("/");
    return pieces[1].startsWith("@") ? pieces.slice(1, 3).join("/") : pieces[1];
  }));
  packageNames.add("typescript");
  const packages = [...packageNames].sort().map((name) => {
    const packagePath = frontend + "/node_modules/" + name + "/package.json";
    const content = fs.readFileSync(packagePath);
    const metadata = JSON.parse(content);
    return { name, version: metadata.version, resolvedPath: fs.realpathSync(packagePath), sha256: hash(content) };
  });
  fingerprints[label] = {
    frontend,
    rootFiles: parsed.fileNames.map((name) => normalizePath(name, frontend)).sort(),
    compilerOptions: Object.fromEntries(Object.entries(parsed.options).filter(([key]) => key !== "configFile")),
    projectReferences: parsed.projectReferences || [],
    sourceFiles,
    packages,
    nodeModulesResolved: fs.realpathSync(frontend + "/node_modules"),
    configHash: hash(fs.readFileSync(frontend + "/tsconfig.json").toString().replaceAll("\r\n", "\n")),
    packageLockHash: hash(fs.readFileSync(frontend + "/package-lock.json").toString().replaceAll("\r\n", "\n")),
    parsedMemory: process.memoryUsage(),
  };
  program = null;
  if (global.gc) global.gc();
  fingerprints[label].afterGcMemory = process.memoryUsage();
}
const leftFiles = new Map(fingerprints.root.sourceFiles.map((source) => [source.path, source]));
const rightFiles = new Map(fingerprints.reviewer.sourceFiles.map((source) => [source.path, source]));
const differences = [...new Set([...leftFiles.keys(), ...rightFiles.keys()])].filter((name) => leftFiles.get(name)?.normalizedLfSha256 !== rightFiles.get(name)?.normalizedLfSha256);
if (hash(fs.readFileSync(roots.root + "/tsconfig.tsbuildinfo")) !== protectedHash) throw new Error("Protected tsbuildinfo changed during read-only probe");
const result = {
  startedUtc,
  endedUtc: new Date().toISOString(),
  nodeVersion: process.version,
  typescriptVersion: ts.version,
  execArgv: process.execArgv,
  heapStatistics: v8.getHeapStatistics(),
  heapSpaceStatistics: v8.getHeapSpaceStatistics(),
  typeCheckingPerformed: false,
  emitPerformed: false,
  protectedTsbuildinfoSha256: protectedHash,
  fingerprints,
  normalizedSourceDifferences: differences,
};
fs.writeFileSync(path.join(run, "input_probe.json"), JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify({ nodeVersion: result.nodeVersion, typescriptVersion: ts.version, inputCounts: Object.fromEntries(Object.entries(fingerprints).map(([label, input]) => [label, { rootFiles: input.rootFiles.length, sourceFiles: input.sourceFiles.length, declarationFiles: input.sourceFiles.filter((source) => source.declaration).length, parsedMemory: input.parsedMemory, afterGcMemory: input.afterGcMemory }])), normalizedSourceDifferences: differences, typeCheckingPerformed: false, protectedTsbuildinfoSha256: protectedHash }));
