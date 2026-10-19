"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// tests/r17_purl_profile_cases.ts
var r17_purl_profile_cases_exports = {};
__export(r17_purl_profile_cases_exports, {
  purlProfileCases: () => purlProfileCases
});
module.exports = __toCommonJS(r17_purl_profile_cases_exports);
var purlProfileCases = [
  { name: "original encoded absolute version", purl: "pkg:generic/synthetic@%2Fhome%2Freview-private%2F.env", expected: false },
  { name: "original encoded at in version", purl: "pkg:pypi/synthetic@review-secret%40private", expected: false },
  { name: "original double encoded slash", purl: "pkg:generic/synthetic@%252Fhome%252Freview-private", expected: false },
  { name: "plain version slash", purl: "pkg:generic/synthetic@/home/review-private", expected: false },
  { name: "plain nested version slash", purl: "pkg:generic/synthetic@release/private", expected: false },
  { name: "double encoded at", purl: "pkg:pypi/synthetic@review%2540private", expected: false },
  { name: "lowercase escape slash", purl: "pkg:generic/synthetic@%2fprivate", expected: false },
  { name: "plain space", purl: "pkg:generic/synthetic@review private", expected: false },
  { name: "encoded space", purl: "pkg:generic/synthetic@review%20private", expected: false },
  { name: "plain tab", purl: "pkg:generic/synthetic@review	private", expected: false },
  { name: "encoded tab", purl: "pkg:generic/synthetic@review%09private", expected: false },
  { name: "plain newline", purl: "pkg:generic/synthetic@review\n", expected: false },
  { name: "encoded NUL", purl: "pkg:generic/synthetic@review%00private", expected: false },
  { name: "plain backslash", purl: "pkg:generic/synthetic@review\\private", expected: false },
  { name: "encoded backslash", purl: "pkg:generic/synthetic@review%5Cprivate", expected: false },
  { name: "residual percent", purl: "pkg:generic/synthetic@review%25private", expected: false },
  { name: "encoded fake URI", purl: "pkg:generic/synthetic@https%3A%2F%2Fsynthetic%3Asynthetic%40example.com", expected: false },
  { name: "twice encoded fake URI", purl: "pkg:generic/synthetic@https%253A%252F%252Fexample.com", expected: false },
  { name: "plain fake URI", purl: "pkg:generic/synthetic@file:///review-private", expected: false },
  { name: "qualifier", purl: "pkg:generic/synthetic@1.0?token=synthetic", expected: false },
  { name: "subpath", purl: "pkg:generic/synthetic@1.0#private", expected: false },
  { name: "encoded qualifier", purl: "pkg:generic/synthetic@1.0%3Ftoken=synthetic", expected: false },
  { name: "ordinary package version", purl: "pkg:pypi/synthetic@1.0", expected: true },
  { name: "version omitted", purl: "pkg:generic/synthetic", expected: true },
  { name: "raw npm scope no version", purl: "pkg:npm/@scope/synthetic", expected: true },
  { name: "raw npm scope with version", purl: "pkg:npm/@scope/synthetic@1.2.3", expected: true },
  { name: "encoded npm scope no version", purl: "pkg:npm/%40scope/synthetic", expected: true },
  { name: "encoded npm scope with version", purl: "pkg:npm/%40scope/synthetic@1.2.3", expected: true },
  { name: "Unicode name", purl: "pkg:generic/\u5408\u6210\u7EC4\u4EF6@1.0", expected: true },
  { name: "encoded Unicode name", purl: "pkg:generic/%E5%90%88%E6%88%90%E7%BB%84%E4%BB%B6@1.0", expected: true },
  { name: "Unicode version", purl: "pkg:generic/synthetic@\u7248\u672C\u4E00", expected: true },
  { name: "encoded Unicode version", purl: "pkg:generic/synthetic@%E7%89%88%E6%9C%AC%E4%B8%80", expected: true },
  { name: "encoded at belongs to name", purl: "pkg:generic/synthetic%40package@1.0", expected: true },
  { name: "build version", purl: "pkg:generic/synthetic@1.0+build", expected: true },
  { name: "case folded type", purl: "pkg:PyPI/synthetic@1.0", expected: true },
  { name: "wrong case scheme", purl: "PKG:pypi/synthetic@1.0", expected: false }
];
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  purlProfileCases
});
