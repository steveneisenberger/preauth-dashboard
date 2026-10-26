# Lists Ortho2 Edge's clickable controls so export_edge.py can find them.
# Never prints lists, grids, text, input fields or images, so no patient information is shown.
# Usage: python inspect_edge.py <label> [--wide]
#   --wide also lists other control types (ribbon tabs, groups, panes), but only ones with a developer ID.
import sys, collections
from pywinauto import Desktop

label = sys.argv[1] if len(sys.argv) > 1 else "screen"
wide = "--wide" in sys.argv
KEEP = {"Button", "MenuItem", "TabItem", "ComboBox", "CheckBox", "RadioButton", "Hyperlink", "SplitButton", "Menu", "ToolBar"}
NEVER = {"DataItem", "ListItem", "Text", "Edit", "Document", "DataGrid", "Table", "TreeItem", "Image",
         "ScrollBar", "Thumb", "Header", "HeaderItem", "List", "Tree", "ToolTip", "StatusBar"}

wins = [w for w in Desktop(backend="uia").windows() if w.window_text().startswith("Ortho2 Edge")]
if not wins:
    sys.exit("Ortho2 Edge window not found")
print(f"=== {label}: {len(wins)} Edge window(s) ===")
for w in wins:
    print(f"## WINDOW: {w.window_text()}")
    types = collections.Counter(); seen = 0
    for e in w.descendants():
        info = e.element_info; ct = info.control_type; types[ct] += 1
        aid = info.automation_id or ""
        show = ct in KEEP or (wide and ct not in NEVER and aid)
        if show:
            name = (info.name or "").replace("\n", " ")[:40]
            print(f"{ct} | {name} | id={aid} | enabled={e.is_enabled()}")
            seen += 1
    print(f"## {seen} shown. All control types on screen: " + ", ".join(f"{k}={v}" for k, v in types.most_common()))
