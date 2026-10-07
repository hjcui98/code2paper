/** C01 byte decoding and schema consumption. Semantic digests remain Python-owned. */
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };
export const MAX_WIRE_BYTES = 1 << 20;

export class WireError extends Error {
  readonly code: string;
  constructor(code: string) { super(code); this.code = code; this.name = 'WireError'; }
}

function fail(code: string): never { throw new WireError(code); }

function validUnicode(value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++index);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail('invalid_unicode');
    } else if (unit >= 0xdc00 && unit <= 0xdfff) fail('invalid_unicode');
  }
}

const numberLexemes = new WeakMap<object, ReadonlyMap<string, string>>();
const childPointer = (pointer: string, key: string): string => `${pointer}/${key.replace(/~/g, '~0').replace(/\//g, '~1')}`;

/** Preserve numeric spelling separately; it must not enter canonical JSON. */
function decodeDocument(raw: Uint8Array | string): { value: JsonValue; lexemes: ReadonlyMap<string, string> } {
  if (typeof raw === 'string') validUnicode(raw);
  const bytes = typeof raw === 'string' ? Buffer.from(raw, 'utf8') : raw;
  if (bytes.byteLength > MAX_WIRE_BYTES) fail('frame_too_large');
  let text: string;
  try { text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); }
  catch { return fail('invalid_json'); }
  let cursor = 0;
  const lexemes = new Map<string, string>();
  const space = (): void => { while (/[\x20\t\r\n]/.test(text[cursor] ?? '') && cursor < text.length) cursor += 1; };
  const string = (): string => {
    if (text[cursor] !== '"') fail('invalid_json');
    const start = cursor++;
    let escaped = false;
    while (cursor < text.length) {
      const character = text[cursor++];
      if (!escaped && character === '"') {
        let result: unknown;
        try { result = JSON.parse(text.slice(start, cursor)); } catch { return fail('invalid_json'); }
        if (typeof result !== 'string') return fail('invalid_json');
        validUnicode(result);
        return result;
      }
      if (!escaped && character === '\\') escaped = true;
      else escaped = false;
    }
    return fail('invalid_json');
  };
  const value = (depth: number, pointer: string): JsonValue => {
    if (depth > 256) fail('invalid_json');
    space();
    const character = text[cursor];
    if (character === '"') return string();
    if (character === '{') {
      cursor += 1;
      const result: JsonObject = {};
      const keys = new Set<string>();
      space();
      if (text[cursor] === '}') { cursor += 1; return result; }
      while (cursor < text.length) {
        space();
        const key = string();
        if (keys.has(key)) fail('duplicate_json_key');
        keys.add(key);
        space();
        if (text[cursor++] !== ':') fail('invalid_json');
        Object.defineProperty(result, key, { value: value(depth + 1, childPointer(pointer, key)), enumerable: true, writable: true, configurable: true });
        space();
        const ending = text[cursor++];
        if (ending === '}') return result;
        if (ending !== ',') fail('invalid_json');
      }
      return fail('invalid_json');
    }
    if (character === '[') {
      cursor += 1;
      const result: JsonValue[] = [];
      space();
      if (text[cursor] === ']') { cursor += 1; return result; }
      while (cursor < text.length) {
        result.push(value(depth + 1, childPointer(pointer, String(result.length))));
        space();
        const ending = text[cursor++];
        if (ending === ']') return result;
        if (ending !== ',') fail('invalid_json');
      }
      return fail('invalid_json');
    }
    for (const [token, result] of [['true', true], ['false', false], ['null', null]] as const) {
      if (text.startsWith(token, cursor)) { cursor += token.length; return result; }
    }
    if (/^(?:NaN|Infinity|-Infinity)/.test(text.slice(cursor))) fail('non_finite_number');
    const number = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(cursor))?.[0];
    if (number === undefined) return fail('invalid_json');
    cursor += number.length;
    const result = Number(number);
    if (!Number.isFinite(result)) fail('non_finite_number');
    if (!/[.eE]/.test(number) && !Number.isSafeInteger(result)) fail('integer_out_of_range');
    lexemes.set(pointer, number);
    return result;
  };
  const result = value(0, '');
  space();
  if (cursor !== text.length) fail('invalid_json');
  if (result !== null && typeof result === 'object') numberLexemes.set(result, lexemes);
  return { value: result, lexemes };
}

/** JSON.parse cannot detect duplicate keys; decode before any object is collapsed. */
export function decodeWire(raw: Uint8Array | string): JsonValue { return decodeDocument(raw).value; }

export function isObject(value: JsonValue | undefined): value is JsonObject {
  return value !== undefined && value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function immutable<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    for (const item of Object.values(value)) immutable(item);
    Object.freeze(value);
  }
  return value;
}

const annotations = new Set(['title', 'description', 'default', 'examples', '$schema', '$id', '$defs', 'definitions', 'discriminator']);
const constraints = new Set(['$ref', 'type', 'const', 'enum', 'oneOf', 'anyOf', 'allOf', 'properties', 'required', 'additionalProperties',
  'items', 'minItems', 'maxItems', 'minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum',
  'x-c2p-character-rule']);

/** Compiled consumer of Python's versioned rule; no host Unicode regex tables. */
export const IDENTIFIER_CHARACTER_RULE = immutable({
  schema_version: 'WireCharacterRulesV1', rule: 'unicode-white-space-nonblank/1', length_unit: 'unicode-code-point',
  pattern: String.raw`[^\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]`,
  whitespace_ranges: [[9, 13], [32, 32], [133, 133], [160, 160], [5760, 5760], [8192, 8202],
    [8232, 8233], [8239, 8239], [8287, 8287], [12288, 12288]],
});
const DIGEST_PATTERN = '^sha256:[0-9a-f]{64}$';

function inspectPattern(node: JsonObject): void {
  const pattern = node['pattern']; const rule = node['x-c2p-character-rule'];
  if (rule !== undefined && (rule !== IDENTIFIER_CHARACTER_RULE.rule || pattern !== IDENTIFIER_CHARACTER_RULE.pattern)) fail('schema_unsupported');
  if (pattern !== undefined && !(pattern === DIGEST_PATTERN && rule === undefined)
    && !(pattern === IDENTIFIER_CHARACTER_RULE.pattern && rule === IDENTIFIER_CHARACTER_RULE.rule)) fail('schema_unsupported');
}

function matchesPattern(value: string, node: JsonObject): boolean {
  if (node['x-c2p-character-rule'] === IDENTIFIER_CHARACTER_RULE.rule) {
    return [...value].some(character => {
      const point = character.codePointAt(0)!;
      return !IDENTIFIER_CHARACTER_RULE.whitespace_ranges.some(range => point >= range[0]! && point <= range[1]!);
    });
  }
  if (node['pattern'] === DIGEST_PATTERN) {
    return value.length === 71 && value.startsWith('sha256:')
      && [...value.slice(7)].every(character => (character >= '0' && character <= '9') || (character >= 'a' && character <= 'f'));
  }
  return true;
}

function equal(left: JsonValue, right: JsonValue): boolean {
  if (left === right) return true;
  if (Array.isArray(left) && Array.isArray(right)) return left.length === right.length && left.every((item, index) => equal(item, right[index]!));
  if (isObject(left) && isObject(right)) {
    const keys = Object.keys(left);
    return keys.length === Object.keys(right).length && keys.every(key => Object.hasOwn(right, key) && equal(left[key]!, right[key]!));
  }
  return false;
}

/** Consume the exported Python schema without flattening nullable/union/extra rules. */
export function validateWireSchema(value: JsonValue, schema: JsonObject): void {
  validateSchema(value, schema, value !== null && typeof value === 'object' ? numberLexemes.get(value) : undefined);
}

function validateSchema(value: JsonValue, schema: JsonObject, lexemes?: ReadonlyMap<string, string>): void {
  const visited = new Set<JsonObject>();
  const resolve = (node: JsonObject): JsonObject => {
    if (node['$ref'] === undefined) return node;
    const reference = node['$ref'];
    if (typeof reference !== 'string' || !reference.startsWith('#/')) return fail('schema_unsupported');
    let result: JsonValue = schema;
    for (const part of reference.slice(2).split('/')) {
      if (!isObject(result)) return fail('schema_unsupported');
      result = result[part.replace(/~1/g, '/').replace(/~0/g, '~')] ?? fail('schema_unsupported');
    }
    if (!isObject(result)) return fail('schema_unsupported');
    return result;
  };
  const inspect = (node: JsonObject): void => {
    if (visited.has(node)) return;
    visited.add(node);
    for (const key of Object.keys(node)) if (!annotations.has(key) && !constraints.has(key)) fail('schema_unsupported');
    inspectPattern(node);
    if (node['$ref'] !== undefined) inspect(resolve(node));
    for (const keyword of ['oneOf', 'anyOf', 'allOf']) {
      const branches = node[keyword];
      if (branches === undefined) continue;
      if (!Array.isArray(branches) || branches.length === 0) fail('schema_unsupported');
      for (const branch of branches) { if (!isObject(branch)) fail('schema_unsupported'); inspect(branch); }
    }
    if (isObject(node['properties'])) for (const property of Object.values(node['properties'])) {
      if (!isObject(property)) fail('schema_unsupported'); inspect(property);
    }
    if (isObject(node['items'])) inspect(node['items']);
    if (isObject(node['additionalProperties'])) inspect(node['additionalProperties']);
  };
  inspect(schema);
  const accepts = (item: JsonValue, node: JsonObject, depth: number, pointer: string): boolean => {
    if (depth > 256) return false;
    if (node['$ref'] !== undefined && !accepts(item, resolve(node), depth + 1, pointer)) return false;
    for (const keyword of ['oneOf', 'anyOf', 'allOf']) {
      const branches = node[keyword];
      if (!Array.isArray(branches)) continue;
      const count = branches.filter(branch => isObject(branch) && accepts(item, branch, depth + 1, pointer)).length;
      if ((keyword === 'oneOf' && count !== 1) || (keyword === 'anyOf' && count === 0) || (keyword === 'allOf' && count !== branches.length)) return false;
    }
    if (node['const'] !== undefined && !equal(item, node['const'])) return false;
    if (Array.isArray(node['enum']) && !node['enum'].some(option => equal(item, option))) return false;
    const type = node['type'];
    if (type !== undefined) {
      const matches = (name: JsonValue): boolean => {
        switch (name) {
          case 'object': return isObject(item);
          case 'array': return Array.isArray(item);
          case 'null': return item === null;
          case 'integer': return typeof item === 'number' && Number.isSafeInteger(item)
            && !/[.eE]/.test(lexemes?.get(pointer) ?? '');
          case 'number': return typeof item === 'number' && Number.isFinite(item);
          case 'string': return typeof item === 'string';
          case 'boolean': return typeof item === 'boolean';
          default: return fail('schema_unsupported');
        }
      };
      if (!(Array.isArray(type) ? type.some(matches) : matches(type))) return false;
    }
    if (typeof item === 'string') {
      const length = [...item].length;
      if (typeof node['minLength'] === 'number' && length < node['minLength']) return false;
      if (typeof node['maxLength'] === 'number' && length > node['maxLength']) return false;
      if (!matchesPattern(item, node)) return false;
    }
    if (typeof item === 'number') {
      if (typeof node['minimum'] === 'number' && item < node['minimum']) return false;
      if (typeof node['maximum'] === 'number' && item > node['maximum']) return false;
      if (typeof node['exclusiveMinimum'] === 'number' && item <= node['exclusiveMinimum']) return false;
      if (typeof node['exclusiveMaximum'] === 'number' && item >= node['exclusiveMaximum']) return false;
    }
    if (Array.isArray(item)) {
      if (typeof node['minItems'] === 'number' && item.length < node['minItems']) return false;
      if (typeof node['maxItems'] === 'number' && item.length > node['maxItems']) return false;
      if (isObject(node['items']) && !item.every((entry, index) => accepts(entry, node['items'] as JsonObject, depth + 1, childPointer(pointer, String(index))))) return false;
    }
    if (isObject(item)) {
      if (Array.isArray(node['required']) && node['required'].some(key => typeof key !== 'string' || !Object.hasOwn(item, key))) return false;
      const properties = isObject(node['properties']) ? node['properties'] : {};
      for (const [key, entry] of Object.entries(item)) {
        const rule = properties[key];
        const child = childPointer(pointer, key);
        if (isObject(rule)) { if (!accepts(entry, rule, depth + 1, child)) return false; }
        else if (node['additionalProperties'] === false) return false;
        else if (isObject(node['additionalProperties']) && !accepts(entry, node['additionalProperties'], depth + 1, child)) return false;
      }
    }
    return true;
  };
  if (!accepts(value, schema, 0, '')) fail('schema_invalid');
}

export function parseWire(raw: Uint8Array | string, schema: JsonObject): JsonValue {
  const document = decodeDocument(raw);
  validateSchema(document.value, schema, document.lexemes);
  return immutable(document.value);
}
