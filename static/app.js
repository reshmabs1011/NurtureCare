const $ = (id) => document.getElementById(id);
const queueKey = "nurturecare_sync_queue_v1";
const draftKey = "nurturecare_draft_v1";
let bpChart = null;
let lastScreening = null;

function readQueue() {
  try { return JSON.parse(localStorage.getItem(queueKey) || "[]"); } catch { return []; }
}
function writeQueue(items) {
  localStorage.setItem(queueKey, JSON.stringify(items));
  updateQueueUI();
}
function updateQueueUI() {
  const count = readQueue().length;
  $("statQueue").textContent = count;
  $("queueLabel").textContent = `${count} waiting`;
}
function showView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  closeDrawer();
  if (name === "reports") loadReports();
  if (name === "home") loadHome();
  window.currentNurtureView = name;
}
function openDrawer() {
  $("drawer").classList.add("open");
  $("drawerBackdrop").classList.add("show");
}
function closeDrawer() {
  $("drawer").classList.remove("open");
  $("drawerBackdrop").classList.remove("show");
}
function showUrgentModal() { $("urgentModal").hidden = false; }
function closeUrgentModal() { $("urgentModal").hidden = true; }

document.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));
document.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => showView(b.dataset.go)));
document.querySelectorAll("[data-view-link]").forEach(b => b.addEventListener("click", e => { e.preventDefault(); showView(b.dataset.viewLink); }));
$("menuOpen").addEventListener("click", openDrawer);
$("menuClose").addEventListener("click", closeDrawer);
$("drawerBackdrop").addEventListener("click", closeDrawer);
$("emergencyQuick").addEventListener("click", () => showView("emergency"));
$("urgentDismiss").addEventListener("click", closeUrgentModal);
$("urgentModal").addEventListener("click", e => { if (e.target === $("urgentModal")) closeUrgentModal(); });
$("closeResult").addEventListener("click", () => $("resultOverlay").hidden = true);
$("resultDone").addEventListener("click", () => $("resultOverlay").hidden = true);
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeDrawer(); closeUrgentModal(); $("resultOverlay").hidden = true; } });

function formDataObject() {
  const form = $("screenForm");
  const fd = new FormData(form);
  const obj = {};
  for (const [k, v] of fd.entries()) {
    if (k === "symptoms") (obj.symptoms ||= []).push(v);
    else obj[k] = v;
  }
  return obj;
}
function qualityCheck(showEmpty = false) {
  const d = formDataObject();
  const messages = [];
  if (!d.weeks && !d.systolic && !d.diastolic && !showEmpty) {
    $("qualityMessage").className = "quality-message";
    $("qualityMessage").textContent = "Data quality check: complete the form to validate entries.";
    return false;
  }
  const weeks = Number(d.weeks), sys = Number(d.systolic), dia = Number(d.diastolic);
  if (!d.name?.trim()) messages.push("Enter a name or demo ID.");
  if (!d.weeks || !Number.isInteger(weeks) || weeks < 1 || weeks > 45) messages.push("Pregnancy week must be a whole number from 1 to 45.");
  if (!d.systolic || !Number.isInteger(sys) || sys < 50 || sys > 300) messages.push("Check the systolic BP value (form plausibility range 50–300).");
  if (!d.diastolic || !Number.isInteger(dia) || dia < 30 || dia > 200) messages.push("Check the diastolic BP value (form plausibility range 30–200).");
  if (d.systolic && d.diastolic && sys <= dia) messages.push("Systolic BP should be higher than diastolic BP.");
  const el = $("qualityMessage");
  el.className = "quality-message " + (messages.length ? "error" : "good");
  el.textContent = messages.length ? "Please check: " + messages.join(" ") : "Data quality check passed for basic form plausibility. This does not confirm medical safety.";
  return messages.length === 0;
}
["name", "weeks", "systolic", "diastolic"].forEach(id => $(id).addEventListener("input", () => qualityCheck()));
document.querySelectorAll('input[name="symptoms"]').forEach(el => el.addEventListener("change", () => {
  const severe = ["heavy_bleeding", "seizure", "difficulty_breathing", "severe_headache_vision", "severe_abdominal_pain", "reduced_fetal_movement"];
  if (el.checked && severe.includes(el.value)) showUrgentModal();
}));

$("saveDraft").addEventListener("click", () => {
  const data = formDataObject();
  localStorage.setItem(draftKey, JSON.stringify(data));
  if (navigator.onLine) {
    const queue = readQueue();
    queue.push({ ...data, client_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}` });
    writeQueue(queue);
    syncQueue();
    $("qualityMessage").textContent = "Draft saved locally. A sync attempt will run when connected.";
  } else {
    const queue = readQueue();
    queue.push({ ...data, client_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}` });
    writeQueue(queue);
    $("qualityMessage").textContent = "Saved in this browser's local queue. It has not been sent to the server.";
  }
});
$("screenForm").addEventListener("submit", async e => {
  e.preventDefault();
  if (!qualityCheck(true)) return;
  const data = formDataObject();
  const severe = ["heavy_bleeding", "seizure", "difficulty_breathing", "severe_headache_vision", "severe_abdominal_pain", "reduced_fetal_movement"];
  if (data.symptoms?.some(s => severe.includes(s))) {
    showUrgentModal();
    // Still allow a record for demonstration, but urgent guidance takes priority.
  }
  if (!navigator.onLine) {
    const queue = readQueue();
    queue.push({ ...data, client_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}` });
    writeQueue(queue);
    localStorage.setItem(draftKey, JSON.stringify(data));
    showResult({level:"notice", explanation:"You are offline. This entry is queued in this browser and has NOT been saved to the server yet. Severe symptoms require urgent medical care now; do not wait for synchronization."});
    return;
  }
  try {
    const response = await fetch("/api/screen", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) { $("qualityMessage").className = "quality-message error"; $("qualityMessage").textContent = (result.errors || ["Unable to validate entry."]).join(" "); return; }
    lastScreening = result;
    localStorage.removeItem(draftKey);
    showResult(result);
    loadHome();
  } catch {
    const queue = readQueue();
    queue.push({ ...data, client_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}` });
    writeQueue(queue);
    showResult({level:"notice", explanation:"The server could not be reached. This entry has been queued in this browser and has not been confirmed as saved. Seek care directly for urgent symptoms."});
  }
});
function showResult(result) {
  const level = result.level || "notice";
  const dialog = document.querySelector(".result-dialog");
  dialog.classList.toggle("urgent", level === "urgent");
  $("resultSymbol").textContent = level === "urgent" ? "!" : level === "review" ? "↗" : "✓";
  $("resultTitle").textContent = level === "urgent" ? "Urgent medical guidance" : level === "review" ? "Prompt clinical review" : "Screening explanation";
  $("resultText").textContent = result.explanation || "No explanation available.";
  $("resultOverlay").hidden = false;
  if (level === "urgent") showUrgentModal();
}
async function loadReports() {
  try {
    const response = await fetch("/api/reports");
    const rows = await response.json();
    $("reportRows").innerHTML = "";
    if (!rows.length) {
      $("reportRows").innerHTML = '<tr><td colspan="6">No saved screening records yet. Use Health Screening to add a demo entry.</td></tr>';
    } else {
      rows.forEach(r => {
        const tr = document.createElement("tr");
        const date = document.createElement("td"); date.textContent = (r.created_at || "").replace("T", " ");
        const name = document.createElement("td"); name.textContent = r.name;
        const weeks = document.createElement("td"); weeks.textContent = r.weeks;
        const bp = document.createElement("td"); bp.textContent = `${r.systolic}/${r.diastolic}`;
        const explanation = document.createElement("td"); explanation.textContent = r.explanation;
        const statusCell = document.createElement("td");
        const select = document.createElement("select"); select.className = "status-select";
        ["Not marked","Referred","Follow-up needed","Completed"].forEach(s => { const o = document.createElement("option"); o.value=s; o.textContent=s; if (r.referral_status === s) o.selected=true; select.appendChild(o); });
        select.addEventListener("change", async () => {
          try { await fetch(`/api/reports/${r.id}/referral`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:select.value})}); }
          catch { alert("Could not update referral status. Check your connection."); }
        });
        statusCell.appendChild(select);
        tr.append(date,name,weeks,bp,explanation,statusCell);
        $("reportRows").appendChild(tr);
      });
    }
    $("statTotal").textContent = rows.length;
    $("statReview").textContent = rows.filter(r => ["review","urgent"].includes(r.result_level)).length;
  } catch {
    $("reportRows").innerHTML = '<tr><td colspan="6">Unable to load server reports. Offline drafts are shown in the queue count, not as confirmed records.</td></tr>';
  }
  updateQueueUI();
}
async function loadHome() {
  try {
    const response = await fetch("/api/reports");
    const rows = await response.json();
    $("statTotal").textContent = rows.length;
    $("statReview").textContent = rows.filter(r => ["review","urgent"].includes(r.result_level)).length;
    drawChart(rows);
  } catch { drawChart([]); }
  updateQueueUI();
}
function drawChart(rows) {
  const sorted = rows.slice().reverse().slice(-12);
  $("chartEmpty").style.display = sorted.length ? "none" : "block";
  const canvas = $("bpChart");
  if (!window.Chart || !canvas) return;
  if (bpChart) bpChart.destroy();
  bpChart = new Chart(canvas, {
    type:"line",
    data:{
      labels:sorted.map((r,i)=>`#${i+1}`),
      datasets:[
        {label:"Systolic",data:sorted.map(r=>r.systolic),borderColor:"#0F4C5C",backgroundColor:"#0F4C5C18",tension:.3},
        {label:"Diastolic",data:sorted.map(r=>r.diastolic),borderColor:"#E36414",backgroundColor:"#E3641418",tension:.3}
      ]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{boxWidth:10,usePointStyle:true,font:{size:11}}}},scales:{y:{beginAtZero:false,ticks:{font:{size:10}}},x:{ticks:{font:{size:10}}}}}
  });
}
async function syncQueue() {
  const items = readQueue();
  if (!items.length) { updateQueueUI(); return; }
  if (!navigator.onLine) { $("onlineText").textContent = "Offline · drafts remain on this device"; return; }
  try {
    const response = await fetch("/api/sync", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({items})});
    if (!response.ok) throw new Error("sync failed");
    const result = await response.json();
    const syncedIds = new Set((result.synced || []).map(x => x.client_id));
    const remaining = items.filter(x => !syncedIds.has(x.client_id));
    writeQueue(remaining);
    $("onlineText").textContent = `Online · ${result.synced.length} draft(s) synced`;
    if (result.rejected?.length) $("onlineText").textContent += ` · ${result.rejected.length} need correction`;
    loadHome();
  } catch { $("onlineText").textContent = "Online, but sync could not be confirmed"; }
}
function updateConnection() {
  $("onlineDot").classList.toggle("online", navigator.onLine);
  $("onlineText").textContent = navigator.onLine ? "Online" : "Offline · drafts stay on this device";
}
$("syncNow").addEventListener("click", syncQueue);
$("refreshReports").addEventListener("click", loadReports);
window.addEventListener("online", () => { updateConnection(); syncQueue(); });
window.addEventListener("offline", updateConnection);
$("mapLocation").addEventListener("input", () => {
  const q = $("mapLocation").value.trim();
  $("mapLink").href = `https://www.google.com/maps/search/${encodeURIComponent(q ? "maternity hospital " + q : "maternity hospital near me")}`;
});
$("makeSms").addEventListener("click", () => {
  const detail = $("smsDetails").value.trim();
  const status = $("smsStatus");

  if (!detail) {
    status.textContent = "Please enter message details before creating the referral.";
    $("smsDetails").focus();
    return;
  }

  const msg = `NurtureCare AI referral draft: ${detail}. Please contact me to coordinate care.`;

  $("smsDetails").value = msg;
  status.textContent = "Draft prepared. Nothing has been sent. Review the message before opening your SMS app.";
});
$("openSms").addEventListener("click", () => {
  const phone = $("smsContact").value.trim().replace(/[^\d+]/g, "");
  const body = encodeURIComponent($("smsDetails").value.trim() || "Maternal health support request. Please contact me.");
  window.location.href = `sms:${phone}?body=${body}`;
  $("smsStatus").textContent = "Your device may open an SMS composer. The message is not sent automatically.";
});
$("languageSelect").addEventListener("change", () => {
  if ($("languageSelect").value !== "en") {
    alert("This starter includes language options in the menu, but full translations are not yet implemented. English remains the interface language.");
    $("languageSelect").value = "en";
  }
});
function restoreDraft() {
  try {
    const d = JSON.parse(localStorage.getItem(draftKey) || "null");
    if (!d) return;
    ["name","weeks","systolic","diastolic"].forEach(k => { if (d[k] != null) $(k).value = d[k]; });
    document.querySelectorAll('input[name="symptoms"]').forEach(el => el.checked = (d.symptoms || []).includes(el.value));
    qualityCheck();
  } catch {}
}
restoreDraft();
updateConnection();
updateQueueUI();
loadHome();
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

// Experimental machine-learning demo form
const mlDemoForm = document.getElementById('mlDemoForm');
const mlResult = document.getElementById('mlResult');
if (mlDemoForm && mlResult) {
  mlDemoForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(mlDemoForm).entries());
    for (const key of Object.keys(payload)) payload[key] = Number(payload[key]);
    mlResult.hidden = false;
    mlResult.className = 'ml-result loading';
    mlResult.innerHTML = '<span class="result-kicker">AI DEMO RESULT</span><strong class="prediction-value">Checking inputs…</strong><p>Please wait while the experimental model responds.</p>';
    try {
      const response = await fetch('/api/ml-demo', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || 'The model could not process these inputs.');
      const label = String(result.demo_prediction || 'No prediction');
      const safeLabel = label.replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      mlResult.className = 'ml-result';
      mlResult.innerHTML = `<span class="result-kicker">EXPERIMENTAL MODEL OUTPUT</span><strong class="prediction-value">${safeLabel}</strong><p>${(result.notice || 'Experimental output only.').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}</p>`;
    } catch (error) {
      mlResult.className = 'ml-result error';
      mlResult.innerHTML = `<span class="result-kicker">MODEL RESPONSE</span><strong class="prediction-value">Unable to show prediction</strong><p>${String(error.message || 'Check that Flask is running.').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}</p>`;
    }
  });
}
