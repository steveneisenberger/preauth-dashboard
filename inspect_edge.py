# Lists Ortho2 Edge's controls so export_edge.py can find them.
# Default/--wide never print lists, grids, text, input fields or images, so no patient information is shown.
# Usage: python inspect_edge.py <label> [--wide] [--trees] [--under <automation_id>]
#   --wide    also list other control types, but only ones with a developer ID
#   --trees   list tree item names (report list / subgroup tree; not patient data)
#   --under X list EVERYTHING inside the control with id X (only use on navigation areas, never on patient lists)
import sys, collections
from pywinauto import Desktop

args = sys.argv[1:]
label = args[0] if args else "screen"
wide = "--wide" in args
trees = "--trees" in args
under = args[args.index("--under") + 1] if "--under" in args else None
menus = "--menus" in args
edits = "--edits" in args
find = args[args.index("--find") + 1] if "--find" in args else None
KEEP = {"Button", "MenuItem", "TabItem", "ComboBox", "CheckBox", "RadioButton", "Hyperlink", "SplitButton", "Menu", "ToolBar"}
NEVER = {"DataItem", "ListItem", "Text", "Edit", "Document", "DataGrid", "Table", "TreeItem", "Image",
         "ScrollBar", "Thumb", "Header", "HeaderItem", "List", "Tree", "ToolTip", "StatusBar"}

desk = Desktop(backend="uia")
main = [w for w in desk.windows() if w.window_text().startswith("Ortho2 Edge")]
if not main:
    sys.exit("Ortho2 Edge window not found")
pid = main[0].process_id()
wins = [w for w in desk.windows() if w.process_id() == pid]     # main window + any Edge dialogs/menus
print(f"=== {label}: {len(wins)} Edge window(s) ===")

def line(e, with_value=False):
    i = e.element_info
    out = f"{i.control_type} | {(i.name or '').replace(chr(10), ' ')[:40]} | id={i.automation_id or ''} | enabled={e.is_enabled()}"
    if with_value:
        try:
            v = e.legacy_properties().get("Value", "")
            if v: out += f" | value={str(v)[:60]}"
        except Exception: pass
    return out

if menus:   # any open drop-down menu anywhere on screen (menu item names only)
    print("=== open menus ===")
    for w in desk.windows():
        for e in w.descendants(control_type="MenuItem"):
            print(f"[{w.window_text()[:30]} | pid={w.process_id()}] " + line(e))

if find:    # locate controls by their exact visible name (e.g. a ribbon tab), with parent chain
    for w in wins:
        for e in w.descendants():
            if (e.element_info.name or "").strip().lower() == find.lower():
                chain, p = [], e.parent()
                while p is not None and len(chain) < 4:
                    pi = p.element_info; chain.append(f"{pi.control_type}#{pi.automation_id or ''}"); p = p.parent()
                print(line(e) + " | parents=" + " < ".join(chain))
    sys.exit(0)

for w in wins:
    print(f"## WINDOW: {w.window_text()} | class={w.class_name()}")
    if edits:   # text boxes in Edge's pop-up dialogs only (e.g. export folder / file name), never the main window
        if not w.window_text().startswith("Ortho2 Edge"):
            for e in w.descendants(control_type="Edit"):
                print(line(e, with_value=True))
        continue
    if under:
        roots = [e for e in w.descendants() if e.element_info.automation_id == under]
        for r in roots:
            print(f"-- inside {under} --")
            for e in r.descendants():
                if e.element_info.control_type in ("Image", "Thumb", "ScrollBar"): continue
                print(line(e, with_value=True))
        continue
    types = collections.Counter(); seen = 0
    for e in w.descendants():
        info = e.element_info; ct = info.control_type; types[ct] += 1
        show = ct in KEEP or (wide and ct not in NEVER and info.automation_id) or (trees and ct == "TreeItem")
        if show:
            print(line(e)); seen += 1
    print(f"## {seen} shown. All control types: " + ", ".join(f"{k}={v}" for k, v in types.most_common()))
