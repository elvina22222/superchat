const fs = require("fs"), path = require("path");
const { createSuperChat } = require("./engine.js");
const T = JSON.parse(fs.readFileSync(path.join(__dirname, "tables.json"), "utf8"));
const P = JSON.parse(fs.readFileSync(path.join(__dirname, "parity.json"), "utf8"));
let bot = createSuperChat(T), bad = 0, n = 0;
for (const r of P.routing) {
  for (const c of r.ctx) bot.handle(r.sid, c);
  const js = bot.route(r.msg, r.sid).category; n++;
  if (js !== r.py) { bad++; console.log("ROUTE DIFF", r.msg, "| py:", r.py, "js:", js); }
}
bot = createSuperChat(T);
P.convs.forEach((rows, i) => rows.forEach(row => {
  const r = bot.handle("c" + i, row.msg); n++;
  if (r.category !== row.cat || r.reply !== row.reply) {
    bad++; console.log("CONV DIFF:", row.msg, "\n  py[" + row.cat + "]:", JSON.stringify(row.reply.slice(0, 300)), "\n  js[" + r.category + "]:", JSON.stringify(r.reply.slice(0, 300)));
  }
}));
console.log(`parity: ${n - bad}/${n} identical`);
