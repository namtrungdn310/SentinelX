import assert from "node:assert/strict";
import ts from "typescript";

// Check the actual JavaScript served by Vite. An HTML 200 alone cannot detect
// a missing optimized React dependency, which leaves the browser page blank.
const base = new URL(process.argv[2] ?? "http://localhost:5174");
const pending = ["/src/main.tsx", "/@vite/client", "/@react-refresh"];
const visited = new Set();
let checked = 0;

while (pending.length) {
    const path = pending.shift();
    const url = new URL(path, base);
    if (visited.has(url.href)) continue;
    visited.add(url.href);
    const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
    assert.equal(response.status, 200, `${url.pathname}: HTTP ${response.status}`);
    const contentType = response.headers.get("content-type") ?? "";
    assert.ok(/javascript/.test(contentType), `${url.pathname}: expected JavaScript, got ${contentType}`);
    const source = await response.text();
    const module = ts.createSourceFile(url.pathname, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
    for (const statement of module.statements) {
        if (!ts.isImportDeclaration(statement) && !ts.isExportDeclaration(statement)) continue;
        if (!statement.moduleSpecifier || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
        const specifier = statement.moduleSpecifier.text;
        if (!specifier.startsWith(".") && !specifier.startsWith("/")) continue;
        const dependency = new URL(specifier, url);
        if (dependency.origin === base.origin) pending.push(dependency.href);
    }
    checked++;
}
assert.ok(checked > 10, "Expected the complete dashboard dependency graph");
console.log(`PASS: ${checked} browser modules return JavaScript HTTP 200, including React and React DOM.`);
