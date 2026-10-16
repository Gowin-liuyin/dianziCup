/** Synthetic uploads exercise the real API without claiming real asset or source evidence. */
export function cyclonedxInput(version: string | null = "1.0.0", dependency = true, componentCount = 2): Buffer {
  return Buffer.from(" \n" + JSON.stringify({
    bomFormat: "CycloneDX", specVersion: "1.6", version: 1,
    components: [
      { type: "library", name: "synthetic-root", "bom-ref": "root", purl: "pkg:npm/%40synthetic/root" + (version === null ? "" : `@${version}`), ...(version === null ? {} : { version }), hashes: [{ alg: "SHA-256", content: "a".repeat(64) }] },
      { type: "library", name: "synthetic-child", "bom-ref": "child" },
      ...Array.from({ length: componentCount - 2 }, (_, index) => ({ type: "library", name: `synthetic-extra-${index}`, "bom-ref": `extra-${index}` })),
    ],
    dependencies: [{ ref: "root", dependsOn: dependency ? ["child"] : [] }],
    compositions: [{ aggregate: "unknown", assemblies: ["root"] }],
    "file:///synthetic-private-location": "synthetic non-public payload",
  }) + "\r\n", "utf8");
}

export function spdxInput(): Buffer {
  return Buffer.from(JSON.stringify({
    spdxVersion: "SPDX-2.3", SPDXID: "SPDXRef-DOCUMENT", name: "synthetic browser SPDX",
    documentNamespace: "https://example.com/synthetic-browser", dataLicense: "CC0-1.0",
    creationInfo: { created: "2026-10-16T00:00:00Z", creators: ["Tool: synthetic-browser"] },
    packages: [{ SPDXID: "SPDXRef-A", name: "synthetic-spdx", versionInfo: "2.0", downloadLocation: "NOASSERTION", externalRefs: [{ referenceCategory: "PACKAGE-MANAGER", referenceType: "purl", referenceLocator: "pkg:pypi/synthetic-spdx@2.0" }] }],
    relationships: [{ spdxElementId: "SPDXRef-DOCUMENT", relationshipType: "DESCRIBES", relatedSpdxElement: "SPDXRef-A" }],
    externalDocumentRefs: [
      { externalDocumentId: "DocumentRef-Public", spdxDocument: "https://example.com/synthetic.spdx.json", checksum: { algorithm: "SHA256", checksumValue: "b".repeat(64) } },
      { externalDocumentId: "DocumentRef-Hidden", spdxDocument: "file:///synthetic-private-location", checksum: { algorithm: "SHA256", checksumValue: "c".repeat(64) } },
    ],
  }), "utf8");
}
