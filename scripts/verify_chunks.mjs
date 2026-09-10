// Verify all JS/CSS static assets referenced in the homepage HTML return HTTP 200.
// Run on VPS: node /tmp/verify_chunks.mjs
const BASE = "https://web.aurexis.web.id";

async function main() {
  console.log("Fetching homepage...");
  const html = await (await fetch(BASE + "/")).text();

  // Extract all script src and link href for /_next/ assets
  const srcs = [];
  for (const m of html.matchAll(/src="(\/_next\/[^"]+)"/g)) srcs.push(m[1]);
  for (const m of html.matchAll(/href="(\/_next\/[^"]+)"/g)) srcs.push(m[1]);

  console.log("Assets found:", srcs.length);
  let failures = 0;

  for (const s of srcs) {
    const url = BASE + s;
    const res = await fetch(url, { method: "HEAD" });
    const ok = res.status === 200;
    console.log(ok ? "OK  " : "FAIL", res.status, s);
    if (!ok) failures++;
  }

  if (failures > 0) {
    console.error(`\nFAILED: ${failures} asset(s) did not return 200`);
    process.exit(1);
  } else {
    console.log("\nALL ASSETS LOADED SUCCESSFULLY.");
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
