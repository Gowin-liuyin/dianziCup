import { recommendationSchemaText } from "./recommendation-wire-schema";
import { ApiProblem } from "../../api/client";

const schemaDocument: unknown = JSON.parse(recommendationSchemaText);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const dateTimePattern = /^(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function definition(name: string): Record<string, unknown> {
  if (!isRecord(schemaDocument) || !isRecord(schemaDocument.$defs)) return invalid();
  const value = schemaDocument.$defs[name]; return isRecord(value) ? value : invalid();
}
export function isRecommendationIdentifier(value: string): boolean { return uuidPattern.test(value); }
function checkFormat(value: string, format: unknown): void {
  if (format === "uuid" && !uuidPattern.test(value)) return invalid();
  if (format === "date-time") {
    const parts = dateTimePattern.exec(value);
    if (parts === null || !Number.isFinite(Date.parse(value))) return invalid();
    const year = Number(parts[1]); const month = Number(parts[2]); const day = Number(parts[3]);
    if (month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate()) return invalid();
  }
  if (format === "uri") {
    let uri: URL; try { uri = new URL(value); } catch { return invalid(); }
    if (!uri.hostname || (uri.protocol !== "https:" && uri.protocol !== "http:") || uri.username || uri.password) return invalid();
  }
}

function validate(value: unknown, schema: Record<string, unknown>, strictDefaults: boolean, budget: { remaining: number }, depth = 0): unknown {
  if (--budget.remaining < 0 || depth > 32) return invalid();
  if (typeof schema.$ref === "string") {
    if (!schema.$ref.startsWith("#/$defs/")) return invalid();
    return validate(value, definition(schema.$ref.slice(8)), strictDefaults, budget, depth + 1);
  }
  if (Object.hasOwn(schema, "const") && value !== schema.const) return invalid();
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) return invalid();
  if (schema.type === "null" && value !== null) return invalid();
  if (schema.type === "boolean" && typeof value !== "boolean") return invalid();
  if (schema.type === "integer" || schema.type === "number") {
    if (typeof value !== "number" || !Number.isFinite(value) || (schema.type === "integer" && !Number.isInteger(value))) return invalid();
    if ((typeof schema.minimum === "number" && value < schema.minimum) || (typeof schema.maximum === "number" && value > schema.maximum)) return invalid();
  }
  if (schema.type === "string") {
    if (typeof value !== "string") return invalid();
    const length = [...value].length;
    if ((typeof schema.minLength === "number" && length < schema.minLength) || (typeof schema.maxLength === "number" && length > schema.maxLength)) return invalid();
    if (typeof schema.pattern === "string" && !new RegExp(schema.pattern).test(value)) return invalid();
    checkFormat(value, schema.format);
  }
  let normalized: unknown = value;
  if (schema.type === "string" && schema.format === "uuid" && typeof value === "string") normalized = value.toLowerCase();
  if (schema.type === "array" || Object.hasOwn(schema, "minItems") || Object.hasOwn(schema, "maxItems")) {
    if (!Array.isArray(value)) return invalid();
    if ((typeof schema.minItems === "number" && value.length < schema.minItems) || (typeof schema.maxItems === "number" && value.length > schema.maxItems)) return invalid();
    if (schema.uniqueItems === true && new Set(value.map((item) => JSON.stringify(item))).size !== value.length) return invalid();
    if (isRecord(schema.items)) { const itemSchema = schema.items; normalized = value.map((item) => validate(item, itemSchema, strictDefaults, budget, depth + 1)); }
    if (schema.uniqueItems === true && Array.isArray(normalized) && new Set(normalized.map((item) => JSON.stringify(item))).size !== normalized.length) return invalid();
  }
  if (schema.type === "object" || isRecord(schema.properties) || Array.isArray(schema.required)) {
    if (!isRecord(value)) return invalid();
    if (Array.isArray(schema.required) && schema.required.some((key) => typeof key !== "string" || !Object.hasOwn(value, key))) return invalid();
    const properties = isRecord(schema.properties) ? schema.properties : {};
    if (schema.additionalProperties === false && Object.keys(value).some((key) => !Object.hasOwn(properties, key))) return invalid();
    const object = { ...value };
    for (const [name, property] of Object.entries(properties)) {
      if (!isRecord(property)) return invalid();
      if (!Object.hasOwn(value, name)) {
        if (strictDefaults) return invalid();
        if (Object.hasOwn(property, "default")) object[name] = structuredClone(property.default);
        else continue;
      }
      object[name] = validate(object[name], property, strictDefaults, budget, depth + 1);
    }
    if (isRecord(schema.additionalProperties)) { const propertySchema = schema.additionalProperties; for (const name of Object.keys(value)) if (!Object.hasOwn(properties, name)) object[name] = validate(value[name], propertySchema, strictDefaults, budget, depth + 1); }
    normalized = object;
  }
  const alternatives = Array.isArray(schema.anyOf) ? schema.anyOf : schema.oneOf;
  if (Array.isArray(alternatives)) {
    const successes: unknown[] = [];
    for (const alternative of alternatives) {
      if (!isRecord(alternative)) return invalid();
      try { successes.push(validate(normalized, alternative, strictDefaults, budget, depth + 1)); } catch (failure: unknown) { if (!(failure instanceof ApiProblem)) throw failure; }
    }
    if (successes.length === 0 || (Array.isArray(schema.oneOf) && successes.length !== 1)) return invalid();
    normalized = successes[0];
  }
  return normalized;
}

/** Schema 声明的 defaults 在严格类型守卫前补齐，未知字段和格式不一致始终拒绝。 */
export function normalizeDefinition(value: unknown, name: string): unknown { return validate(value, definition(name), false, { remaining: 100_000 }); }
export function matchesDefinition(value: unknown, name: string): boolean {
  try { validate(value, definition(name), true, { remaining: 100_000 }); return true; } catch (failure: unknown) { if (failure instanceof ApiProblem) return false; throw failure; }
}
