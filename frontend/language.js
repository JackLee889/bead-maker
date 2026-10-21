// No image data, cookies, referrer or full IP is sent back to the app.
const preferenceKey = "bead-maker.language.v1";
const countryKey = "bead-maker.country.v1";
const choices = ["auto", "zh-CN", "zh-TW", "en", "ja"];
let lookupPromise;
let published = "";

function readStorage(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function writeStorage(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Private mode still works. */ }
}

async function lookupCountry() {
  const cached = readStorage(countryKey);
  const ttl = cached?.country ? 24 * 60 * 60 * 1000 : 5 * 60 * 1000;
  if (cached && Number.isFinite(cached.time) && Date.now() >= cached.time && Date.now() - cached.time < ttl) {
    return cached.country;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1800);
  let country = null;
  try {
    const response = await fetch("https://api.country.is/", {
      signal: controller.signal, credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store",
    });
    if (!response.ok) throw new Error("Country lookup unavailable");
    const payload = await response.json();
    if (typeof payload.country === "string" && /^[A-Z]{2}$/.test(payload.country) && !["XX", "ZZ"].includes(payload.country)) {
      country = payload.country;
    }
  } catch { /* Offline, CORS, rate limits and timeouts fall back to the browser language. */ }
  finally { clearTimeout(timer); }
  writeStorage(countryKey, {country, time: Date.now()});
  return country;
}

export default function({data, setStateValue}) {
  let active = true;
  const saved = readStorage(preferenceKey);
  const preference = choices.includes(data.preference) ? data.preference : choices.includes(saved) ? saved : "auto";
  if (choices.includes(data.preference)) writeStorage(preferenceKey, preference);
  if (choices.includes(data.language) && data.language !== "auto") document.documentElement.lang = data.language;
  const publish = (country) => {
    const environment = {preference, country, locale: navigator.language || ""};
    const signature = JSON.stringify([data.session, environment]);
    if (active && published !== signature) {
      published = signature;
      setStateValue("environment", environment);
    }
  };
  if (preference !== "auto" || !data.ipEnabled) {
    publish(null);
  } else {
    // Share in-flight work across rerenders, and avoid repeated requests after a failure.
    lookupPromise ??= lookupCountry();
    lookupPromise.then(publish);
  }
  return () => { active = false; };
}
