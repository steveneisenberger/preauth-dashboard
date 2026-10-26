# Lists Ortho2 Edge's clickable controls (buttons, menus, tabs, dropdowns, checkboxes) so export_edge.py can find them.
# Skips lists, grids, text and input fields so no patient information is printed.
# Usage: python inspect_edge.py <label>
import sys
from pywinauto import Desktop

label = sys.argv[1] if len(sys.argv) > 1 else "screen"
KEEP = {"Button", "MenuItem", "TabItem", "ComboBox", "CheckBox", "RadioButton", "Hyperlink", "SplitButton", "Menu", "ToolBar"}

wins = [w for w in Desktop(backend="uia").windows() if w.window_text().startswith("Ortho2 Edge")]
if not wins:
    sys.exit("Ortho2 Edge window not found")
print(f"=== {label}: {len(wins)} Edge window(s) ===")
for w in wins:
    print(f"## WINDOW: {w.window_text()}")
    seen = 0
    for e in w.descendants():
        info = e.element_info
        if info.control_type in KEEP:
            name = (info.name or "").replace("\n", " ")[:50]
            print(f"{info.control_type} | {name} | id={info.automation_id} | enabled={e.is_enabled()}")
            seen += 1
    print(f"## {seen} controls")
