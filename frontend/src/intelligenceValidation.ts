import { wireSchemas } from './intelligence.validation.generated'

// Validate wire structure before React touches nested fields. Domain eligibility remains
// a separate check; schema validity never upgrades evidence or provenance.
type Schema = Record<string, any>
function matches(schema: Schema, value: unknown): boolean {
  if (schema.$ref) return matches((wireSchemas as Record<string, Schema>)[schema.$ref.split('/').at(-1)], value)
  if (schema.anyOf) return schema.anyOf.some((s: Schema) => matches(s, value))
  if (schema.allOf && !schema.allOf.every((s: Schema) => matches(s, value))) return false
  if ('const' in schema && value !== schema.const) return false
  if (schema.enum && !schema.enum.includes(value)) return false
  if (schema.type === 'null') return value === null
  if (schema.type === 'object') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false
    const object = value as Record<string, unknown>
    if ((schema.required || []).some((key: string) => !Object.hasOwn(object, key))) return false
    return Object.entries(object).every(([key, item]) => schema.properties?.[key]
      ? matches(schema.properties[key], item) : schema.additionalProperties === false ? false
        : typeof schema.additionalProperties === 'object' ? matches(schema.additionalProperties, item) : true)
  }
  if (schema.type === 'array') return Array.isArray(value)
    && (schema.minItems === undefined || value.length >= schema.minItems)
    && (schema.maxItems === undefined || value.length <= schema.maxItems)
    && value.every(item => matches(schema.items || {}, item))
  if (schema.type === 'string') return typeof value === 'string'
    && (schema.minLength === undefined || Array.from(value).length >= schema.minLength)
    && (schema.maxLength === undefined || Array.from(value).length <= schema.maxLength)
    && (!schema.pattern || new RegExp(schema.pattern).test(value))
    && (schema.format !== 'date-time' || Number.isFinite(Date.parse(value)))
  if (schema.type === 'number' || schema.type === 'integer') return typeof value === 'number' && Number.isFinite(value)
    && (schema.type !== 'integer' || Number.isInteger(value))
    && (schema.minimum === undefined || value >= schema.minimum) && (schema.maximum === undefined || value <= schema.maximum)
    && (schema.exclusiveMinimum === undefined || value > schema.exclusiveMinimum)
  if (schema.type === 'boolean') return typeof value === 'boolean'
  return true
}
export function validWire(name: 'BriefingView' | 'EventDetailView' | 'SnapshotPage' | 'VisitView', value: unknown): boolean {
  try { return matches((wireSchemas as Record<string, Schema>)[name], value) } catch { return false }
}
