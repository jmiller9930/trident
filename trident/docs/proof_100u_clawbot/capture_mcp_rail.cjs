const puppeteer = require("puppeteer");
(async () => {
  const browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900 });
  await page.goto("http://127.0.0.1:3000/", { waitUntil: "networkidle0", timeout: 120000 });
  const aside = await page.$("aside.control");
  if (aside) await aside.screenshot({ path: "/out/100u-mcp-router-rail.png" });
  await browser.close();
})();
