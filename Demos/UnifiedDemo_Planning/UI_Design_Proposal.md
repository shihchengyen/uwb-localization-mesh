# UI/UX Design Proposal: MiniPlayer & MainWindow

## Design Philosophy

**Core Principles:**

- **Clean & Modern**: Minimalist interface, focus on functionality
- **Professional**: Suitable for demo/presentation environments
- **Functional**: All controls easily accessible
- **Consistent**: Shared design language across all widgets
- **Dark Theme Ready**: Dark mode support for low-light environments

---

## 1. MiniPlayer Design

### 1.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  MiniPlayer Widget (Sidebar - ~300px wide, flexible height) │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Current Track Display                               │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │ 🎵 Song Title - Artist Name                 │   │   │
│  │  │    [3:45 / 5:23]                            │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Progress Bar                                         │   │
│  │  ████████████░░░░░░░░░░░░░░░  [Seekable]            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Playback Controls                                    │   │
│  │  [⏮ Previous]  [⏸ Play/Pause]  [⏭ Skip]           │   │
│  │         (or)                                         │   │
│  │  [◀◀]  [▶]  [⏸]  [▶▶]  [⏹]                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Volume Control                                       │   │
│  │  🔊 Volume: [████████░░] 70%                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Playlist Selector                                   │   │
│  │  📋 Playlist: [▼] Playlist 1                        │   │
│  │  [🔀 Shuffle] [🔁 Repeat]                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Queue Preview (3-5 tracks)                          │   │
│  │  ┌─────────────────────────────────────────────┐   │   │
│  │  │ ▶ Next: Track 2 - Artist B                   │   │   │
│  │  │ ✅ Then: Track 3 - Artist C                  │   │   │
│  │  │ ✅ Then: Track 4 - Artist D                  │   │   │
│  │  │ ✅ Then: Track 5 - Artist E                  │   │   │
│  │  └─────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Visual Style

**Color Scheme (Dark Theme):**

```
Background:     #2b2b2b (Dark gray)
Surface:        #363636 (Slightly lighter gray)
Primary:        #4a9eff (Bright blue - for active/selected)
Accent:         #ff6b6b (Red - for stop/important actions)
Text Primary:   #ffffff (White)
Text Secondary: #b0b0b0 (Light gray)
Text Muted:     #808080 (Gray)
Border:         #404040 (Medium gray)
```

**Color Scheme (Light Theme):**

```
Background:     #ffffff (White)
Surface:        #f5f5f5 (Light gray)
Primary:        #0066cc (Blue)
Accent:         #cc0000 (Red)
Text Primary:   #000000 (Black)
Text Secondary: #505050 (Dark gray)
Text Muted:     #909090 (Gray)
Border:         #d0d0d0 (Light gray)
```

### 1.3 Component Specifications

#### **Current Track Display**

- **Font**: Segoe UI or system font, 12pt bold for title, 10pt for artist
- **Height**: ~60px
- **Icon**: Optional music note icon (🎵)
- **Alignment**: Left-aligned with padding
- **Style**: Card-like background with subtle border

#### **Progress Bar**

- **Height**: 6px (drag handle: 12px hover, 16px active)
- **Style**: Rounded corners, smooth gradient fill
- **Colors**: Primary color (active), Surface (inactive)
- **Interactive**: Click to seek, drag to scrub
- **Time Display**: Current time / Total time on right side

#### **Playback Controls**

- **Button Style**: Icon buttons, 40x40px, rounded
- **Icons**: Unicode or icon font (⏮ ⏸ ⏭)
- **Spacing**: 8px between buttons
- **Hover Effect**: Scale 1.1x, slight glow
- **Active State**: Pressed-in appearance
- **Layout**: Horizontal row, centered

#### **Volume Control**

- **Slider**: Horizontal, width ~200px
- **Label**: "🔊 Volume: XX%"
- **Style**: Same as progress bar
- **Range**: 0-100, increments of 5

#### **Playlist Selector**

- **Dropdown**: Standard QComboBox style
- **Icons**: Shuffle (🔀) and Repeat (🔁) as toggle buttons
- **Layout**: Horizontal row, dropdown + 2 toggle buttons

#### **Queue Preview**

- **Style**: Scrollable list (QListWidget or QScrollArea)
- **Item Height**: 40px per track
- **Icon**: ▶ for next track, ✅ for upcoming tracks
- **Font**: 10pt, secondary text color
- **Max Height**: 200px (5 tracks visible)
- **Hover Effect**: Highlight background color

### 1.4 PyQt5 Implementation Stylesheet

```python
MINIPLAYER_STYLESHEET = """
QWidget {
    background-color: #2b2b2b;
    color: #ffffff;
    font-family: 'Segoe UI', Arial, sans-serif;
}

/* Current Track Display */
QLabel#trackTitle {
    font-size: 12pt;
    font-weight: bold;
    color: #ffffff;
    padding: 8px;
}

QLabel#trackArtist {
    font-size: 10pt;
    color: #b0b0b0;
    padding: 8px;
}

/* Progress Bar */
QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background: #363636;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #4a9eff;
    border: 2px solid #ffffff;
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}

QSlider::handle:horizontal:hover {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #6bb0ff;
}

/* Playback Buttons */
QPushButton#playButton,
QPushButton#pauseButton,
QPushButton#skipButton,
QPushButton#previousButton,
QPushButton#stopButton {
    background-color: #363636;
    border: none;
    border-radius: 20px;
    width: 40px;
    height: 40px;
    font-size: 16pt;
}

QPushButton#playButton:hover,
QPushButton#pauseButton:hover,
QPushButton#skipButton:hover,
QPushButton#previousButton:hover,
QPushButton#stopButton:hover {
    background-color: #404040;
    transform: scale(1.1);
}

QPushButton#playButton:pressed,
QPushButton#pauseButton:pressed,
QPushButton#skipButton:pressed,
QPushButton#previousButton:pressed,
QPushButton#stopButton:pressed {
    background-color: #4a9eff;
}

/* Volume Slider */
QSlider::groove:horizontal#volumeSlider {
    border: none;
    height: 4px;
    background: #363636;
    border-radius: 2px;
}

QSlider::handle:horizontal#volumeSlider {
    background: #4a9eff;
    border: 1px solid #ffffff;
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 5px;
}

/* Playlist Dropdown */
QComboBox {
    background-color: #363636;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px 8px;
    color: #ffffff;
}

QComboBox:hover {
    border-color: #4a9eff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

/* Toggle Buttons (Shuffle/Repeat) */
QPushButton#shuffleButton,
QPushButton#repeatButton {
    background-color: transparent;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px 8px;
}

QPushButton#shuffleButton:checked,
QPushButton#repeatButton:checked {
    background-color: #4a9eff;
    border-color: #4a9eff;
}

/* Queue List */
QListWidget {
    background-color: #2b2b2b;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 4px;
}

QListWidget::item {
    padding: 4px;
    border-radius: 2px;
    color: #b0b0b0;
}

QListWidget::item:hover {
    background-color: #363636;
    color: #ffffff;
}

QListWidget::item:selected {
    background-color: #4a9eff;
    color: #ffffff;
}
"""
```

---

## 2. MainWindow Design

### 2.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  MainWindow                                                          │
├─────────────────────────────────────────────────────────────────────┤
│  Menu Bar: File | Edit | View | Tools | Help                        │
├─────────────────────────────────────────────────────────────────────┤
│  Toolbar: [📁 Open] [📐 Mark Corners] [🎯 Place Zones] [▶ Start]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Tab Bar                                                     │   │
│  │  [PGO Data] [Adaptive Audio] [Zone DJ]                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │         Widget Content Area (Tab Content)                     │   │
│  │                                                               │   │
│  │         (Adaptive Audio Widget shown)                         │   │
│  │         ┌──────────────────┬──────────────────┐             │   │
│  │         │                  │                  │             │   │
│  │         │   FloorplanView  │   MiniPlayer     │             │   │
│  │         │   (3/4 width)    │   (1/4 width)    │             │   │
│  │         │                  │                  │             │   │
│  │         │                  │                  │             │   │
│  │         └──────────────────┴──────────────────┘             │   │
│  │                                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Status Bar: [🟢 Running] [Position: 2.4m, 3.1m] [FPS: 20] [Time] │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Window Properties

**Dimensions:**

- **Default Size**: 1400×900px (16:9 aspect ratio)
- **Min Size**: 1200×700px
- **Max Size**: None (allows fullscreen)
- **Title**: "UWB Localization Visualization - Unified Demo"

**Window Style:**

- Standard window controls (minimize, maximize, close)
- Dark theme by default (light theme optional)
- System-native window decorations
- Resizable, dockable widgets (future enhancement)

### 2.3 Menu Bar

```
File Menu:
  - New Session
  - Open Floorplan... (Ctrl+O)
  - Save Configuration... (Ctrl+S)
  - Export Data... (Ctrl+E)
  - Exit (Ctrl+Q)

Edit Menu:
  - Preferences... (Ctrl+,)
  - Settings...

View Menu:
  - Toolbar (toggle)
  - Status Bar (toggle)
  - Fullscreen (F11)

Tools Menu:
  - Start Simulation (F5)
  - Stop Simulation (F6)
  - Reset Position

Help Menu:
  - User Guide
  - About
```

### 2.4 Toolbar

**Standard Actions:**

- 📁 Open Floorplan Image
- 📐 Mark Corners (auto/manual)
- 🎯 Place Zones Mode (toggle)
- 🗑️ Clear Zones
- ❌ Clear Mapping
- ▶ Start Simulation
- ⏹ Stop Simulation
- ⚙️ Settings

**Style:**

- Icon buttons with tooltips
- 32x32px icons
- Horizontal layout
- Grouped: [File] [Mapping] [Zones] [Simulation] [Settings]
- Separators between groups

### 2.5 Tab Widget

**Style:**

- Dark theme tabs at top
- Active tab: Highlighted with primary color
- Inactive tabs: Secondary color
- Tab height: 40px
- Font: 11pt, medium weight

**Tab Indicators:**

- Optional: Status indicators (🟢 Active, 🟡 Paused, 🔴 Stopped)
- Badge for updates (future)

### 2.6 Status Bar

**Left Side:**

- Server status icon + text: `[🟢 Running]` / `[🔴 Stopped]` / `[🟡 Error]`
- Position display: `Position: 2.4m, 3.1m`
- FPS counter: `FPS: 20`
- Update rate: `Rate: 20Hz`

**Right Side:**

- Current time: `14:32:45`
- Simulation time: `Sim Time: 00:05:23`
- Memory usage: `Memory: 145MB` (optional)

**Style:**

- Height: 24px
- Text size: 9pt
- Background: Darker than main window
- Separator lines between sections

### 2.7 MainWindow Stylesheet

```python
MAINWINDOW_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
    color: #ffffff;
}

/* Menu Bar */
QMenuBar {
    background-color: #2b2b2b;
    color: #ffffff;
    border-bottom: 1px solid #404040;
    padding: 4px;
}

QMenuBar::item {
    padding: 4px 8px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #363636;
}

QMenu {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #404040;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #4a9eff;
}

/* Toolbar */
QToolBar {
    background-color: #2b2b2b;
    border: none;
    spacing: 4px;
    padding: 4px;
}

QToolBar::separator {
    background-color: #404040;
    width: 1px;
    margin: 4px 8px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    width: 32px;
    height: 32px;
}

QToolButton:hover {
    background-color: #363636;
    border-color: #404040;
}

QToolButton:pressed {
    background-color: #4a9eff;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #404040;
    background-color: #1e1e1e;
    top: -1px;
}

QTabBar::tab {
    background-color: #2b2b2b;
    color: #b0b0b0;
    border: 1px solid #404040;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #ffffff;
    border-color: #4a9eff;
    border-bottom: 1px solid #1e1e1e;
}

QTabBar::tab:hover {
    background-color: #363636;
    color: #ffffff;
}

/* Status Bar */
QStatusBar {
    background-color: #1e1e1e;
    border-top: 1px solid #404040;
    color: #b0b0b0;
    font-size: 9pt;
    padding: 4px;
}

QStatusBar::item {
    border: none;
}

QStatusBar QLabel {
    padding: 0 8px;
    border-right: 1px solid #404040;
}

QStatusBar QLabel:last-child {
    border-right: none;
}
"""
```

---

## 3. Responsive Design Considerations

### 3.1 Window Resizing

**MiniPlayer:**

- Fixed width: 300px (minimum)
- Flexible height: Expands with queue
- Scrollable queue if content exceeds available space
- Hide queue if window too small (optional)

**MainWidget:**

- FloorplanView scales with window size
- MiniPlayer maintains fixed width
- Horizontal layout → Vertical layout on small screens (future)

### 3.2 High DPI Support

- Use Qt's device pixel ratio scaling
- Test at 125%, 150%, 200% scaling
- Icons: SVG or high-resolution bitmaps
- Fonts: Scale-aware sizing

---

## 4. Icon Recommendations

### 4.1 Icon Library

**Options:**

1. **Material Icons** (Google) - Free, comprehensive
2. **Font Awesome** - Free, widely used
3. **Feather Icons** - Free, minimal
4. **Custom Unicode** - No dependencies

**Recommendation**: Material Icons or Font Awesome

- Easy to integrate
- Consistent style
- Large icon set

### 4.2 Icon Mappings

| Action        | Icon | Unicode Alternative |
| ------------- | ---- | ------------------- |
| Play          | ▶    | U+25B6              |
| Pause         | ⏸    | U+23F8              |
| Stop          | ⏹    | U+23F9              |
| Skip Next     | ⏭    | U+23ED              |
| Skip Previous | ⏮    | U+23EE              |
| Volume        | 🔊   | U+1F50A             |
| Playlist      | 📋   | U+1F4CB             |
| Shuffle       | 🔀   | U+1F500             |
| Repeat        | 🔁   | U+1F501             |

---

## 5. Animation & Transitions

### 5.1 Suggested Animations

**Playback State Changes:**

- Button transition: 150ms ease-in-out
- Progress bar updates: Smooth, no animation (direct update)

**Queue Updates:**

- Fade in new items: 200ms
- Slide transitions: Optional

**Zone Registration:**

- Fade highlight: 300ms
- Pulse animation: Optional (3 pulses, 500ms each)

**Window Transitions:**

- Tab switching: Instant (no animation)
- Status bar updates: Fade in: 200ms

### 5.2 Performance Considerations

- Use Qt's built-in animations (QPropertyAnimation)
- Disable animations on low-end hardware (optional setting)
- Hardware acceleration: Use QGraphicsView for complex animations

---

## 6. Accessibility Features

### 6.1 Keyboard Shortcuts

```
Playback:
  Space       - Play/Pause
  Ctrl+Right  - Skip next track
  Ctrl+Left   - Previous track
  Ctrl+Up     - Volume up
  Ctrl+Down   - Volume down
  Ctrl+Shift+S - Stop

Navigation:
  Ctrl+Tab    - Next tab
  Ctrl+Shift+Tab - Previous tab
  Ctrl+O      - Open floorplan
  F5          - Start simulation
  F6          - Stop simulation
```

### 6.2 Screen Reader Support

- All buttons have descriptive tooltips
- Status bar announcements for important events
- ARIA labels (if using web components)

---

## 7. Theme Switching

### 7.1 Implementation

```python
class ThemeManager:
    THEMES = {
        "dark": DARK_THEME_STYLESHEET,
        "light": LIGHT_THEME_STYLESHEET,
    }

    def apply_theme(self, theme_name: str):
        stylesheet = self.THEMES.get(theme_name, self.THEMES["dark"])
        app.setStyleSheet(stylesheet)
```

### 7.2 User Preference

- Store theme preference in QSettings
- Apply on startup
- Allow runtime switching via menu

---

## 8. Implementation Checklist

### Phase 1: Basic Styling

- [ ] Create base stylesheet for MainWindow
- [ ] Create base stylesheet for MiniPlayer
- [ ] Apply dark theme by default
- [ ] Test all components render correctly

### Phase 2: Enhanced UI

- [ ] Add icons to buttons
- [ ] Implement hover effects
- [ ] Add tooltips to all controls
- [ ] Polish spacing and alignment

### Phase 3: Animations

- [ ] Add button press animations
- [ ] Implement smooth progress bar updates
- [ ] Add queue update transitions

### Phase 4: Polish

- [ ] High DPI testing
- [ ] Accessibility improvements
- [ ] Theme switching
- [ ] Performance optimization

---

## 9. Visual Mockup Descriptions

### MiniPlayer Sidebar

**Compact Mode** (collapsed):

- Shows only: Current track, play/pause, progress bar
- Height: ~120px

**Expanded Mode** (default):

- All controls visible
- Height: ~400px (adjusts with queue)

**Queue Mode**:

- Queue preview expanded
- Max height: ~600px (scrollable)

### MainWindow Layouts

**Default Layout**:

- Toolbar: Top
- Tabs: Below toolbar
- Content: Main area
- Status bar: Bottom

**Fullscreen Mode**:

- Hide menu bar (press Alt to show)
- Hide toolbar (toggle via menu)
- Maximize content area
- Status bar: Always visible

---

## 10. Color Palette Reference

### Dark Theme Colors (Hex)

```
Primary Palette:
  Background:  #1e1e1e  (Window background)
  Surface:     #2b2b2b  (Card backgrounds)
  Surface Light: #363636  (Hover states)
  Border:      #404040  (Borders, dividers)

Accent Palette:
  Primary:     #4a9eff  (Blue - actions, active)
  Primary Hover: #6bb0ff  (Lighter blue)
  Accent:      #ff6b6b  (Red - stop, errors)
  Success:     #51cf66  (Green - running, success)
  Warning:     #ffd43b  (Yellow - paused, warnings)

Text Palette:
  Primary:     #ffffff  (Main text)
  Secondary:   #b0b0b0  (Secondary text)
  Muted:       #808080  (Placeholder, disabled)
```

### Light Theme Colors (Hex)

```
Primary Palette:
  Background:  #ffffff  (Window background)
  Surface:     #f5f5f5  (Card backgrounds)
  Surface Dark: #e0e0e0  (Hover states)
  Border:      #d0d0d0  (Borders, dividers)

Accent Palette:
  Primary:     #0066cc  (Blue - actions, active)
  Primary Hover: #0052a3  (Darker blue)
  Accent:      #cc0000  (Red - stop, errors)
  Success:     #28a745  (Green - running, success)
  Warning:     #ffc107  (Yellow - paused, warnings)

Text Palette:
  Primary:     #000000  (Main text)
  Secondary:   #505050  (Secondary text)
  Muted:       #909090  (Placeholder, disabled)
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-11  
**Status:** Proposal - Ready for Review
