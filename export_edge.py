# Exports Ortho2 Edge "Patient List - Custom" to PDF, finding every control by its ID or name (no fixed screen positions).
# Usage: python export_edge.py <output.pdf>
# Route: Reporting tab > Recent Reports > Patient List - Custom > Run > (verify 7 statuses + Office) > View > Export > PDF
# Exit 0 = PDF saved. Any problem = message + exit 1 (run_preauth.ps1 then deletes leftovers and resumes Rob).
import sys, os, time, glob, shutil
from pywinauto import Desktop
from pywinauto.keyboard import send_keys

OUT = sys.argv[1]
TMP = os.path.join(os.path.dirname(OUT), "tmp")
REPORT = "Patient List - Custom"
WANT = {"MC", "SUB", "APP-MC", "REJ-MC", "(1) MC PH1", "(1) PH1SUB", "(1)PH1 APP"}
desk = Desktop(backend="uia")

def log(m): print(f"  [{time.strftime('%H:%M:%S')}] {m}", flush=True)
def fail(m): log("FAILED: " + m); close_dialogs(); os._exit(1)

def edge():
    w = [w for w in desk.windows() if w.window_text().startswith("Ortho2 Edge")]
    if not w: fail("Ortho2 Edge is not open")
    return w[0]

def pid_windows(): p = edge().process_id(); return [w for w in desk.windows() if w.process_id() == p]

_last_err = [None]
def find(root, timeout=30, title=None, auto_id=None, control_type=None):
    """Wait for a control under root matching visible name / developer ID / control type.
    Same full-tree scan as inspect_edge.py (known to work on this PC); all matching done here."""
    end = time.time() + timeout
    while True:
        try:
            for e in root.descendants():
                i = e.element_info
                if control_type is not None and i.control_type != control_type: continue
                if title is not None and (i.name or "").strip().lower() != title.lower(): continue
                if auto_id is not None and (i.automation_id or "") != auto_id: continue
                return e
        except Exception as ex:
            if str(ex) != _last_err[0]: _last_err[0] = str(ex); log(f"(lookup retry: {ex})")
        if time.time() >= end: return None
        time.sleep(0.5)

def describe(root, title):
    """For error messages: every control with this visible name (type + ID), no patient data."""
    try:
        return "; ".join(f"{e.element_info.control_type}#{e.element_info.automation_id or ''}"
                         for e in root.descendants() if (e.element_info.name or "").strip().lower() == title.lower()) or "none"
    except Exception as ex: return f"scan error {ex}"

def wait_enabled(ctrl_fn, timeout, what):
    end = time.time() + timeout
    while time.time() < end:
        c = ctrl_fn()
        if c is not None and c.is_enabled(): return c
        time.sleep(1)
    fail(f"timed out waiting for {what}")

def press(ctrl, what):
    """Press a button without the mouse and without blocking.
    WinForms/Win32 buttons have a real window handle: post BM_CLICK to it. A posted message is
    handled by Edge's UI thread even if another window (the 'Exporting Report...' spinner) sits
    on top of the button, and it returns at once even when the button opens a modal window
    (invoke() blocks until that window closes; click_input() misses when something covers it)."""
    import ctypes
    h = ctrl.element_info.handle
    if h:
        ctypes.windll.user32.PostMessageW(h, 0x00F5, 0, 0)   # BM_CLICK
        log(f"{what}: posted click to handle {h}")
        return True
    log(f"{what}: no window handle, using mouse click")
    ctrl.click_input()
    return False

def close_dialogs():
    # must never call fail()/edge() (that caused an endless loop when Edge was busy)
    try:
        ws = [w for w in desk.windows() if w.window_text().startswith("Ortho2 Edge")]
        if not ws: return
        p = ws[0].process_id()
        for w in desk.windows():
            if w.process_id() == p and w.window_text() in ("Save As", "Export", "Browse For Folder", "Select Folder"):
                try: w.close()
                except Exception: pass
    except Exception: pass

def _on_crash(t, v, tb):
    import traceback; traceback.print_exception(t, v, tb)
    close_dialogs(); os._exit(1)
sys.excepthook = _on_crash   # any unexpected error still closes Edge's Export window

# ---------- 1. Bring Edge forward, open Reporting > Recent Reports ----------
main = edge()
main.set_focus(); time.sleep(1)
log("Opening Reporting tab")
tab = find(main, title="Reporting", auto_id="PART_LabelContent", timeout=10) or find(main, title="Reporting", timeout=2)
if tab is None: fail(f"Reporting tab not found. Window: {main.window_text()!r}. Controls named Reporting: {describe(main, 'Reporting')}")
log(f"Found Reporting: {tab.element_info.control_type}#{tab.element_info.automation_id}")
tab.click_input(); time.sleep(2)

reuse = False
if find(main, auto_id="lstStatuses", control_type="List", timeout=3) is not None:
    reuse = True
    log(f"{REPORT} is already open; re-using it (will click View for fresh numbers)")
else:
    grid = find(main, auto_id="lstRecentReports", control_type="DataGrid", timeout=15)
    if grid is None: fail("Recent Reports list not found")
    row = find(grid, title=REPORT, control_type="Text", timeout=10)
    if row is None: fail(f"'{REPORT}' not in Recent Reports")
    log(f"Selecting {REPORT}")
    run_ok = lambda: (lambda b: b is not None and b.is_enabled())(find(main, auto_id="btnRunRecentReport", timeout=1))
    item = row
    for _ in range(4):                                 # walk up from the text to its grid row
        if item.element_info.control_type == "DataItem": break
        item = item.parent()
    try: item.iface_selection_item.Select()           # select the row directly
    except Exception: pass
    time.sleep(1)
    if not run_ok(): row.click_input(); time.sleep(2)  # then try a normal click
    if run_ok():
        find(main, auto_id="btnRunRecentReport", timeout=2).invoke()
    else:
        log("Run stayed greyed out; double-clicking the report instead")
        row.double_click_input()
    if find(main, auto_id="lstStatuses", control_type="List", timeout=30) is None:
        fail(f"report did not open. Run enabled={run_ok()}. Controls named '{REPORT}': {describe(main, REPORT)}")
    time.sleep(3)

# ---------- 2. Verify the saved settings (never changes them) ----------
time.sleep(2)   # settings panel opens; View may be greyed while Run loads the report
lst = find(main, auto_id="lstStatuses", control_type="List", timeout=15)
if lst is None: fail("status list not found")
checked, seen = set(), set()
try:
    sc = lst.iface_scroll
    sc.SetScrollPercent(-1, 0); time.sleep(0.5)
    for step in range(0, 101, 5):
        sc.SetScrollPercent(-1, step); time.sleep(0.3)
        for cb in lst.descendants(control_type="CheckBox"):
            n = cb.window_text(); seen.add(n)
            if cb.get_toggle_state() == 1: checked.add(n)
    sc.SetScrollPercent(-1, 0)
except Exception as e:
    fail(f"could not read status list ({e})")
log(f"Statuses checked: {sorted(checked)}  (scanned {len(seen)})")
if checked != WANT:
    fail(f"status selection changed. Missing: {sorted(WANT - checked)}  Extra: {sorted(checked - WANT)}")
office = find(main, auto_id="cboOffice", control_type="ComboBox", timeout=5)
try: office_txt = office.selected_text()
except Exception: office_txt = (office.legacy_properties().get("Value", "") if office else "")
log(f"Office: {office_txt!r}")
if "all" not in str(office_txt).lower():
    fail(f"Office is set to {office_txt!r}, expected All")

# ---------- 3. Wait for the report to load (Run usually starts it; click View only if it didn't) ----------
# While Edge is loading, View is greyed out. Loaded = Export becomes clickable.
# If View stays clickable for 15 s with Export still grey, nothing is loading, so click View once.
if reuse:
    # an already-open report may show old numbers: wait until View is clickable, click it, then wait for the new load to start
    v = wait_enabled(lambda: find(main, auto_id="btnView", timeout=2), 600, "View button on open report")
    log("Clicking View to refresh"); 
    try: v.invoke()
    except Exception: v.click_input()
    end = time.time() + 60
    while time.time() < end:
        eb = find(main, auto_id="btnExport", timeout=2)
        if eb is not None and not eb.is_enabled(): break
        time.sleep(1)
log("Waiting for report to load (up to 10 min)")
# Freshness guard: only accept the report once Export has been seen greyed out (a load happened after Run/View).
saw_loading = False
if reuse:
    saw_loading = True   # the reuse branch above already waited for Export to grey out
end, idle_since, viewed = time.time() + 600, None, reuse
export_btn = None
while time.time() < end:
    eb = find(main, auto_id="btnExport", timeout=2)
    if eb is not None and not eb.is_enabled():
        saw_loading = True
    elif eb is not None and eb.is_enabled():
        if saw_loading or viewed:
            export_btn = eb; break
        # Export is clickable but no load was seen: could be an old render. Refresh once with View.
        v = find(main, auto_id="btnView", timeout=2)
        if v is not None and v.is_enabled():
            log("Report looks already loaded; clicking View to make sure numbers are fresh")
            try: v.invoke()
            except Exception:
                try: v.click_input()
                except Exception: pass
            viewed = True
            t = time.time() + 60
            while time.time() < t:
                e2 = find(main, auto_id="btnExport", timeout=2)
                if e2 is not None and not e2.is_enabled(): saw_loading = True; break
                time.sleep(0.5)
            continue
    v = find(main, auto_id="btnView", timeout=2)
    if v is not None and v.is_enabled() and not viewed and not (eb is not None and eb.is_enabled()):
        idle_since = idle_since or time.time()
        if time.time() - idle_since >= 15:
            log("Report not loading on its own; clicking View")
            try: v.invoke()
            except Exception:
                try: v.click_input()
                except Exception: pass
            viewed, idle_since = True, None
    else:
        idle_since = None
    time.sleep(2)
if export_btn is None: fail("report did not finish loading within 10 min")
log("Report loaded")

# Export becomes clickable while the viewer is still rendering pages (the "1/434" counter keeps
# climbing to the real total). Exporting then would silently undercount, so wait until the
# page total has held still for 15 s. Non-fatal if the counter can't be found.
import re
def page_total():
    try:
        for e in main.descendants(control_type="Text"):
            m = re.fullmatch(r"\s*\d+\s*/\s*(\d+)\s*", e.element_info.name or "")
            if m: return int(m.group(1))
    except Exception: pass
    return None
end, last, stable_since = time.time() + 300, None, None
while time.time() < end:
    n = page_total()
    if n is None:
        log("(page counter not found; waiting 15 s instead)"); time.sleep(15); break
    if n != last: last, stable_since = n, time.time(); log(f"Pages rendered so far: {n}")
    elif time.time() - stable_since >= 15: break
    time.sleep(3)
if last is not None: log(f"Report pages: {last}")
time.sleep(2)

# ---------- 4. Export > PDF ----------
os.makedirs(TMP, exist_ok=True)
for f in glob.glob(os.path.join(TMP, "*")): os.remove(f)
log("Export > PDF")
def find_pdf_item():
    # only Edge's own windows (the drop-down is an Edge pop-up); scanning Chrome/Claude trees is far too slow
    for w in pid_windows():
        try:
            for e in w.descendants():
                if (e.element_info.name or "").strip() == "PDF":
                    return e
        except Exception: pass
    return None

pdf_item = None
for attempt in range(3):
    export_btn = find(main, auto_id="btnExport", timeout=5) or export_btn
    export_btn.click_input(); time.sleep(2)
    end = time.time() + 15
    while pdf_item is None and time.time() < end:
        pdf_item = find_pdf_item()
        if pdf_item is None: time.sleep(0.5)
    if pdf_item is not None: break
    log(f"Export menu not seen (try {attempt + 1}); pressing Esc and retrying")
    send_keys("{ESC}"); time.sleep(2)
if pdf_item is None: fail("PDF option not found in Export menu")
log(f"PDF option: {pdf_item.element_info.control_type}")
pdf_item.click_input(); time.sleep(3)

dlg = None
end = time.time() + 60
while dlg is None and time.time() < end:
    dlg = next((w for w in pid_windows() if w.window_text() == "Export"), None); time.sleep(1)
if dlg is None: fail("Export window did not open")
box = find(dlg, auto_id="_exportDirectoryTextBox", control_type="Edit", timeout=10)
if box is None: fail("export folder box not found")
def export_ready():
    b = find(dlg, auto_id="_exportButton", timeout=1); return b is not None and b.is_enabled()

# Edge's "Export to" box is read-only; Browse opens a standard Windows "Save As" window (confirmed
# on screen Oct 28: it starts in Edge's Program Files folder). Type the full file path into its
# File name box and click Save; Edge then fills the box with that path and enables Export.
target = os.path.join(TMP, "preauth.pdf")
log("Browse > Save As")
before = {w.handle for w in pid_windows()}
browse = find(dlg, auto_id="_exportDirectoryButton", timeout=5)
if browse is None: fail("Browse button not found in Export window")
def find_saveas():
    s = next((w for w in pid_windows() if w.handle not in before and w.window_text() == "Save As"), None)
    if s is None:   # common dialogs are sometimes owned by another process; fall back to any "Save As"
        s = next((w for w in desk.windows() if w.window_text() == "Save As"), None)
    return s
def wait_saveas(secs):
    s, end = None, time.time() + secs
    while s is None and time.time() < end:
        time.sleep(1); s = find_saveas()
    return s
posted = press(browse, "Browse")
saveas = wait_saveas(20)
if saveas is None and posted:
    log("Save As not seen after posted click; trying a mouse click on Browse")
    try: dlg.set_focus()
    except Exception: pass
    browse.click_input()
    saveas = wait_saveas(15)
if saveas is None: fail("Save As window did not open after Browse")
log("Save As open")
name_box = next((e for e in saveas.descendants() if e.element_info.control_type == "Edit"
                 and (e.element_info.automation_id or "") == "1001"), None)
if name_box is None:
    name_box = next((e for e in saveas.descendants() if e.element_info.control_type == "Edit"
                     and "file name" in (e.element_info.name or "").lower()), None)
if name_box is None: saveas.close(); fail("File name box not found in Save As")
try: name_box.set_edit_text(target)
except Exception:
    name_box.click_input(); send_keys("^a{BACKSPACE}"); send_keys(target, with_spaces=True)
time.sleep(1)
try: typed = name_box.legacy_properties().get("Value", "")
except Exception: typed = "?"
log(f"File name box now: {typed!r}")
save_btn = next((e for e in saveas.descendants() if e.element_info.control_type == "Button"
                 and (e.element_info.automation_id or "") == "1"), None)
if save_btn is not None: press(save_btn, "Save")
else: name_box.click_input(); send_keys("{ENTER}")
end = time.time() + 15
while time.time() < end and find_saveas() is not None: time.sleep(0.5)
if find_saveas() is not None:
    fail("Save As did not close (path rejected?)")
time.sleep(1)
v_ = box.legacy_properties().get("Value", "") if box else ""
log(f"Export-to box now: {v_!r}")
if TMP.lower() not in str(v_).lower():
    fail(f"Export-to box does not point at the temp folder; not exporting")
go = wait_enabled(lambda: find(dlg, auto_id="_exportButton", timeout=2), 15, "Export button in dialog")
log(f"Exporting to {TMP}")
press(go, "Export")   # not invoke: the export runs while Edge shows a busy window

# ---------- 5. Wait for the PDF to finish writing ----------
end, last = time.time() + 900, -1
pdf = None
while time.time() < end:
    files = glob.glob(os.path.join(TMP, "*.pdf"))
    if files:
        size = os.path.getsize(files[0])
        if size > 0 and size == last: pdf = files[0]; break
        last = size
    time.sleep(5)
if pdf is None: fail("PDF never appeared or kept growing for 15 min")
time.sleep(3)
close_dialogs()
if os.path.exists(OUT): os.remove(OUT)
shutil.move(pdf, OUT)
log(f"PDF saved ({os.path.getsize(OUT)//1024} KB)")

# ---------- 6. Leave Edge on Home for Rob ----------
try:
    home = find(edge(), title="Home", auto_id="PART_LabelContent", control_type="Text", timeout=5)
    if home: home.click_input()
except Exception: pass
sys.exit(0)
