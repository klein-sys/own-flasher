---
title: "FlashDock — Tomorrow's Execution Plan & Master Prompt (v1.3.3)"
type: execution-plan
status: ready
version: 1.3.3
date: 2026-10-13
tags:
  - flashdock
  - execution-prompt
  - layout-restructuring
  - non-scrolling-tools-canvas
  - scrollable-sidebar
  - interactive-workflow-guide
  - virtual-keypad-fix
  - terminal-splitter
---

# FlashDock — Master Execution Prompt (Phase 24 / v1.3.3)

> **Instructions for Tomorrow:**
> Copy and paste the entire `/goal` block below into your conversation. It contains every layout fix, non-scrolling tools canvas requirement, scrollable sidebar & terminal setup, interactive guide overhaul, and the Virtual Keypad bug fix ready for autonomous execution.

---

```markdown
/goal

Execute a comprehensive layout streamlining, interactive guide overhaul, and bug fix sprint in FlashDock (Phase 24 / v1.3.3):
1. Fix the broken **Virtual Keypad (ADB)** in `HardwareKeyGuideDialog` so clicking Volume +, Volume -, Power, and D-Pad actually sends keypresses to connected devices.
2. Make the **Main Tools Canvas & Home Screen 100% non-scrollable**, fitting all 15 action cards and controls completely on screen at once.
3. Keep the **Left Navigation Sidebar comfortably scrollable** (smooth slim scrollbar for categories and reboot controls) alongside the **Live Activity Terminal** (scrollable command history and resizable splitter).
4. Overhaul the **Workflow & Function Guide** (`WorkflowGuideDialog`) so every tool is clickable, detailing both "How It Works" and "Step-by-Step How to Use It" with a 1-click "Launch Tool" button.

### Workspace Context & Standards
- Root: `C:\Users\dxzmw\.gemini\antigravity-ide\scratch\FlashDock`
- Target Files:
  - `flashdock/ui/widgets/key_guide_dialog.py` (`HardwareKeyGuideDialog`, `_send_keyevent`)
  - `flashdock/ui/main_window.py` (`_build_home_page`, `ActionCardButton`, `_tools_grid`, `_main_splitter`, `_show_key_guide`)
  - `flashdock/ui/widgets/phone_panel.py` (`PhoneControlPanel`, `_NavPillButton`)
  - `flashdock/ui/widgets/workflow_guide.py` (`WorkflowGuideDialog`)
  - `flashdock/ui/widgets/side_terminal.py` (`SideTerminalWidget`)
- Mandatory Standard: Enforce Section 4 of `.agents/skills/flashdock-workstation/SKILL.md` (bump version to `1.3.3`, 100% test pass, compile release, and push to GitHub).
- Version Increment: Bump version to `1.3.3` (patch release).

---

### Step-by-Step Implementation Specifications

#### 1. Fix Virtual Keypad (ADB) Not Working (`key_guide_dialog.py` & `main_window.py`)
- **Root Cause**:
  - In `flashdock/ui/widgets/key_guide_dialog.py` line 296, `_send_keyevent` calls:
    `self._adb.shell(["input", "keyevent", str(keycode)])` with a list `["input", "keyevent", ...]`.
    However, `ADB.shell()` in `flashdock/tools/adb.py` line 306 expects a single **string** command: `def shell(self, command: str, serial: str = "", ...)`.
    Passing a list results in Python joining it into `"['input', 'keyevent', '24']"` which ADB rejects as a malformed command! Furthermore, `serial` was not passed, so multiple devices cause ADB ambiguous errors.
- **Fix**:
  - In `flashdock/ui/widgets/key_guide_dialog.py`:
    - Update `_send_keyevent(self, keycode: int)` to pass a formatted string:
      `res = self._adb.shell(f"input keyevent {keycode}", serial=self._serial)`
    - Accept `serial: str = ""` in `HardwareKeyGuideDialog.__init__` and pass `serial=self._device_mgr.device.serial if self._device_mgr.device else ""` from `main_window.py`.
    - If no device is connected in normal ADB mode, show a clear warning banner: `"Please connect a device via USB debugging in normal System mode to use the virtual keypad."`

#### 2. Keep Left Sidebar Smoothly Scrollable (`phone_panel.py`)
- Retain the slim, elegant `QScrollArea` inside `PhoneControlPanel` with transparent track and smooth vertical scrollbar so all categories, custom tools, and bottom phone reboot controls can be scrolled comfortably on smaller laptop screens.
- Clean up button padding and font scale (`padding: 6px 10px; font-size: 11.5px`) so labels never get truncated or clip.

#### 3. Re-architect Main Home Tools Canvas to be 100% Non-Scrollable (`main_window.py`)
- **Header Compression**:
  - In `_build_home_page()`, merge quick utility buttons (`Setup Laptop`, `Key Guide`, `Workflow Guide`, `Self-Test`) directly onto the **Search & Filter row**.
  - Tighten Live Device HUD banner vertical margins (`device_hud.py`) to `6px`.
  - Reduce Home screen outer margins (`setContentsMargins(18, 6, 18, 6)`).
- **4-Column "HyperOS Control Chips" Grid**:
  - Arrange tools into **4 columns** instead of 3 (4 columns $\times$ 4 rows max for 15 tools).
  - Compact card height (`ActionCardButton`): reduce from `84px` down to **`52px`–`56px`**.
  - Display Action Title (`font-size: 11.5px; font-weight: 600;`) and category badge inline.
  - Move lengthy 2-line descriptions out of the card layout into rich tooltips (`setToolTip(desc)`).
- **Completely Eliminate ScrollArea on Main Home Canvas**:
  - Remove the outer `QScrollArea` from `_build_home_page()`.
  - Place `self._tools_grid` directly into the page layout with `self._tools_grid.setSpacing(8)`.
  - Ensure the entire Home tools view—from the top header down to the last row of cards and the bottom status bar—renders **100% visible on screen with zero vertical or horizontal scrollbars** on standard 1366x768 and 1920x1080 laptop displays.

#### 4. Live Terminal: Dedicated Scrolling & Smooth Resizable Splitter
- Keep standard vertical scrolling active inside `SideTerminalWidget` (`QPlainTextEdit`) for command history.
- Configure `_main_splitter`:
  - Set `min-width: 240px; max-width: 600px;` on the terminal.
  - Set `setChildrenCollapsible(False)` to prevent zero-width canvas collapse glitches.
  - Style the splitter handle with a clean 5px grip line (`hover: #0A84FF;`) for smooth manual dragging.
  - Keep the bottom bar `[Hide Terminal]` / `[Show Terminal]` button in sync.

#### 5. Overhaul Workflow & Function Guide: Interactive & Clickable Cards (`workflow_guide.py`)
- In `WorkflowGuideDialog` (`_build_functions_tab`):
- Transform every function item from a plain text description into an **Interactive, Expandable Action Card**:
  - **Header Row**:
    - Distinct circular vector icon chip + Tool Title.
    - Category Pill Badge (`DEVICE`, `ROOT`, `FLASHING`, `RESCUE`).
    - Dedicated **"Launch This Tool ➔"** button: clicking it emits an action signal (`action_requested.emit(action_id)`), closes the guide dialog, and immediately switches to that tool screen in `main_window.py`!
  - **Two-Column / Tabbed Detail Breakdown**:
    - ⚙️ **"How It Works (Under the Hood)"**: Explains the technical mechanism (fastboot commands, partition targets, GKI kernel patching, AVB 2.0 flags).
    - 📋 **"How to Use It (Step-by-Step Guide)"**: Clear, numbered instructions detailing required phone mode (ADB vs Bootloader), file prerequisites, safety rules, and expected output.
    - ⚠️ **"Safety Checklist / Pro-Tips"**: What to watch out for to prevent bricks (never lock bootloader with custom ROM, backup EFS/NVRAM first).
- Add support across all 15 workstation utilities (`Check my phone`, `Safety Checklist`, `Unlock Bootloader`, `Root my phone`, `Flash ROM / GSI`, `Manage Modules`, `Diagnostics & Tweaks`, `Fix Play Integrity`, `Backup / Restore`, `Fix bricked phone`, `Return to Stock`, `MTK / Unisoc mode`, `Sideload & Apps`, `Screen Mirror`, `Downloads & Drivers`, `Logs & Help`).

---

### Step 6: Verification, Version Bump & GitHub Pipeline
*(Strictly enforce Section 4 of `.agents/skills/flashdock-workstation/SKILL.md`)*
1. **Semantic Version Bump to `1.3.3`**:
   - `flashdock/__init__.py`: `__version__ = "1.3.3"`
   - `flashdock/constants.py`: `APP_VERSION = "1.3.3"`
   - `scripts/version_info.txt`: Update `FileVersion` and `ProductVersion` to `1.3.3.0`
   - `README.md`, `read.md`, and `handoff.md`: Update badges, frontmatter, and headings to `v1.3.3`.
2. **Automated Verification & Release Packaging**:
   - Run `python scripts/release_build.py`.
   - Ensure all 467+ unit/integration tests pass with 100% success rate.
   - Compile clean binary `dist/FlashDock_Dist/FlashDock.exe` and archive `dist/FlashDock-v1.3.3-windows-x64.zip`.
3. **GitHub Push**:
   - `git add .`
   - `git commit -m "feat(v1.3.3): fix virtual keypad ADB keyevent, non-scrolling home canvas, scrollable sidebar, and interactive workflow guide"`
   - `git push origin main`
```
