"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.getHslIndexService = getHslIndexService;
exports.registerHslIntelliSense = registerHslIntelliSense;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const vscode = __importStar(require("vscode"));
const DEFAULT_LIBRARY_ROOT = "C:\\Program Files (x86)\\Hamilton\\Library";
const INDEX_CACHE_FILE = "hsl-global-index-cache.json";
function normalizeWindowsPath(filePath) {
    return path.win32.normalize(filePath).toLowerCase();
}
function isAbsoluteWindowsPath(includeTarget) {
    return /^[a-zA-Z]:[\\/]/.test(includeTarget) || /^\\\\[^\\]+\\[^\\]+/.test(includeTarget);
}
function getLibraryRoot() {
    const cfg = vscode.workspace.getConfiguration("hsl");
    const configured = cfg.get("libraryRoot", DEFAULT_LIBRARY_ROOT);
    return path.win32.normalize(configured);
}
function toWindowsLike(input) {
    return input.replace(/[\/]/g, "\\");
}
function markdownForSymbol(symbol) {
    const params = symbol.parameters
        .map((p) => `${p.typeText}${p.isByRef ? "&" : ""} ${p.nameText}${p.isArray ? "[]" : ""}`)
        .join(", ");
    const lines = [];
    lines.push(`**${symbol.qualifiedName}**`);
    lines.push("");
    lines.push(`\`${symbol.name}(${params}) ${symbol.returnTypeText}\``);
    if (symbol.docComment.trim().length > 0) {
        lines.push("");
        lines.push(symbol.docComment);
    }
    lines.push("");
    lines.push(`Defined in: ${symbol.definedInFile}`);
    return new vscode.MarkdownString(lines.join("\n"));
}
function sanitizeForParsing(text) {
    const chars = [...text];
    let i = 0;
    while (i < chars.length) {
        const ch = chars[i];
        const next = i + 1 < chars.length ? chars[i + 1] : "";
        if (ch === '"') {
            let j = i;
            chars[j] = " ";
            j++;
            while (j < chars.length) {
                const c = chars[j];
                if (c === "\\" && j + 1 < chars.length) {
                    chars[j] = " ";
                    chars[j + 1] = " ";
                    j += 2;
                    continue;
                }
                chars[j] = c === "\n" || c === "\r" ? c : " ";
                if (c === '"') {
                    j++;
                    break;
                }
                j++;
            }
            i = j;
            continue;
        }
        if (ch === "/" && next === "/") {
            chars[i] = " ";
            chars[i + 1] = " ";
            i += 2;
            while (i < chars.length && chars[i] !== "\n") {
                chars[i] = " ";
                i++;
            }
            continue;
        }
        if (ch === "/" && next === "*") {
            chars[i] = " ";
            chars[i + 1] = " ";
            i += 2;
            while (i < chars.length) {
                if (chars[i] === "*" && i + 1 < chars.length && chars[i + 1] === "/") {
                    chars[i] = " ";
                    chars[i + 1] = " ";
                    i += 2;
                    break;
                }
                chars[i] = chars[i] === "\n" || chars[i] === "\r" ? chars[i] : " ";
                i++;
            }
            continue;
        }
        i++;
    }
    return chars.join("");
}
function extractIncludeTargets(text, libraryRoot) {
    const includes = [];
    const pattern = /^\s*#include\s+"([^"]+)"/gm;
    let m;
    while ((m = pattern.exec(text)) !== null) {
        const rawTarget = m[1].trim();
        const resolvedPath = resolveIncludeTarget(rawTarget, libraryRoot);
        includes.push({
            rawTarget,
            isAbsolute: isAbsoluteWindowsPath(rawTarget),
            resolvedPath: resolvedPath ?? undefined,
        });
    }
    return includes;
}
function resolveIncludeTarget(target, libraryRoot) {
    const winTarget = toWindowsLike(target);
    const candidate = isAbsoluteWindowsPath(winTarget)
        ? path.win32.normalize(winTarget)
        : path.win32.normalize(path.win32.join(libraryRoot, winTarget));
    if (fs.existsSync(candidate)) {
        return candidate;
    }
    return null;
}
function splitArgs(paramList) {
    const parts = [];
    let current = "";
    let depth = 0;
    for (const c of paramList) {
        if (c === "(") {
            depth++;
            current += c;
            continue;
        }
        if (c === ")") {
            depth = Math.max(0, depth - 1);
            current += c;
            continue;
        }
        if (c === "," && depth === 0) {
            parts.push(current.trim());
            current = "";
            continue;
        }
        current += c;
    }
    if (current.trim().length > 0) {
        parts.push(current.trim());
    }
    return parts;
}
function parseParameter(param) {
    const trimmed = param.trim();
    const rawNoDefault = trimmed.includes("=") ? trimmed.slice(0, trimmed.indexOf("=")).trim() : trimmed;
    const isArray = /\[\]\s*$/.test(rawNoDefault);
    const noArray = rawNoDefault.replace(/\[\]\s*$/, "").trim();
    const nameMatch = /([A-Za-z_]\w*)\s*$/.exec(noArray);
    const nameText = nameMatch ? nameMatch[1] : noArray;
    let beforeName = nameMatch ? noArray.slice(0, nameMatch.index).trim() : "";
    const isByRef = beforeName.includes("&");
    beforeName = beforeName.replace(/&/g, "").trim();
    return {
        typeText: beforeName,
        nameText,
        isByRef,
        isArray,
    };
}
function extractDocComment(originalLines, functionStartLine) {
    let i = functionStartLine - 1;
    while (i >= 0 && originalLines[i].trim() === "") {
        i--;
    }
    if (i < 0) {
        return "";
    }
    const line = originalLines[i].trim();
    if (line.startsWith("//")) {
        const buf = [];
        while (i >= 0 && originalLines[i].trim().startsWith("//")) {
            buf.push(originalLines[i].trim().replace(/^\/\/\s?/, ""));
            i--;
        }
        buf.reverse();
        return buf.join("\n").trim();
    }
    if (line.endsWith("*/") || line.includes("*/")) {
        const buf = [];
        while (i >= 0) {
            buf.push(originalLines[i]);
            if (originalLines[i].includes("/*")) {
                break;
            }
            i--;
        }
        buf.reverse();
        const block = buf.join("\n");
        return block
            .replace(/^\s*\/\*+/, "")
            .replace(/\*+\/\s*$/, "")
            .split(/\r?\n/)
            .map((s) => s.replace(/^\s*\*\s?/, ""))
            .join("\n")
            .trim();
    }
    return "";
}
function toRelativeIncludePath(absoluteFile, libraryRoot) {
    const relative = path.win32.relative(path.win32.normalize(libraryRoot), path.win32.normalize(absoluteFile));
    return toWindowsLike(relative);
}
function parseFunctionsAndNamespaces(text, filePath, libraryRoot) {
    const sanitized = sanitizeForParsing(text);
    const originalLines = text.split(/\r?\n/);
    const cleanLines = sanitized.split(/\r?\n/);
    const functions = [];
    const namespaceStack = [];
    let braceDepth = 0;
    let pendingNamespace = null;
    let collectingFunction = false;
    let functionStartLine = -1;
    let functionHeaderParts = [];
    for (let lineIndex = 0; lineIndex < cleanLines.length; lineIndex++) {
        const cleanLine = cleanLines[lineIndex];
        const originalLine = originalLines[lineIndex] ?? "";
        if (!collectingFunction) {
            const nsMatch = /^\s*(?:(?:private|public|static|global|const|synchronized)\s+)*namespace\s+([A-Za-z_]\w*)\b/.exec(cleanLine);
            if (nsMatch) {
                pendingNamespace = nsMatch[1];
            }
            if (/^\s*(?:(?:private|public|static|global|const|synchronized)\s+)*function\b/.test(cleanLine)) {
                collectingFunction = true;
                functionStartLine = lineIndex;
                functionHeaderParts = [originalLine];
            }
        }
        else {
            functionHeaderParts.push(originalLine);
        }
        if (collectingFunction) {
            const joinedClean = sanitizeForParsing(functionHeaderParts.join("\n"));
            const parenDelta = (joinedClean.match(/\(/g)?.length ?? 0) - (joinedClean.match(/\)/g)?.length ?? 0);
            const hasTerminator = /[;{]/.test(joinedClean);
            if (parenDelta <= 0 && hasTerminator) {
                const joinedOriginal = functionHeaderParts.join("\n");
                const fnMatch = /^\s*((?:(?:private|public|static|global|const|synchronized)\s+)*)function\s+([A-Za-z_]\w*)\s*\(([\s\S]*?)\)\s*([A-Za-z_]\w*)\s*(?:;|\{)/m.exec(joinedOriginal);
                if (fnMatch) {
                    const modifiers = fnMatch[1] ?? "";
                    const name = fnMatch[2];
                    const paramsRaw = fnMatch[3] ?? "";
                    const returnTypeText = fnMatch[4] ?? "variable";
                    const parameters = splitArgs(paramsRaw)
                        .filter((p) => p.length > 0)
                        .map(parseParameter);
                    const nsPrefix = namespaceStack.map((n) => n.name).join("::");
                    const qualifiedName = nsPrefix.length > 0 ? `${nsPrefix}::${name}` : name;
                    const docComment = extractDocComment(originalLines, functionStartLine);
                    const includeText = toRelativeIncludePath(filePath, libraryRoot);
                    functions.push({
                        name,
                        qualifiedName,
                        parameters,
                        returnTypeText,
                        docComment,
                        definedInFile: path.win32.normalize(filePath),
                        requiredInclude: {
                            includeText,
                            resolvedPath: path.win32.normalize(filePath),
                        },
                        isPrivate: /\bprivate\b/.test(modifiers),
                    });
                }
                collectingFunction = false;
                functionStartLine = -1;
                functionHeaderParts = [];
            }
        }
        for (const ch of cleanLine) {
            if (ch === "{") {
                braceDepth++;
                if (pendingNamespace) {
                    namespaceStack.push({ name: pendingNamespace, depth: braceDepth });
                    pendingNamespace = null;
                }
            }
            else if (ch === "}") {
                while (namespaceStack.length > 0 && namespaceStack[namespaceStack.length - 1].depth >= braceDepth) {
                    namespaceStack.pop();
                }
                braceDepth = Math.max(0, braceDepth - 1);
            }
        }
    }
    return functions;
}
async function* walkHslFiles(root) {
    let entries = [];
    try {
        entries = await fs.promises.readdir(root, { withFileTypes: true });
    }
    catch {
        return;
    }
    for (const entry of entries) {
        const full = path.win32.join(root, entry.name);
        if (entry.isDirectory()) {
            yield* walkHslFiles(full);
            continue;
        }
        if (entry.isFile() && full.toLowerCase().endsWith(".hsl")) {
            yield full;
        }
    }
}
class HslIndexService {
    constructor(context) {
        this.parseCache = new Map();
        this.globalSymbols = [];
        this.globalByQualified = new Map();
        this.unresolvedIncludeCollection = vscode.languages.createDiagnosticCollection("hsl-includes");
        this.buildStarted = false;
        this.buildComplete = false;
        this.context = context;
    }
    register(context) {
        context.subscriptions.push(this.unresolvedIncludeCollection);
        const provider = vscode.languages.registerCompletionItemProvider({ language: "hsl", scheme: "file" }, {
            provideCompletionItems: async (document) => {
                const visible = await this.getVisibleSymbolContext(document);
                await this.ensureGlobalIndex();
                const allItems = this.buildCompletionItems(document, visible);
                this.publishUnresolvedIncludeDiagnostics(document);
                return allItems;
            },
        }, ":");
        const hoverProvider = vscode.languages.registerHoverProvider({ language: "hsl", scheme: "file" }, {
            provideHover: async (document, position) => {
                const token = this.getSymbolTokenAtPosition(document, position);
                if (!token) {
                    return undefined;
                }
                const symbol = await this.findBestSymbol(document, token);
                if (!symbol) {
                    return undefined;
                }
                return new vscode.Hover(markdownForSymbol(symbol));
            },
        });
        const signatureProvider = vscode.languages.registerSignatureHelpProvider({ language: "hsl", scheme: "file" }, {
            provideSignatureHelp: async (document, position) => {
                const call = this.findCallAtPosition(document, position);
                if (!call) {
                    return undefined;
                }
                const symbol = await this.findBestSymbol(document, call.name);
                if (!symbol) {
                    return undefined;
                }
                const sig = new vscode.SignatureInformation(`${symbol.qualifiedName}(${symbol.parameters
                    .map((p) => `${p.typeText}${p.isByRef ? "&" : ""} ${p.nameText}${p.isArray ? "[]" : ""}`)
                    .join(", ")}) ${symbol.returnTypeText}`, symbol.docComment);
                sig.parameters = symbol.parameters.map((p) => new vscode.ParameterInformation(`${p.typeText}${p.isByRef ? "&" : ""} ${p.nameText}${p.isArray ? "[]" : ""}`));
                const help = new vscode.SignatureHelp();
                help.signatures = [sig];
                help.activeSignature = 0;
                help.activeParameter = Math.min(call.activeParameter, Math.max(0, symbol.parameters.length - 1));
                return help;
            },
        }, "(", ",");
        context.subscriptions.push(provider, hoverProvider, signatureProvider);
        void this.ensureGlobalIndex();
    }
    async getVisibleSymbolContext(document) {
        const visited = new Set();
        const symbols = [];
        const visibleFiles = new Set();
        const queue = [
            { filePath: document.uri.fsPath, inlineText: document.getText() },
        ];
        while (queue.length > 0) {
            const next = queue.shift();
            if (!next) {
                continue;
            }
            const normalized = normalizeWindowsPath(next.filePath);
            if (visited.has(normalized)) {
                continue;
            }
            visited.add(normalized);
            const parsed = await this.getParseResult(next.filePath, next.inlineText);
            if (!parsed) {
                continue;
            }
            visibleFiles.add(normalized);
            for (const fn of parsed.functions) {
                if (!fn.isPrivate) {
                    symbols.push(fn);
                }
            }
            for (const inc of parsed.includes) {
                if (inc.resolvedPath) {
                    queue.push({ filePath: inc.resolvedPath });
                }
            }
        }
        return { symbols, visibleFiles };
    }
    buildCompletionItems(document, visible) {
        const items = [];
        const seen = new Set();
        const pushSymbol = (symbol, source) => {
            const key = `${symbol.qualifiedName}|${normalizeWindowsPath(symbol.definedInFile)}`;
            if (seen.has(key)) {
                return;
            }
            seen.add(key);
            const signature = `${symbol.qualifiedName}(${symbol.parameters
                .map((p) => `${p.typeText}${p.isByRef ? "&" : ""} ${p.nameText}${p.isArray ? "[]" : ""}`)
                .join(", ")})`;
            const item = new vscode.CompletionItem(symbol.qualifiedName, vscode.CompletionItemKind.Function);
            item.detail = `${signature} : ${symbol.returnTypeText}`;
            item.documentation = markdownForSymbol(symbol);
            item.insertText = new vscode.SnippetString(`${symbol.qualifiedName}($0)`);
            item.filterText = `${symbol.qualifiedName} ${symbol.name}`;
            item.sortText = source === "visible" ? `0_${symbol.qualifiedName}` : `1_${symbol.qualifiedName}`;
            if (source === "global") {
                const definingNormalized = normalizeWindowsPath(symbol.definedInFile);
                const alreadyVisible = visible.visibleFiles.has(definingNormalized);
                if (!alreadyVisible) {
                    const includeEdit = this.getIncludeInsertionEdit(document, symbol.definedInFile);
                    if (includeEdit) {
                        item.additionalTextEdits = [includeEdit];
                    }
                }
            }
            items.push(item);
        };
        for (const symbol of visible.symbols) {
            pushSymbol(symbol, "visible");
        }
        for (const symbol of this.globalSymbols) {
            if (!symbol.isPrivate) {
                pushSymbol(symbol, "global");
            }
        }
        return items;
    }
    chooseIncludeStyle(document) {
        const includes = this.readDocumentIncludes(document);
        if (includes.length === 0) {
            return "relative";
        }
        let abs = 0;
        let rel = 0;
        for (const inc of includes) {
            if (isAbsoluteWindowsPath(inc.rawTarget)) {
                abs++;
            }
            else {
                rel++;
            }
        }
        return abs > rel ? "absolute" : "relative";
    }
    readDocumentIncludes(document) {
        return extractIncludeTargets(document.getText(), getLibraryRoot());
    }
    getIncludeInsertionEdit(document, absoluteIncludeFile) {
        const includes = this.readDocumentIncludes(document);
        const normalizedTarget = normalizeWindowsPath(absoluteIncludeFile);
        for (const inc of includes) {
            if (inc.resolvedPath && normalizeWindowsPath(inc.resolvedPath) === normalizedTarget) {
                return null;
            }
        }
        const style = this.chooseIncludeStyle(document);
        const libraryRoot = getLibraryRoot();
        const includeText = style === "absolute" ? path.win32.normalize(absoluteIncludeFile) : toRelativeIncludePath(absoluteIncludeFile, libraryRoot);
        const includeLine = `#include "${includeText}"`;
        const insertLine = this.findIncludeInsertLine(document);
        const eol = document.eol === vscode.EndOfLine.CRLF ? "\r\n" : "\n";
        return new vscode.TextEdit(new vscode.Range(insertLine, 0, insertLine, 0), `${includeLine}${eol}`);
    }
    findIncludeInsertLine(document) {
        let pragmaOnceLine = -1;
        let lastIncludeLine = -1;
        let ifndefLine = -1;
        let defineLine = -1;
        for (let i = 0; i < document.lineCount; i++) {
            const text = document.lineAt(i).text.trim();
            if (/^#pragma\s+once\b/.test(text)) {
                pragmaOnceLine = i;
            }
            if (/^#include\s+"[^"]+"/.test(text)) {
                lastIncludeLine = i;
            }
            if (ifndefLine < 0 && /^#ifndef\b/.test(text)) {
                ifndefLine = i;
            }
            if (defineLine < 0 && /^#define\b/.test(text)) {
                defineLine = i;
            }
        }
        if (pragmaOnceLine >= 0) {
            return pragmaOnceLine + 1;
        }
        if (lastIncludeLine >= 0) {
            return lastIncludeLine + 1;
        }
        if (ifndefLine >= 0 && defineLine >= ifndefLine) {
            return defineLine + 1;
        }
        return 0;
    }
    async findBestSymbol(document, symbolText) {
        const visible = await this.getVisibleSymbolContext(document);
        const visibleMatch = visible.symbols.find((s) => s.qualifiedName === symbolText) ??
            visible.symbols.find((s) => s.name === symbolText);
        if (visibleMatch) {
            return visibleMatch;
        }
        await this.ensureGlobalIndex();
        const exactGlobal = this.globalSymbols.find((s) => s.qualifiedName === symbolText);
        if (exactGlobal) {
            return exactGlobal;
        }
        return this.globalSymbols.find((s) => s.name === symbolText);
    }
    getSymbolTokenAtPosition(document, position) {
        const line = document.lineAt(position.line).text;
        let start = position.character;
        let end = position.character;
        while (start > 0 && /[A-Za-z0-9_:]/.test(line[start - 1])) {
            start--;
        }
        while (end < line.length && /[A-Za-z0-9_:]/.test(line[end])) {
            end++;
        }
        const token = line.slice(start, end).trim();
        return token.length > 0 ? token : null;
    }
    findCallAtPosition(document, position) {
        const offset = document.offsetAt(position);
        const text = document.getText();
        let depth = 0;
        let openIndex = -1;
        for (let i = offset - 1; i >= 0; i--) {
            const ch = text[i];
            if (ch === ")") {
                depth++;
            }
            else if (ch === "(") {
                if (depth === 0) {
                    openIndex = i;
                    break;
                }
                depth--;
            }
        }
        if (openIndex < 0) {
            return null;
        }
        let nameEnd = openIndex;
        let nameStart = openIndex;
        while (nameStart > 0 && /[A-Za-z0-9_:]/.test(text[nameStart - 1])) {
            nameStart--;
        }
        const name = text.slice(nameStart, nameEnd).trim();
        if (name.length === 0) {
            return null;
        }
        let activeParameter = 0;
        let nested = 0;
        for (let i = openIndex + 1; i < offset; i++) {
            const ch = text[i];
            if (ch === "(") {
                nested++;
            }
            else if (ch === ")") {
                nested = Math.max(0, nested - 1);
            }
            else if (ch === "," && nested === 0) {
                activeParameter++;
            }
        }
        return { name, activeParameter };
    }
    async ensureGlobalIndex() {
        if (this.buildComplete || this.buildStarted) {
            return;
        }
        this.buildStarted = true;
        const libraryRoot = getLibraryRoot();
        await fs.promises.mkdir(this.context.globalStorageUri.fsPath, { recursive: true });
        const cachePath = path.join(this.context.globalStorageUri.fsPath, INDEX_CACHE_FILE);
        const cache = await this.readGlobalCache(cachePath, libraryRoot);
        const cacheByPath = new Map();
        for (const record of cache?.records ?? []) {
            cacheByPath.set(normalizeWindowsPath(record.filePath), record);
        }
        const newRecords = [];
        for await (const hslFile of walkHslFiles(libraryRoot)) {
            let stat;
            try {
                stat = await fs.promises.stat(hslFile);
            }
            catch {
                continue;
            }
            const norm = normalizeWindowsPath(hslFile);
            const cached = cacheByPath.get(norm);
            if (cached && cached.mtimeMs === stat.mtimeMs) {
                newRecords.push(cached);
                continue;
            }
            let text = "";
            try {
                text = await fs.promises.readFile(hslFile, "utf8");
            }
            catch {
                continue;
            }
            const includes = extractIncludeTargets(text, libraryRoot);
            const functions = parseFunctionsAndNamespaces(text, hslFile, libraryRoot);
            newRecords.push({
                filePath: path.win32.normalize(hslFile),
                mtimeMs: stat.mtimeMs,
                includes,
                functions,
            });
        }
        const cacheToWrite = {
            libraryRoot,
            createdAt: Date.now(),
            records: newRecords,
        };
        try {
            await fs.promises.writeFile(cachePath, JSON.stringify(cacheToWrite), "utf8");
        }
        catch {
            // cache write is best-effort only
        }
        this.globalSymbols.length = 0;
        this.globalByQualified = new Map();
        for (const record of newRecords) {
            const parsed = {
                filePath: record.filePath,
                mtimeMs: record.mtimeMs,
                includes: record.includes,
                functions: record.functions,
            };
            this.parseCache.set(normalizeWindowsPath(record.filePath), parsed);
            for (const fn of record.functions) {
                if (fn.isPrivate) {
                    continue;
                }
                this.globalSymbols.push(fn);
                const existing = this.globalByQualified.get(fn.qualifiedName) ?? [];
                existing.push(fn);
                this.globalByQualified.set(fn.qualifiedName, existing);
            }
        }
        this.buildComplete = true;
    }
    async readGlobalCache(cachePath, libraryRoot) {
        try {
            const raw = await fs.promises.readFile(cachePath, "utf8");
            const parsed = JSON.parse(raw);
            if (normalizeWindowsPath(parsed.libraryRoot) !== normalizeWindowsPath(libraryRoot)) {
                return null;
            }
            return parsed;
        }
        catch {
            return null;
        }
    }
    async getParseResult(filePath, inlineText) {
        const normalized = normalizeWindowsPath(filePath);
        if (!inlineText) {
            const cached = this.parseCache.get(normalized);
            if (cached) {
                try {
                    const stat = await fs.promises.stat(filePath);
                    if (cached.mtimeMs === stat.mtimeMs) {
                        return cached;
                    }
                }
                catch {
                    return cached;
                }
            }
        }
        let text = inlineText;
        if (text === undefined) {
            try {
                text = await fs.promises.readFile(filePath, "utf8");
            }
            catch {
                return null;
            }
        }
        if (text === undefined) {
            return null;
        }
        const libraryRoot = getLibraryRoot();
        const includes = extractIncludeTargets(text, libraryRoot);
        const functions = parseFunctionsAndNamespaces(text, filePath, libraryRoot);
        let mtimeMs = Date.now();
        if (!inlineText) {
            try {
                mtimeMs = (await fs.promises.stat(filePath)).mtimeMs;
            }
            catch {
                // leave default
            }
        }
        const parsed = {
            filePath: path.win32.normalize(filePath),
            mtimeMs,
            includes,
            functions,
        };
        this.parseCache.set(normalized, parsed);
        return parsed;
    }
    publishUnresolvedIncludeDiagnostics(document) {
        const includes = this.readDocumentIncludes(document);
        const diagnostics = [];
        const lines = document.getText().split(/\r?\n/);
        includes.forEach((inc) => {
            if (inc.resolvedPath) {
                return;
            }
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                const marker = `#include \"${inc.rawTarget}\"`;
                const idx = line.indexOf(marker);
                if (idx >= 0) {
                    const range = new vscode.Range(i, idx, i, idx + marker.length);
                    const diagnostic = new vscode.Diagnostic(range, `Unable to resolve include target \"${inc.rawTarget}\" from library root \"${getLibraryRoot()}\".`, vscode.DiagnosticSeverity.Warning);
                    diagnostic.source = "hsl-intellisense";
                    diagnostics.push(diagnostic);
                    break;
                }
            }
        });
        this.unresolvedIncludeCollection.set(document.uri, diagnostics);
    }
}
let indexServiceInstance = null;
function getHslIndexService() {
    return indexServiceInstance;
}
function registerHslIntelliSense(context) {
    const service = new HslIndexService(context);
    indexServiceInstance = service;
    service.register(context);
}
//# sourceMappingURL=hslIntellisense.js.map