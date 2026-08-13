/**
 * What happens when things break. The app is local, so the failures that
 * actually occur are: the API is not running, a vendor key is wrong, a vendor
 * is unreachable. Each one must be SAID, not swallowed.
 *
 *   node .resilience.mjs
 */
import { execSync, spawn } from "node:child_process";
import { chromium } from "playwright";

const BACKEND = "C:\\Users\\Administrator\\Music\\Zonelab\\backend";
const PY = `${BACKEND}\\.venv\\Scripts\\python.exe`;
const results = [];
const check = (n, p, d = "") => results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function apiPid() {
  try {
    const out = execSync("netstat -ano -p TCP").toString();
    const line = out.split("\n").find((l) => l.includes(":8100") && l.includes("LISTENING"));
    return line ? Number(line.trim().split(/\s+/).pop()) : null;
  } catch {
    return null;
  }
}

function killApi() {
  const pid = apiPid();
  if (pid) execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
  return pid;
}

function startApi(env = {}) {
  const child = spawn(PY, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8100"],
    { cwd: BACKEND, env: { ...process.env, ...env }, detached: true, stdio: "ignore" });
  child.unref();
  return child;
}

async function waitForApi(up = true, tries = 40) {
  for (let i = 0; i < tries; i++) {
    const alive = apiPid() !== null;
    if (alive === up) return true;
    await sleep(400);
  }
  return false;
}

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
const crashes = [];
page.on("pageerror", (e) => crashes.push(e.message));

const alertText = () =>
  page.locator('[role="alert"]:not(#__next-route-announcer__)').allTextContents();

await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await sleep(5000);
check("starts healthy", (await page.locator("canvas").count()) > 0);

// ---- the API dies mid-session ------------------------------------------
killApi();
await waitForApi(false);
await page.locator('div[aria-label="Timeframe"] button:text-is("1h")').click();
await sleep(6000);

const dead = await alertText();
check("a dead API produces a visible error", dead.length > 0, dead.join("|"));
check("the error names the address and the cause",
      dead.join(" ").includes("8100") && /running|reach/i.test(dead.join(" ")), dead.join("|"));
check("the loading indicator does not lie",
      !(await page.locator("text=/^loading$/").count()), "still says loading");
check("the app did not crash", crashes.length === 0, crashes.slice(0, 2).join("|"));
check("the last good chart is still on screen", (await page.locator("canvas").count()) > 0);

// ---- it comes back ------------------------------------------------------
startApi();
await waitForApi(true);
await sleep(2500);
await page.locator('div[aria-label="Timeframe"] button:text-is("15m")').click();
await sleep(7000);
check("recovers without a reload", (await alertText()).length === 0, (await alertText()).join("|"));
check("zones are drawn again",
      Number((await page.locator("text=/\\d+ drawn/").first().textContent()).match(/\d+/)[0]) > 0);

// ---- a wrong vendor key -------------------------------------------------
killApi();
await waitForApi(false);
startApi({ ZONELAB_TWELVEDATA_KEY: "definitely-not-a-real-key" });
await waitForApi(true);
await sleep(2500);
await page.reload({ waitUntil: "networkidle" });
await sleep(5000);

const options = await page.locator("select").nth(1).locator("option").allTextContents();
check("a configured provider is offered even with a bad key", options.includes("twelvedata"),
      options.join(","));

await page.locator("select").nth(1).selectOption("twelvedata");
await sleep(7000);
const keyError = await alertText();
check("a rejected key surfaces the vendor's own words", keyError.length > 0, keyError.join("|"));
check("the rejected key is not confused with an empty market",
      /key|apikey|invalid|twelvedata/i.test(keyError.join(" ")), keyError.join("|"));

await page.screenshot({ path: process.argv[2] + "\\resilience-bad-key.png" });

// ---- back to a working provider ----------------------------------------
await page.locator("select").nth(1).selectOption("binance");
await sleep(6000);
check("switching back to a good provider clears the error",
      (await alertText()).length === 0, (await alertText()).join("|"));

await browser.close();

// ---- leave the environment as we found it -------------------------------
killApi();
await waitForApi(false);
startApi();
await waitForApi(true);

console.log(results.join("\n"));
const failed = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
