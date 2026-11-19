"use strict";

let token = "";
try { token = localStorage.getItem("atcctl_token") || ""; } catch (_) {}
const $ = (s, el = document) => el.querySelector(s);
$("#token").value = token;
$("#saveToken").onclick = () => {
  token = $("#token").value.trim();
  try { localStorage.setItem("atcctl_token", token); } catch (_) {}
  refreshAll();
};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

let presets = [];
const cards = new Map();

function renderReceiver(st) {
  let card = cards.get(st.id);
  if (!card) {
    card = $("#rxTpl").content.firstElementChild.cloneNode(true);
    cards.set(st.id, card);
    $("#receivers").append(card);
    const audio = $("audio", card);
    const err = $(".err", card);
    const form = $(".tune", card);

    form.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const body = {};
      for (const [k, v] of fd) if (String(v).trim() !== "") body[k] = String(v).trim();
      await tune(st.id, body, card);
    };
    $(".listen", card).onclick = () => {
      audio.src = `/stream/${st.id}.mp3?token=${encodeURIComponent(token)}&t=${Date.now()}`;
      audio.play().catch((e) => (err.textContent = "재생 실패: " + e.message));
    };
    $(".stop", card).onclick = () => { audio.pause(); audio.removeAttribute("src"); audio.load(); };
    $(".presetSel", card).onchange = async (e) => {
      if (e.target.value) await tune(st.id, { frequency: e.target.value }, card);
      e.target.value = "";
    };
  }
  $(".name", card).textContent = st.name;
  $(".mhz", card).textContent = st.frequency_mhz;
  const s = $(".state", card);
  s.textContent = st.running ? `● 수신중 (${st.band.toUpperCase()}) · 청취자 ${st.listeners}` : "● 정지";
  s.className = "state " + (st.running ? "on" : "off");
  const form = $(".tune", card);
  if (!form.contains(document.activeElement)) {
    form.frequency.value = st.frequency_mhz;
    form.gain.value = st.gain;
    form.squelch.value = st.squelch;
  }
  if (st.error) $(".err", card).textContent = st.error;
  fillPresetSelect($(".presetSel", card));
}

async function tune(id, body, card) {
  const err = $(".err", card);
  err.textContent = "";
  try {
    const st = await api(`/api/receivers/${id}/tune`, { method: "POST", body: JSON.stringify(body) });
    renderReceiver(st);
    const audio = $("audio", card);
    if (!audio.paused) $(".listen", card).click(); // 재시작된 스트림에 재접속
  } catch (e) { err.textContent = e.message; }
}

function fillPresetSelect(sel) {
  const key = JSON.stringify(presets);
  if (sel.dataset.key === key) return;
  sel.dataset.key = key;
  sel.length = 1;
  for (const p of presets) sel.add(new Option(`${p.name} (${p.frequency})`, p.frequency));
}

function renderPresets() {
  const box = $("#presets");
  box.replaceChildren();
  presets.forEach((p, i) => {
    const chip = document.createElement("span");
    chip.textContent = `${p.name} · ${p.frequency}`;
    const del = document.createElement("button");
    del.textContent = "×";
    del.title = "삭제";
    del.onclick = async () => {
      presets = await api("/api/presets", { method: "PUT", body: JSON.stringify(presets.filter((_, j) => j !== i)) });
      renderPresets();
    };
    chip.append(del);
    box.append(chip);
  });
  for (const c of cards.values()) fillPresetSelect($(".presetSel", c));
}

$("#presetForm").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  presets = await api("/api/presets", {
    method: "PUT",
    body: JSON.stringify([...presets, { name: f.name.value.trim(), frequency: f.frequency.value.trim() }]),
  });
  f.reset();
  renderPresets();
};

function fmt(v, d = 0) { return v == null ? "" : typeof v === "number" ? v.toFixed(d) : v; }

async function refreshAdsb() {
  try {
    const d = await api("/api/adsb");
    if (!d.available) { $("#adsbSummary").textContent = d.error; return; }
    if (d.tar1090_url) {
      // "/tar1090/" 처럼 경로만 주어지면 같은 호스트의 80번(lighttpd)으로 연결
      $("#mapLink").href = d.tar1090_url.startsWith("/")
        ? `${location.protocol}//${location.hostname}${d.tar1090_url}` : d.tar1090_url;
    }
    $("#adsbSummary").textContent =
      `항공기 ${d.total}대 (위치 수신 ${d.with_position} · Mode S 전용 ${d.mode_s_only}) · 누적 메시지 ${d.messages ?? "-"}`;
    const tb = $("#aircraft");
    tb.replaceChildren();
    for (const a of d.aircraft) {
      const tr = document.createElement("tr");
      const cells = [a.hex, a.flight, a.squawk, fmt(a.alt), fmt(a.gs), a.lat != null ? `${a.lat.toFixed(3)}, ${a.lon.toFixed(3)}` : "",
        a.type, fmt(a.rssi, 1), fmt(a.seen, 0)];
      for (const c of cells) { const td = document.createElement("td"); td.textContent = c ?? ""; td.className = "mono"; tr.append(td); }
      if (["7500", "7600", "7700"].includes(a.squawk)) tr.style.color = "var(--bad)";
      tb.append(tr);
    }
  } catch (e) { $("#adsbSummary").textContent = e.message; }
}

async function refreshReceivers() {
  try { (await api("/api/receivers")).forEach(renderReceiver); }
  catch (e) { $("#receivers").textContent = e.message; cards.clear(); }
}

async function refreshAll() {
  try { presets = await api("/api/presets"); renderPresets(); } catch (_) {}
  await refreshReceivers();
  await refreshAdsb();
}

refreshAll();
setInterval(refreshReceivers, 5000);
setInterval(refreshAdsb, 2000);
