const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('D:/dianzi/frontend/node_modules/typescript');

const sourceRoot = 'D:/wt/r17-root-investigation-sdk-review1';
const outputRoot = 'D:/dianzi/reports/runs/r17_root_junit_provenance_review1_20261017';
const xmlPath = 'D:/dianzi/reports/runs/recovery_reviewed_integration_20261016/frontend_batch10_unit.xml';
const withheldPath = path.join(sourceRoot, 'reports/runs/recovery_reviewed_integration_20261016/frontend_batch10_xml_withheld.json');
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex');

function xmlDecode(value) {
  return value.replace(/&#x([\da-f]+);|&#(\d+);|&(quot|apos|lt|gt|amp);/gi, (_, hex, decimal, named) => {
    if (hex) return String.fromCodePoint(Number.parseInt(hex, 16));
    if (decimal) return String.fromCodePoint(Number.parseInt(decimal, 10));
    return { quot: '"', apos: "'", lt: '<', gt: '>', amp: '&' }[named.toLowerCase()];
  });
}

function attributes(tag) {
  return Object.fromEntries(Array.from(tag.matchAll(/([\w:.-]+)="([^"]*)"/g), match => [match[1], xmlDecode(match[2])]));
}

function sourceFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const location = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(location);
    return /\.[cm]?tsx?$/.test(entry.name) ? [location] : [];
  });
}

function ancestorKinds(node) {
  const kinds = [];
  for (let ancestor = node.parent; ancestor && kinds.length < 8; ancestor = ancestor.parent) {
    kinds.push(ts.SyntaxKind[ancestor.kind]);
  }
  return kinds;
}

function callTestMetadata(node, source) {
  for (let ancestor = node.parent; ancestor; ancestor = ancestor.parent) {
    if (!ts.isCallExpression(ancestor)) continue;
    const callee = ancestor.expression.getText(source);
    if (!/^(?:it|test)(?:\.[A-Za-z]+)*$/.test(callee)) continue;
    const first = ancestor.arguments[0];
    return {
      call_line: source.getLineAndCharacterOfPosition(ancestor.getStart(source)).line + 1,
      callee,
      test_name_sha256: first && ts.isStringLiteralLike(first) ? sha256(first.text) : null,
    };
  }
  return null;
}

function nodeLocation(node, source, filePath) {
  const position = source.getLineAndCharacterOfPosition(node.getStart(source));
  const property = ts.isPropertyAssignment(node.parent) ? node.parent.name : null;
  return {
    path: path.relative(sourceRoot, filePath).replaceAll('\\', '/'),
    line: position.line + 1,
    column: position.character + 1,
    node_kind: ts.SyntaxKind[node.kind],
    ancestor_kinds: ancestorKinds(node),
    property_name_sha256: property ? sha256(property.getText(source)) : null,
    test: callTestMetadata(node, source),
  };
}

function calleeName(expression) {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) return `${calleeName(expression.expression)}.${expression.name.text}`;
  if (ts.isCallExpression(expression)) return `${calleeName(expression.expression)}()`;
  if (ts.isArrowFunction(expression)) return '<arrow>';
  return `<${ts.SyntaxKind[expression.kind]}>`;
}

function astCalls(root, source) {
  const calls = [];
  function visit(node) {
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) calls.push({
      line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1,
      kind: ts.SyntaxKind[node.kind],
      callee: calleeName(node.expression),
      argument_kinds: Array.from(node.arguments || [], argument => ts.SyntaxKind[argument.kind]),
    });
    ts.forEachChild(node, visit);
  }
  visit(root);
  return calls;
}

function eachFlow(literal, source, filePath, junitName) {
  const table = literal.parent;
  const each = table && table.parent;
  const test = each && each.parent;
  if (!ts.isArrayLiteralExpression(table) || !ts.isCallExpression(each) || !ts.isCallExpression(test) || test.expression !== each || calleeName(each.expression) !== 'it.each') return null;
  const callback = test.arguments.find(argument => ts.isArrowFunction(argument) || ts.isFunctionExpression(argument));
  if (!callback) return null;
  const parameterNames = callback.parameters.map(parameter => ts.isIdentifier(parameter.name) ? parameter.name.text : '<binding-pattern>');
  const flows = [];
  function visit(node) {
    if (ts.isIdentifier(node) && parameterNames.includes(node.text) && !callback.parameters.some(parameter => parameter.name === node)) {
      for (let ancestor = node.parent; ancestor && ancestor !== callback; ancestor = ancestor.parent) {
        if (!ts.isCallExpression(ancestor)) continue;
        const argumentIndex = ancestor.arguments.findIndex(argument => node.pos >= argument.pos && node.end <= argument.end);
        if (argumentIndex < 0) continue;
        flows.push({ parameter: node.text, line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1, call: calleeName(ancestor.expression), argument_index: argumentIndex });
        break;
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(callback.body);
  const directCallees = new Set(flows.map(flow => flow.call));
  const titleTemplate = ts.isStringLiteralLike(test.arguments[0]) ? test.arguments[0].text : null;
  const expandedTitle = titleTemplate && titleTemplate.replace('%s', literal.text);
  const importedTargets = [];
  for (const statement of source.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause || !statement.importClause.namedBindings || !ts.isNamedImports(statement.importClause.namedBindings) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
    const relativeModule = statement.moduleSpecifier.text;
    if (!relativeModule.startsWith('./') && !relativeModule.startsWith('../')) continue;
    for (const specifier of statement.importClause.namedBindings.elements) {
      if (!directCallees.has(specifier.name.text)) continue;
      const importedName = specifier.propertyName ? specifier.propertyName.text : specifier.name.text;
      const base = path.resolve(path.dirname(filePath), relativeModule);
      const targetPath = [base + '.ts', base + '.tsx', path.join(base, 'index.ts')].find(candidate => fs.existsSync(candidate));
      if (!targetPath) continue;
      const targetText = fs.readFileSync(targetPath, 'utf8');
      const targetSource = ts.createSourceFile(targetPath, targetText, ts.ScriptTarget.Latest, true);
      const target = targetSource.statements.find(candidate => ts.isFunctionDeclaration(candidate) && candidate.name && candidate.name.text === importedName);
      const targetCalls = target ? astCalls(target, targetSource) : [];
      const localHelpers = targetCalls.flatMap(call => {
        const helper = targetSource.statements.find(candidate => ts.isFunctionDeclaration(candidate) && candidate.name && candidate.name.text === call.callee);
        return helper ? [{ name: call.callee, line: targetSource.getLineAndCharacterOfPosition(helper.getStart(targetSource)).line + 1, calls: astCalls(helper, targetSource) }] : [];
      });
      const allCalls = targetCalls.concat(localHelpers.flatMap(helper => helper.calls));
      importedTargets.push({
        import_binding: specifier.name.text,
        imported_name: importedName,
        path: path.relative(sourceRoot, targetPath).replaceAll('\\', '/'),
        source_sha256: sha256(targetText),
        function_line: target ? targetSource.getLineAndCharacterOfPosition(target.getStart(targetSource)).line + 1 : null,
        calls: targetCalls,
        local_helper_functions: localHelpers,
        network_or_credential_client_calls: allCalls.filter(call => /^(?:fetch|axios|http|https|net|tls|process|require|connect|Pool|Client)(?:$|\.|\()/.test(call.callee)),
        directly_contains_throw_statement: target ? containsKind(target, ts.SyntaxKind.ThrowStatement) : null,
      });
    }
  }
  return {
    table_kind: ts.SyntaxKind[table.kind],
    row_index: table.elements.indexOf(literal),
    test_call_line: source.getLineAndCharacterOfPosition(test.getStart(source)).line + 1,
    test_title_template_sha256: ts.isStringLiteralLike(test.arguments[0]) ? sha256(test.arguments[0].text) : null,
    expanded_test_title_sha256: expandedTitle ? sha256(expandedTitle) : null,
    junit_name_ends_with_table_expansion: expandedTitle ? junitName.endsWith(expandedTitle) : null,
    callback_parameter_names: parameterNames,
    callback_calls: astCalls(callback.body, source),
    parameter_argument_flows: flows,
    imported_targets: importedTargets,
    fixture_origin: 'compile_time_string_literal_in_it_each_input_array',
  };
}

function containsKind(root, kind) {
  let result = false;
  function visit(node) { if (node.kind === kind) result = true; ts.forEachChild(node, visit); }
  visit(root);
  return result;
}

function uriShape(value) {
  try {
    const candidate = new URL(value);
    const hostname = candidate.hostname.toLowerCase();
    return {
      parses_as_url: true,
      has_username: candidate.username.length > 0,
      has_password: candidate.password.length > 0,
      host_is_reserved_example_or_test: /(?:^|\.)(?:example\.com|example\.net|example\.org|test|invalid)$/.test(hostname) || ['localhost', 'example'].includes(hostname),
      hostname_sha256: sha256(hostname),
      url_scheme_class: ['http:', 'https:'].includes(candidate.protocol) ? 'http_family' : 'other',
    };
  } catch (_) { return { parses_as_url: false }; }
}

try {
  const withheld = JSON.parse(fs.readFileSync(withheldPath, 'utf8'));
  const xml = fs.readFileSync(xmlPath);
  const actualHash = sha256(xml);
  if (actualHash !== withheld.raw_sha256 || xml.length !== withheld.bytes) throw new Error('RAW_IDENTITY_MISMATCH');
  const files = ['src', 'tests', 'e2e'].flatMap(directory => sourceFiles(path.join(sourceRoot, 'frontend', directory)));
  const matchReports = withheld.matches.map(expected => {
    const exclusive = xml.subarray(expected.byte_start, expected.byte_end);
    const inclusive = xml.subarray(expected.byte_start, expected.byte_end + 1);
    const matched = sha256(exclusive) === expected.sha256 ? exclusive : sha256(inclusive) === expected.sha256 ? inclusive : null;
    if (!matched) throw new Error('MATCH_IDENTITY_MISMATCH');
    const testcaseStart = xml.lastIndexOf(Buffer.from('<testcase '), expected.byte_start);
    const testcaseOpenEnd = xml.indexOf(Buffer.from('>'), testcaseStart);
    const testcaseEnd = xml.indexOf(Buffer.from('</testcase>'), testcaseOpenEnd);
    if (testcaseStart < 0 || testcaseEnd < expected.byte_start) throw new Error('TESTCASE_NOT_CONTAINING_MATCH');
    const testcaseOpening = xml.subarray(testcaseStart, testcaseOpenEnd + 1).toString('utf8');
    const testcaseAttributes = attributes(testcaseOpening);
    const matchAttribute = Array.from(testcaseOpening.matchAll(/([\w:.-]+)="([^"]*)"/g)).find(attribute => {
      const attributeStart = testcaseStart + Buffer.byteLength(testcaseOpening.slice(0, attribute.index));
      return expected.byte_start >= attributeStart && expected.byte_end <= attributeStart + Buffer.byteLength(attribute[0]);
    });
    const variants = new Set([matched.toString('utf8'), xmlDecode(matched.toString('utf8'))]);
    const occurrences = [];
    for (const filePath of files) {
      const sourceText = fs.readFileSync(filePath, 'utf8');
      const source = ts.createSourceFile(filePath, sourceText, ts.ScriptTarget.Latest, true, filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
      function visit(node) {
        if (ts.isStringLiteralLike(node)) {
          const matchingVariant = [...variants].find(value => value.length && node.text.includes(value));
          if (matchingVariant) occurrences.push({
            ...nodeLocation(node, source, filePath),
            source_sha256: sha256(sourceText),
            literal_value_sha256: sha256(node.text),
            literal_value_length: node.text.length,
            literal_uri_shape: uriShape(node.text),
            literal_source_byte_start: Buffer.byteLength(sourceText.slice(0, node.getStart(source))),
            literal_source_byte_end_exclusive: Buffer.byteLength(sourceText.slice(0, node.end)),
            source_match_byte_start: Buffer.byteLength(sourceText.slice(0, sourceText.indexOf(matchingVariant, node.getStart(source)))),
            source_match_byte_end_exclusive: Buffer.byteLength(sourceText.slice(0, sourceText.indexOf(matchingVariant, node.getStart(source)) + matchingVariant.length)),
            match_is_whole_literal: node.text === matchingVariant,
            decoded_match_sha256: sha256(matchingVariant),
            literal_flow: eachFlow(node, source, filePath, testcaseAttributes.name || ''),
          });
        }
        ts.forEachChild(node, visit);
      }
      visit(source);
    }
    return {
      byte_start: expected.byte_start,
      byte_end: expected.byte_end,
      byte_end_convention: matched.length === exclusive.length ? 'exclusive' : 'inclusive',
      match_sha256: expected.sha256,
      match_bytes: matched.length,
      match_uri_shape: uriShape(xmlDecode(matched.toString('utf8'))),
      testcase_byte_start: testcaseStart,
      testcase_byte_end_exclusive: testcaseEnd + Buffer.byteLength('</testcase>'),
      testcase_name_sha256: sha256(testcaseAttributes.name || ''),
      testcase_classname_sha256: sha256(testcaseAttributes.classname || ''),
      testcase_attribute_names: Object.keys(testcaseAttributes),
      testcase_has_failure_or_error: /<(?:failure|error)(?:\s|>)/.test(xml.subarray(testcaseOpenEnd + 1, testcaseEnd).toString('utf8')),
      testcase_has_skipped: /<skipped(?:\s|>|\/)/.test(xml.subarray(testcaseOpenEnd + 1, testcaseEnd).toString('utf8')),
      match_location: matchAttribute ? 'testcase_opening_attribute' : 'testcase_body',
      match_attribute_name: matchAttribute ? matchAttribute[1] : null,
      safe_classname_path: /^[\w./\\-]+\.(?:test|spec)\.[cm]?tsx?$/.test(testcaseAttributes.classname || '') ? testcaseAttributes.classname : null,
      literal_occurrences: occurrences,
    };
  });
  const report = {
    schema_version: 1,
    mode: 'metadata_only_read_only_provenance',
    code_version: 'a576fc1f88cd82bc13e5bed9a4c7a013bb8cd74b',
    xml_path: xmlPath,
    xml_bytes: xml.length,
    xml_sha256: actualHash,
    withheld_metadata_path: withheldPath.replaceAll('\\', '/'),
    withheld_metadata_sha256: sha256(fs.readFileSync(withheldPath)),
    typescript_version: ts.version,
    source_file_count: files.length,
    matches: matchReports,
    raw_content_emitted: false,
    exemption_created: false,
    scanner_executed: false,
    classification: 'test_only_synthetic_invalid_uri_literal_echoed_in_parameterized_test_name',
    observed_flow: 'static_it_each_row_to_isSafeSbomDocumentUri_then_expect_toBe_false; no_network_or_credential_client_call_in_inspected_validation_function_and_local_helper',
    verification_limits: [
      'No new unit, integration, live or browser tests were run.',
      'A frozen source match and matching table-expanded testcase name establish fixture provenance; original batch command provenance was not independently rerun.',
      'Actual-secret exact comparison was not performed; no private secrets were accessed.',
      'This classification applies only to the stated original XML hash and exact byte span; it creates no exemption and does not authorize broader scan exclusions.',
    ],
  };
  fs.mkdirSync(outputRoot, { recursive: true });
  fs.writeFileSync(path.join(outputRoot, 'provenance_metadata.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
} catch (error) {
  console.log(JSON.stringify({ status: 'failed', safe_error_code: /^\w+$/.test(error.message) ? error.message : 'PROVENANCE_PROBE_FAILED', raw_content_emitted: false }));
  process.exitCode = 1;
}
