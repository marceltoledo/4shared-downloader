(function () {
  "use strict";

  function reload() {
    window.location.reload();
  }

  async function jsonFetch(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = (body && body.detail && body.detail.message) || body.detail || detail;
      } catch (e) {
        /* ignore non-JSON error bodies */
      }
      const err = new Error(detail);
      err.status = res.status;
      err.body = detail;
      throw err;
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // --- Dashboard: add account ---------------------------------------------
  const addForm = document.getElementById("add-account-form");
  if (addForm) {
    addForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = new FormData(addForm).get("url");
      try {
        await jsonFetch("/api/accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        reload();
      } catch (err) {
        alert("Could not add account: " + err.message);
      }
    });
  }

  // --- Dashboard: remove account -------------------------------------------
  document.querySelectorAll(".delete-account").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const folderId = btn.dataset.folderId;
      if (!confirm("Remove this account from the list? Downloaded files and history are kept.")) return;
      try {
        await jsonFetch("/api/accounts/" + encodeURIComponent(folderId), { method: "DELETE" });
        reload();
      } catch (err) {
        alert("Could not remove account: " + err.message);
      }
    });
  });

  // --- Dashboard: trigger a run --------------------------------------------
  const runForm = document.getElementById("run-form");
  if (runForm) {
    runForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const folderIds = Array.from(runForm.querySelectorAll('input[name="folder_ids"]:checked')).map((el) => el.value);
      if (folderIds.length === 0) {
        alert("Select at least one account to run.");
        return;
      }
      const formData = new FormData(runForm);
      const nameFilter = (formData.get("name_filter") || "").trim() || null;
      const destDir = (formData.get("dest_dir") || "").trim() || null;
      const limitRaw = (formData.get("limit") || "").trim();
      const limit = limitRaw ? Number(limitRaw) : null;
      const fileType = formData.get("file_type") || "all";
      try {
        const data = await jsonFetch("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            folder_ids: folderIds,
            name_filter: nameFilter,
            file_type: fileType,
            limit: limit,
            dest_dir: destDir,
          }),
        });
        window.location.href = "/runs/" + data.job_id;
      } catch (err) {
        if (err.status === 409 && err.body && err.body.job_id) {
          window.location.href = "/runs/" + err.body.job_id;
        } else {
          alert("Could not start run: " + err.message);
        }
      }
    });
  }

  // --- Run detail page: live log + status polling + cancel ----------------
  const jobId = window.DOWNLOADER_JOB_ID;
  if (jobId) {
    const logEl = document.getElementById("log");
    const statusEl = document.getElementById("run-status");
    const cancelBtn = document.getElementById("cancel-run");
    const optionsEl = document.getElementById("run-options");

    function renderRunOptions(job) {
      if (!optionsEl) return;
      const parts = [];
      if (job.name_filter) parts.push('contains "' + job.name_filter + '"');
      if (job.file_type && job.file_type !== "all") parts.push(job.file_type);
      if (job.limit) parts.push("limit " + job.limit + "/account");
      if (job.dest_dir) parts.push("→ " + job.dest_dir);
      optionsEl.textContent = parts.length ? "Filters: " + parts.join(" · ") : "";
    }

    let ended = false;

    const source = new EventSource("/api/runs/" + jobId + "/stream");
    source.onmessage = (event) => {
      logEl.textContent += event.data + "\n";
      logEl.scrollTop = logEl.scrollHeight;
    };
    source.onerror = () => {
      // EventSource retries automatically; nothing to do here.
    };
    // The server sends this once the job has reached a terminal status, so
    // the stream ends deliberately here rather than via EventSource's normal
    // auto-reconnect (which would otherwise open a new subscription and
    // replay the whole log again).
    source.addEventListener("end", (event) => {
      ended = true;
      source.close();
      statusEl.textContent = event.data;
      statusEl.className = "status status-" + event.data;
      if (cancelBtn) cancelBtn.disabled = true;
    });

    const terminalStatuses = new Set(["done", "error", "cancelled"]);
    async function pollStatus() {
      if (ended) return;
      try {
        const job = await jsonFetch("/api/runs/" + jobId);
        statusEl.textContent = job.status;
        statusEl.className = "status status-" + job.status;
        renderRunOptions(job);
        if (terminalStatuses.has(job.status)) {
          if (cancelBtn) cancelBtn.disabled = true;
          return;
        }
      } catch (err) {
        statusEl.textContent = "unknown";
      }
      setTimeout(pollStatus, 2000);
    }
    pollStatus();

    if (cancelBtn) {
      cancelBtn.addEventListener("click", async () => {
        try {
          await jsonFetch("/api/runs/" + jobId + "/cancel", { method: "POST" });
        } catch (err) {
          alert("Could not cancel run: " + err.message);
        }
      });
    }
  }
})();
