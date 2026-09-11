# Test-only runtime fixtures

These files are development fixtures. They are not included in the .risum or .charx package.

- `json.lua`: RisuAI's bundled Lua JSON implementation (rxi/json.lua, MIT; copyright/license retained in file), from `https://github.com/kwaroran/RisuAI/blob/main/public/lua/json.lua`. Reused from this workspace's earlier cached official source.
- `markdown-it.cjs`: markdown-it browser-compatible bundle, MIT. Reused from the workspace's existing Markdown QA fixture.
- `purify.js`: DOMPurify bundle, Apache-2.0 OR MPL-2.0. Its license notice is retained in the file. Reused from the workspace's existing sanitizer QA fixture.

These reproduce the host's JSON and rendering contracts without touching installed RisuAI user data. Game engine, UI, progression, and opponents are original to Last Bell.
