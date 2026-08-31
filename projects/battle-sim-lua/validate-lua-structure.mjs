import fs from "node:fs";

const path = process.argv[2];
if (!path) {
  throw new Error("Usage: node validate-lua-structure.mjs <lua-file>");
}

const source = fs.readFileSync(path, "utf8");
const tokens = [];
const brackets = [];
let index = 0;
let line = 1;

function advance() {
  if (source[index] === "\n") line++;
  index++;
}

function skipQuoted(quote) {
  const startLine = line;
  advance();
  while (index < source.length) {
    if (source[index] === "\\") {
      advance();
      if (index < source.length) advance();
    } else if (source[index] === quote) {
      advance();
      return;
    } else {
      advance();
    }
  }
  throw new Error(`Unterminated string starting on line ${startLine}`);
}

function skipLongBracket() {
  const match = source.slice(index).match(/^\[(=*)\[/);
  if (!match) return false;
  const startLine = line;
  const close = `]${match[1]}]`;
  for (let count = 0; count < match[0].length; count++) advance();
  while (index < source.length && !source.startsWith(close, index)) advance();
  if (index >= source.length) {
    throw new Error(`Unterminated long bracket starting on line ${startLine}`);
  }
  for (let count = 0; count < close.length; count++) advance();
  return true;
}

while (index < source.length) {
  const char = source[index];

  if (/\s/.test(char)) {
    advance();
    continue;
  }
  if (source.startsWith("--", index)) {
    advance();
    advance();
    if (skipLongBracket()) continue;
    while (index < source.length && source[index] !== "\n") advance();
    continue;
  }
  if (char === "'" || char === '"') {
    skipQuoted(char);
    continue;
  }
  if (char === "[" && skipLongBracket()) continue;

  const identifier = source.slice(index).match(/^[A-Za-z_][A-Za-z0-9_]*/);
  if (identifier) {
    tokens.push({ value: identifier[0], line });
    for (let count = 0; count < identifier[0].length; count++) advance();
    continue;
  }

  if ("({[".includes(char)) {
    brackets.push({ value: char, line });
  } else if (")}]".includes(char)) {
    const expected = { ")": "(", "}": "{", "]": "[" }[char];
    const open = brackets.pop();
    if (!open || open.value !== expected) {
      throw new Error(`Mismatched '${char}' on line ${line}`);
    }
  }
  advance();
}

if (brackets.length) {
  const open = brackets.at(-1);
  throw new Error(`Unclosed '${open.value}' from line ${open.line}`);
}

const blocks = [];
for (const token of tokens) {
  if (["function", "if", "for", "while", "repeat"].includes(token.value)) {
    blocks.push(token);
  } else if (token.value === "until") {
    const open = blocks.pop();
    if (!open || open.value !== "repeat") {
      throw new Error(`Unexpected 'until' on line ${token.line}`);
    }
  } else if (token.value === "end") {
    const open = blocks.pop();
    if (!open || open.value === "repeat") {
      throw new Error(`Unexpected 'end' on line ${token.line}`);
    }
  }
}

if (blocks.length) {
  const open = blocks.at(-1);
  throw new Error(`Unclosed '${open.value}' block from line ${open.line}`);
}

const requiredFragments = [
  "local RESULT_TABLE",
  "local GROGGY_TABLE",
  "local function setPresentation",
  "local function advancePresentation",
  "{{raw::",
  "player.png",
  "bsim-resolution",
  "listenEdit('editDisplay'",
  "onStart=function",
  "onButtonClick=function",
];

for (const fragment of requiredFragments) {
  if (!source.includes(fragment)) {
    throw new Error(`Required fragment is missing: ${fragment}`);
  }
}

console.log(`Lua structural validation: OK (${line} lines, ${tokens.length} tokens)`);
