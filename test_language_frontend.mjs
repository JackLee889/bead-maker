// Optional frontend regressions: node --test test_language_frontend.mjs
import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./frontend/language.js", import.meta.url), "utf8");
let moduleId = 0;
const settle = () => new Promise(resolve => setImmediate(resolve));

async function browser({storage = new Map(), fetcher = async () => ({ok: true, json: async () => ({country: "JP", ip: "ignored"})}), denied = false} = {}) {
  const requests = [];
  const events = [];
  globalThis.localStorage = {
    getItem(key) { if (denied) throw new Error("Storage blocked"); return storage.get(key) ?? null; },
    setItem(key, value) { if (denied) throw new Error("Storage blocked"); storage.set(key, value); },
  };
  globalThis.document = {documentElement: {lang: ""}};
  Object.defineProperty(globalThis, "navigator", {value: {language: "zh-Hant"}, configurable: true});
  globalThis.fetch = async (url, options) => { requests.push({url, options}); return fetcher(url, options); };
  const module = await import("data:text/javascript;base64," + Buffer.from(source + `\n// test ${++moduleId}`).toString("base64"));
  const mount = data => module.default({data: {preference: null, ipEnabled: true, language: "zh-TW", session: "test", ...data},
                                        setStateValue: (key, value) => events.push({key, value})});
  return {mount, requests, events, storage};
}

test("IP request returns only region metadata and is shared across rerenders", async () => {
  const b = await browser();
  b.mount({});
  await settle();
  assert.equal(b.requests.length, 1);
  assert.equal(b.requests[0].url, "https://api.country.is/");
  assert.equal(b.requests[0].options.credentials, "omit");
  assert.equal(b.requests[0].options.referrerPolicy, "no-referrer");
  assert.equal(b.requests[0].options.body, undefined);
  assert.deepEqual(b.events[0].value, {preference: "auto", country: "JP", locale: "zh-Hant"});
  assert.equal(JSON.stringify([...b.storage]).includes("ignored"), false);
  b.mount({preference: "auto", language: "ja"});
  await settle();
  assert.equal(b.requests.length, 1);
  assert.equal(b.events.length, 1);
  assert.equal(document.documentElement.lang, "ja");
});

test("saved manual preference skips IP; an explicit selection overrides it", async () => {
  const b = await browser({storage: new Map([["bead-maker.language.v1", JSON.stringify("ja")]])});
  b.mount({});
  assert.equal(b.events.at(-1).value.preference, "ja");
  assert.equal(b.requests.length, 0);
  b.mount({preference: "en", language: "en"});
  assert.equal(JSON.parse(b.storage.get("bead-maker.language.v1")), "en");
  assert.equal(b.events.at(-1).value.preference, "en");
});

test("cached country, invalid response and disabled IP do not block language fallback", async () => {
  const b = await browser({storage: new Map([["bead-maker.country.v1", JSON.stringify({country: "HK", time: Date.now()})]])});
  b.mount({});
  await settle();
  assert.equal(b.requests.length, 0);
  assert.equal(b.events[0].value.country, "HK");
  for (const payload of [{country: "ZZ"}, {country: null}, {}, {country: "not-a-country"}]) {
    const invalid = await browser({fetcher: async () => ({ok: true, json: async () => payload})});
    invalid.mount({});
    await settle();
    assert.equal(invalid.events[0].value.country, null);
    assert.equal(invalid.events[0].value.locale, "zh-Hant");
  }
  const disabled = await browser();
  disabled.mount({ipEnabled: false});
  assert.equal(disabled.requests.length, 0);
  assert.equal(disabled.events[0].value.country, null);
});

test("offline errors and unavailable local storage still publish the browser fallback", async () => {
  const b = await browser({denied: true, fetcher: async () => { throw new Error("Offline"); }});
  b.mount({});
  await settle();
  assert.equal(b.events[0].value.country, null);
  assert.equal(b.events[0].value.locale, "zh-Hant");
  b.mount({preference: "ja"});
  assert.equal(b.events.at(-1).value.preference, "ja");
});

test("a late IP response cannot override a manual choice", async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const b = await browser({fetcher: () => pending});
  const cleanup = b.mount({});
  cleanup();
  b.mount({preference: "en", language: "en"});
  release({ok: true, json: async () => ({country: "JP"})});
  await settle();
  assert.equal(b.events.length, 1);
  assert.equal(b.events[0].value.preference, "en");
});

test("country queries time out and fall back", async () => {
  const b = await browser({fetcher: (_, {signal}) => new Promise((_, reject) => {
    signal.addEventListener("abort", () => reject(new Error("Timed out")), {once: true});
  })});
  b.mount({});
  await new Promise(resolve => setTimeout(resolve, 1900));
  assert.equal(b.events[0].value.country, null);
});
