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

def line(e):
    i = e.element_info
    return f"{i.control_type} | {(i.name or '').replace(chr(10), ' ')[:40]} | id={i.automation_id or ''} | enabled={e.is_enabled()}"

for w in wins:
    print(f"## WINDOW: {w.window_text()} | class={w.class_name()}")
    if under:
        roots = [e for e in w.descendants() if e.element_info.automation_id == under]
        for r in roots:
            print(f"-- inside {under} --")
            for e in r.descendants():
                if e.element_info.control_type in ("Image", "Thumb", "ScrollBar"): continue
                print(line(e))
        continue
    types = collections.Counter(); seen = 0
    for e in w.descendants():
        info = e.element_info; ct = info.control_type; types[ct] += 1
        show = ct in KEEP or (wide and ct not in NEVER and info.automation_id) or (trees and ct == "TreeItem")
        if show:
            print(line(e)); seen += 1
    print(f"## {seen} shown. All control types: " + ", ".join(f"{k}={v}" for k, v in types.most_common()))
