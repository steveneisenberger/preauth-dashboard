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
def fail(m): log("FAILED: " + m); close_dialogs(); sys.exit(1)

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

def close_dialogs():
    try:
        for w in pid_windows():
            if w.window_text() == "Export": w.close()
    except Exception: pass

# ---------- 1. Bring Edge forward, open Reporting > Recent Reports ----------
main = edge()
main.set_focus(); time.sleep(1)
log("Opening Reporting tab")
tab = find(main, title="Reporting", auto_id="PART_LabelContent", timeout=10) or find(main, title="Reporting", timeout=2)
if tab is None: fail(f"Reporting tab not found. Window: {main.window_text()!r}. Controls named Reporting: {describe(main, 'Reporting')}")
log(f"Found Reporting: {tab.element_info.control_type}#{tab.element_info.automation_id}")
tab.click_input(); time.sleep(2)

grid = find(main, auto_id="lstRecentReports", control_type="DataGrid", timeout=15)
if grid is None: fail("Recent Reports list not found")
row = find(grid, title=REPORT, control_type="Text", timeout=10)
if row is None: fail(f"'{REPORT}' not in Recent Reports")
log(f"Selecting {REPORT}"); row.click_input(); time.sleep(1)
run = wait_enabled(lambda: find(main, auto_id="btnRunRecentReport", timeout=2), 15, "Run button")
run.invoke(); time.sleep(3)

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
log("Waiting for report to load (up to 10 min)")
end, idle_since, viewed = time.time() + 600, None, False
export_btn = None
while time.time() < end:
    eb = find(main, auto_id="btnExport", timeout=2)
    if eb is not None and eb.is_enabled():
        export_btn = eb; break
    v = find(main, auto_id="btnView", timeout=2)
    if v is not None and v.is_enabled() and not viewed:
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
time.sleep(5)

# ---------- 4. Export > PDF ----------
os.makedirs(TMP, exist_ok=True)
for f in glob.glob(os.path.join(TMP, "*")): os.remove(f)
log("Export > PDF")
export_btn.click_input(); time.sleep(2)
pdf_item = None
end = time.time() + 15
while pdf_item is None and time.time() < end:
    for w in desk.windows():
        try:
            hits = [e for e in w.descendants() if e.window_text().strip() == "PDF"]
            if hits: pdf_item = hits[0]; break
        except Exception: pass
    time.sleep(0.5)
if pdf_item is None: fail("PDF option not found in Export menu")
pdf_item.click_input(); time.sleep(3)

dlg = None
end = time.time() + 60
while dlg is None and time.time() < end:
    dlg = next((w for w in pid_windows() if w.window_text() == "Export"), None); time.sleep(1)
if dlg is None: fail("Export window did not open")
box = find(dlg, auto_id="_exportDirectoryTextBox", control_type="Edit", timeout=10)
if box is None: fail("export folder box not found")
box.set_edit_text(TMP); time.sleep(1)
go = wait_enabled(lambda: find(dlg, auto_id="_exportButton", timeout=2), 15, "Export button in dialog")
log(f"Exporting to {TMP}")
go.invoke()

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
