# macOS Accessibility APIs Deep Dive

> Research conducted February 24, 2026 for the Nexus project.
> Covers public APIs, private APIs, system internals, and practical implications for GUI automation.

---

## Table of Contents

1. [AXUIElement API Completeness](#1-axuielement-api-completeness)
2. [AX Notifications](#2-ax-notifications)
3. [CGWindowList APIs](#3-cgwindowlist-apis)
4. [Private Accessibility APIs](#4-private-accessibility-apis)
5. [NSAccessibility Protocol](#5-nsaccessibility-protocol-cocoa-side)
6. [Accessibility Permission Deep Dive](#6-accessibility-permission-deep-dive)
7. [macOS Version Differences](#7-macos-version-differences)
8. [Process-Specific Accessibility](#8-process-specific-accessibility)
9. [XPC and macOS IPC](#9-xpc-and-macos-ipc)

---

## 1. AXUIElement API Completeness

The AXUIElement API is defined in HIServices.framework within ApplicationServices.framework. The key header files are:
- `AXAttributeConstants.h` — all attribute constants
- `AXActionConstants.h` — all action constants
- `AXRoleConstants.h` — all role and subrole constants
- `AXNotificationConstants.h` — all notification constants
- `AXUIElement.h` — core API functions

**References:**
- [AXAttributeConstants.h (Apple Developer)](https://developer.apple.com/documentation/applicationservices/axattributeconstants_h)
- [AXAttributeConstants.h (GitHub SDK mirror)](https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX10.7.sdk/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXAttributeConstants.h)
- [AXAttributeConstants.h (Gist)](https://gist.github.com/p6p/24fbac5d12891fcfffa2b53761f4343e)

### 1.1 Complete Attribute List

#### Informational Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXRoleAttribute` | `"AXRole"` | Type/role of the element (required on all elements) |
| `kAXSubroleAttribute` | `"AXSubrole"` | More specific role classification |
| `kAXRoleDescriptionAttribute` | `"AXRoleDescription"` | Human-readable, localized role description |
| `kAXTitleAttribute` | `"AXTitle"` | Localized display string shown as part of the element |
| `kAXDescriptionAttribute` | `"AXDescription"` | Localized description for assistive technologies |
| `kAXHelpAttribute` | `"AXHelp"` | Localized help text content |

#### Hierarchy / Relationship Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXParentAttribute` | `"AXParent"` | Parent element in the hierarchy |
| `kAXChildrenAttribute` | `"AXChildren"` | Child elements |
| `kAXSelectedChildrenAttribute` | `"AXSelectedChildren"` | Currently selected children |
| `kAXVisibleChildrenAttribute` | `"AXVisibleChildren"` | Currently visible children |
| `kAXWindowAttribute` | `"AXWindow"` | Containing window |
| `kAXTopLevelUIElementAttribute` | `"AXTopLevelUIElement"` | Top-level element (usually window) |
| `kAXTitleUIElementAttribute` | `"AXTitleUIElement"` | Element serving as the title |
| `kAXServesAsTitleForUIElementsAttribute` | `"AXServesAsTitleForUIElements"` | Elements this element titles |
| `kAXLinkedUIElementsAttribute` | `"AXLinkedUIElements"` | Related/linked elements |
| `kAXSharedFocusElementsAttribute` | `"AXSharedFocusElements"` | Elements sharing focus |

#### Visual State Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXEnabledAttribute` | `"AXEnabled"` | Whether the element is enabled |
| `kAXFocusedAttribute` | `"AXFocused"` | Whether the element has keyboard focus |
| `kAXPositionAttribute` | `"AXPosition"` | Screen position (AXValue CGPoint) |
| `kAXSizeAttribute` | `"AXSize"` | Size (AXValue CGSize) |
| `kAXOrientationAttribute` | `"AXOrientation"` | Horizontal/vertical orientation |

#### Value Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXValueAttribute` | `"AXValue"` | The element's value (type varies) |
| `kAXValueDescriptionAttribute` | `"AXValueDescription"` | Human-readable value description |
| `kAXMinValueAttribute` | `"AXMinValue"` | Minimum allowed value |
| `kAXMaxValueAttribute` | `"AXMaxValue"` | Maximum allowed value |
| `kAXValueIncrementAttribute` | `"AXValueIncrement"` | Step size for increment/decrement |
| `kAXValueWrapsAttribute` | `"AXValueWraps"` | Whether value wraps around |
| `kAXAllowedValuesAttribute` | `"AXAllowedValues"` | Array of allowed values |
| `kAXPlaceholderValueAttribute` | `"AXPlaceholderValue"` | Placeholder text |
| `kAXElementBusyAttribute` | `"AXElementBusy"` | Whether element is in a busy/loading state |

#### Text-Specific Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXSelectedTextAttribute` | `"AXSelectedText"` | Currently selected text string |
| `kAXSelectedTextRangeAttribute` | `"AXSelectedTextRange"` | Range of selected text |
| `kAXSelectedTextRangesAttribute` | `"AXSelectedTextRanges"` | Array of selected ranges (multi-selection) |
| `kAXVisibleCharacterRangeAttribute` | `"AXVisibleCharacterRange"` | Range of currently visible characters |
| `kAXNumberOfCharactersAttribute` | `"AXNumberOfCharacters"` | Total character count |
| `kAXSharedTextUIElementsAttribute` | `"AXSharedTextUIElements"` | Elements sharing this text storage |
| `kAXSharedCharacterRangeAttribute` | `"AXSharedCharacterRange"` | Character range within shared storage |
| `kAXInsertionPointLineNumberAttribute` | `"AXInsertionPointLineNumber"` | Line number of the insertion point |
| `kAXTextAttribute` | `"AXText"` | Full text content |
| `kAXVisibleTextAttribute` | `"AXVisibleText"` | Currently visible text |
| `kAXIsEditableAttribute` | `"AXIsEditable"` | Whether the text is editable |

#### Window / Sheet / Drawer Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXMainAttribute` | `"AXMain"` | Whether this is the main window |
| `kAXMinimizedAttribute` | `"AXMinimized"` | Whether window is minimized |
| `kAXCloseButtonAttribute` | `"AXCloseButton"` | Reference to the close button |
| `kAXZoomButtonAttribute` | `"AXZoomButton"` | Reference to the zoom button |
| `kAXMinimizeButtonAttribute` | `"AXMinimizeButton"` | Reference to the minimize button |
| `kAXToolbarButtonAttribute` | `"AXToolbarButton"` | Reference to the toolbar button |
| `kAXFullScreenButtonAttribute` | `"AXFullScreenButton"` | Reference to the fullscreen button |
| `kAXProxyAttribute` | `"AXProxy"` | Document proxy icon |
| `kAXGrowAreaAttribute` | `"AXGrowArea"` | Window resize corner |
| `kAXModalAttribute` | `"AXModal"` | Whether window is modal |
| `kAXDefaultButtonAttribute` | `"AXDefaultButton"` | The default button |
| `kAXCancelButtonAttribute` | `"AXCancelButton"` | The cancel button |

#### Application-Level Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXMenuBarAttribute` | `"AXMenuBar"` | Application's main menu bar |
| `kAXExtrasMenuBarAttribute` | `"AXExtrasMenuBar"` | Extras/status menu bar (added later) |
| `kAXWindowsAttribute` | `"AXWindows"` | All application windows |
| `kAXFrontmostAttribute` | `"AXFrontmost"` | Whether app is frontmost |
| `kAXHiddenAttribute` | `"AXHidden"` | Whether app is hidden |
| `kAXMainWindowAttribute` | `"AXMainWindow"` | The main window |
| `kAXFocusedWindowAttribute` | `"AXFocusedWindow"` | The focused window |
| `kAXFocusedUIElementAttribute` | `"AXFocusedUIElement"` | The focused element |
| `kAXFocusedApplicationAttribute` | `"AXFocusedApplication"` | The frontmost application (system-wide) |
| `kAXIsApplicationRunningAttribute` | `"AXIsApplicationRunning"` | Whether app process is running |

#### Menu Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXMenuItemCmdCharAttribute` | `"AXMenuItemCmdChar"` | Keyboard shortcut character |
| `kAXMenuItemCmdVirtualKeyAttribute` | `"AXMenuItemCmdVirtualKey"` | Virtual key code for shortcut |
| `kAXMenuItemCmdGlyphAttribute` | `"AXMenuItemCmdGlyph"` | Glyph index for shortcut |
| `kAXMenuItemCmdModifiersAttribute` | `"AXMenuItemCmdModifiers"` | Modifier keys (shift, cmd, etc.) |
| `kAXMenuItemMarkCharAttribute` | `"AXMenuItemMarkChar"` | Check mark character |
| `kAXMenuItemPrimaryUIElementAttribute` | `"AXMenuItemPrimaryUIElement"` | Primary UI element for the menu item |

#### Table / Outline / Browser Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXRowsAttribute` | `"AXRows"` | All rows |
| `kAXVisibleRowsAttribute` | `"AXVisibleRows"` | Currently visible rows |
| `kAXSelectedRowsAttribute` | `"AXSelectedRows"` | Selected rows |
| `kAXColumnsAttribute` | `"AXColumns"` | All columns |
| `kAXVisibleColumnsAttribute` | `"AXVisibleColumns"` | Visible columns |
| `kAXSelectedColumnsAttribute` | `"AXSelectedColumns"` | Selected columns |
| `kAXSortDirectionAttribute` | `"AXSortDirection"` | Sort direction |
| `kAXColumnHeaderUIElementsAttribute` | `"AXColumnHeaderUIElements"` | Column header elements |
| `kAXIndexAttribute` | `"AXIndex"` | Index of the element |
| `kAXDisclosingAttribute` | `"AXDisclosing"` | Whether outline row is expanded |
| `kAXDisclosedRowsAttribute` | `"AXDisclosedRows"` | Child rows of disclosure |
| `kAXDisclosedByRowAttribute` | `"AXDisclosedByRow"` | Parent row of disclosure |
| `kAXDisclosureLevelAttribute` | `"AXDisclosureLevel"` | Nesting level |
| `kAXRowCountAttribute` | `"AXRowCount"` | Total row count |
| `kAXColumnCountAttribute` | `"AXColumnCount"` | Total column count |
| `kAXOrderedByRowAttribute` | `"AXOrderedByRow"` | Whether ordered by row |
| `kAXColumnTitleAttribute` / `kAXColumnTitlesAttribute` | `"AXColumnTitles"` | Column title(s) |

#### Cell-Based Table Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXSelectedCellsAttribute` | `"AXSelectedCells"` | Selected cells |
| `kAXVisibleCellsAttribute` | `"AXVisibleCells"` | Visible cells |
| `kAXRowHeaderUIElementsAttribute` | `"AXRowHeaderUIElements"` | Row header elements |
| `kAXRowIndexRangeAttribute` | `"AXRowIndexRange"` | Row index range of a cell |
| `kAXColumnIndexRangeAttribute` | `"AXColumnIndexRange"` | Column index range of a cell |

#### Miscellaneous UI Attributes
| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXHeaderAttribute` | `"AXHeader"` | Header element |
| `kAXEditedAttribute` | `"AXEdited"` | Whether content has been edited |
| `kAXTabsAttribute` | `"AXTabs"` | Tab elements in a tab group |
| `kAXHorizontalScrollBarAttribute` | `"AXHorizontalScrollBar"` | Horizontal scroll bar |
| `kAXVerticalScrollBarAttribute` | `"AXVerticalScrollBar"` | Vertical scroll bar |
| `kAXOverflowButtonAttribute` | `"AXOverflowButton"` | Overflow/more button |
| `kAXFilenameAttribute` | `"AXFilename"` | Associated filename |
| `kAXExpandedAttribute` | `"AXExpanded"` | Whether element is expanded |
| `kAXSelectedAttribute` | `"AXSelected"` | Whether element is selected |
| `kAXSplittersAttribute` | `"AXSplitters"` | Splitter elements |
| `kAXContentsAttribute` | `"AXContents"` | Content elements |
| `kAXNextContentsAttribute` | `"AXNextContents"` | Next content section |
| `kAXPreviousContentsAttribute` | `"AXPreviousContents"` | Previous content section |
| `kAXDocumentAttribute` | `"AXDocument"` | Document URL |
| `kAXURLAttribute` | `"AXURL"` | URL associated with element |
| `kAXLabelUIElementsAttribute` | `"AXLabelUIElements"` | Label elements |
| `kAXLabelValueAttribute` | `"AXLabelValue"` | Label value |
| `kAXShownMenuUIElementAttribute` | `"AXShownMenuUIElement"` | Currently shown menu |
| `kAXSearchButtonAttribute` | `"AXSearchButton"` | Search button in search field |
| `kAXClearButtonAttribute` | `"AXClearButton"` | Clear button in search field |
| `kAXIdentifierAttribute` | `"AXIdentifier"` | Developer-assigned identifier |
| `kAXAlternateUIVisibleAttribute` | `"AXAlternateUIVisible"` | Whether alternate UI is shown |
| `kAXWarningValueAttribute` | `"AXWarningValue"` | Warning threshold |
| `kAXCriticalValueAttribute` | `"AXCriticalValue"` | Critical threshold |
| `kAXHandlesAttribute` | `"AXHandles"` | Drag handles |

#### Date/Time Field Attributes
| Constant | String Value |
|----------|-------------|
| `kAXHourFieldAttribute` | `"AXHourField"` |
| `kAXMinuteFieldAttribute` | `"AXMinuteField"` |
| `kAXSecondFieldAttribute` | `"AXSecondField"` |
| `kAXAMPMFieldAttribute` | `"AXAMPMField"` |
| `kAXDayFieldAttribute` | `"AXDayField"` |
| `kAXMonthFieldAttribute` | `"AXMonthField"` |
| `kAXYearFieldAttribute` | `"AXYearField"` |

#### Ruler Attributes
| Constant | String Value |
|----------|-------------|
| `kAXMarkerUIElementsAttribute` | `"AXMarkerUIElements"` |
| `kAXUnitsAttribute` | `"AXUnits"` |
| `kAXUnitDescriptionAttribute` | `"AXUnitDescription"` |
| `kAXMarkerTypeAttribute` | `"AXMarkerType"` |
| `kAXMarkerTypeDescriptionAttribute` | `"AXMarkerTypeDescription"` |
| `kAXHorizontalUnitsAttribute` | `"AXHorizontalUnits"` |
| `kAXVerticalUnitsAttribute` | `"AXVerticalUnits"` |
| `kAXHorizontalUnitDescriptionAttribute` | `"AXHorizontalUnitDescription"` |
| `kAXVerticalUnitDescriptionAttribute` | `"AXVerticalUnitDescription"` |

#### Matte Attributes
| Constant | String Value |
|----------|-------------|
| `kAXMatteHoleAttribute` | `"AXMatteHole"` |
| `kAXMatteContentUIElementAttribute` | `"AXMatteContentUIElement"` |

#### Layout Attributes
| Constant | String Value |
|----------|-------------|
| `kAXIncrementorAttribute` | `"AXIncrementor"` |
| `kAXIncrementButtonAttribute` | `"AXIncrementButton"` |
| `kAXDecrementButtonAttribute` | `"AXDecrementButton"` |

### 1.2 Attribute Reliability Across Apps

**Most reliable (present on virtually all elements):**
- `AXRole` — always present, the only required attribute
- `AXPosition`, `AXSize` — present on all visible elements
- `AXEnabled` — present on interactive elements
- `AXChildren`, `AXParent` — present on all elements in the hierarchy

**Highly reliable (standard Cocoa apps):**
- `AXTitle` — present on buttons, windows, menu items, etc.
- `AXValue` — present on text fields, sliders, checkboxes, etc.
- `AXFocused` — present on focusable elements
- `AXDescription` — present when VoiceOver labels are set

**Moderately reliable:**
- `AXIdentifier` — only if the developer set it (common in Apple apps, rare in third-party)
- `AXHelp` — tooltip text, only if set by the developer
- `AXSubrole` — present on windows, buttons with special meaning, dock items

**Unreliable across apps:**
- `AXPlaceholderValue` — only in some text fields
- `AXDocument`, `AXURL` — only in document-based apps
- `AXIsEditable` — not consistently reported

### 1.3 Parameterized Attributes

Parameterized attributes require an input parameter (typically a range or index) and return computed results. Query supported ones via `AXUIElementCopyParameterizedAttributeNames()`.

**Reference:** [Text-Specific Parameterized Attributes (Apple)](https://developer.apple.com/documentation/appkit/accessibility/nsaccessibility/text-specific_parameterized_attributes)

#### Text Parameterized Attributes
| Constant | Input | Output | Description |
|----------|-------|--------|-------------|
| `kAXLineForIndexParameterizedAttribute` | CFNumber (char index) | CFNumber (line number) | Line number containing the character |
| `kAXRangeForLineParameterizedAttribute` | CFNumber (line number) | AXValue (CFRange) | Character range for a line |
| `kAXStringForRangeParameterizedAttribute` | AXValue (CFRange) | CFString | Substring for a range |
| `kAXRangeForPositionParameterizedAttribute` | AXValue (CGPoint) | AXValue (CFRange) | Character range at a screen position |
| `kAXRangeForIndexParameterizedAttribute` | CFNumber (char index) | AXValue (CFRange) | Range of the "word" at an index |
| `kAXBoundsForRangeParameterizedAttribute` | AXValue (CFRange) | AXValue (CGRect) | Screen bounds for a text range |
| `kAXRTFForRangeParameterizedAttribute` | AXValue (CFRange) | CFData (RTF) | RTF data for a text range |
| `kAXAttributedStringForRangeParameterizedAttribute` | AXValue (CFRange) | CFAttributedString | Attributed string for a range |
| `kAXStyleRangeForIndexParameterizedAttribute` | CFNumber (char index) | AXValue (CFRange) | Range of uniform style at index |

#### Table Parameterized Attributes
| Constant | Input | Output | Description |
|----------|-------|--------|-------------|
| `kAXCellForColumnAndRowParameterizedAttribute` | CFArray (2 CFNumbers) | AXUIElementRef | Cell at column, row |

#### Layout Parameterized Attributes
| Constant | Input | Output | Description |
|----------|-------|--------|-------------|
| `kAXLayoutPointForScreenPointParameterizedAttribute` | AXValue (CGPoint) | AXValue (CGPoint) | Convert screen to layout coords |
| `kAXLayoutSizeForScreenSizeParameterizedAttribute` | AXValue (CGSize) | AXValue (CGSize) | Convert screen to layout size |
| `kAXScreenPointForLayoutPointParameterizedAttribute` | AXValue (CGPoint) | AXValue (CGPoint) | Convert layout to screen coords |
| `kAXScreenSizeForLayoutSizeParameterizedAttribute` | AXValue (CGSize) | AXValue (CGSize) | Convert layout to screen size |

#### Private Parameterized Attributes (AXTextMarker)
| Attribute | Description |
|-----------|-------------|
| `AXTextMarkerForPosition` | Get a text marker for a screen position |
| `AXTextMarkerRangeForUIElement` | Get the full text marker range for an element |
| `AXStringForTextMarkerRange` | Get string content for a text marker range |
| `AXBoundsForTextMarkerRange` | Get screen bounds for a text marker range |
| `AXTextMarkerForIndex` | Get text marker for a character index |
| `AXIndexForTextMarker` | Get character index for a text marker |

AXTextMarker/AXTextMarkerRange are **private, undocumented types** used heavily by WebKit-based apps (Safari, Apple apps using WKWebView). They represent opaque serialized text positions. Hammerspoon has reverse-engineered support via `hs.axuielement.axtextmarker`.

**Reference:** [Hammerspoon AXTextMarker docs](https://www.hammerspoon.org/docs/hs.axuielement.axtextmarker.html)

### 1.4 Settable Attributes

Check settability at runtime with `AXUIElementIsAttributeSettable()`. Common settable attributes:

**Reference:** [AXUIElementIsAttributeSettable (Apple)](https://developer.apple.com/documentation/applicationservices/1459972-axuielementisattributesettable)

| Attribute | When Settable | Notes |
|-----------|--------------|-------|
| `AXFocused` | Any focusable element | Set to `true` to focus an element |
| `AXValue` | Text fields, sliders, checkboxes | Set text content, slider position, toggle state |
| `AXSelectedText` | Text areas/fields | Replace selected text |
| `AXSelectedTextRange` | Text areas/fields | Move selection/cursor |
| `AXVisibleCharacterRange` | Text areas/fields | Scroll to show a range |
| `AXMinimized` | Windows | Minimize/restore windows |
| `AXPosition` | Windows | Move a window |
| `AXSize` | Windows | Resize a window |
| `AXMain` | Windows | Make a window the main window |
| `AXFrontmost` | Applications | Activate an application |
| `AXHidden` | Applications | Hide/show an application |
| `AXExpanded` | Disclosure triangles, combo boxes | Expand/collapse |
| `AXSelected` | Tab items, list items | Select an item |
| `AXSelectedChildren` | Lists, tables | Set selection |
| `AXSelectedRows` | Tables, outlines | Set row selection |
| `AXDisclosing` | Outline rows | Expand/collapse outline rows |

**Known issues:**
- Microsoft Word on macOS does not properly support `AXUIElementSetAttributeValue` for some attributes ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/1324855/macos-axuielementsetattribute-not-working-on-word))
- Electron apps may not support `AXSelectedTextRange` correctly when lines start with blank characters ([Electron issue #36337](https://github.com/electron/electron/issues/36337))

### 1.5 Actions

Actions are the things you can "do" to an element. Query supported actions with `AXUIElementCopyActionNames()`.

**Reference:** [AXActionConstants.h (GitHub)](https://github.com/timnlupo/Crowd-Participation/blob/master/Crowd%20Participation/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXActionConstants.h)

| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXPressAction` | `"AXPress"` | Click/activate the element (buttons, checkboxes, menu items) |
| `kAXIncrementAction` | `"AXIncrement"` | Increment value (sliders, steppers) |
| `kAXDecrementAction` | `"AXDecrement"` | Decrement value |
| `kAXConfirmAction` | `"AXConfirm"` | Simulate pressing Return (text fields) |
| `kAXCancelAction` | `"AXCancel"` | Simulate pressing Escape |
| `kAXShowMenuAction` | `"AXShowMenu"` | Show context/popup menu |
| `kAXShowAlternateUIAction` | `"AXShowAlternateUI"` | Show alternate UI (e.g., hidden toolbar button) |
| `kAXShowDefaultUIAction` | `"AXShowDefaultUI"` | Restore default UI |
| `kAXRaiseAction` | `"AXRaise"` | Bring window/element to front |
| `kAXPickAction` | `"AXPick"` | Select/pick element (obsolete, use AXPress) |

**Undocumented but widely supported actions:**
- `"AXScrollToVisible"` — scroll the element into view (WebKit adds this to all elements)
- `"AXZoomWindow"` — zoom window to fill screen

**Action reliability:**
- `AXPress` — the most universally supported action, works on buttons, checkboxes, menu items, links
- `AXShowMenu` — can lock up Hammerspoon/apps for ~5 seconds if the element doesn't support it ([Hammerspoon issue](https://github.com/asmagill/hs._asm.axuielement/issues/13))
- `AXRaise` — reliable on windows, less so on arbitrary elements
- `AXIncrement`/`AXDecrement` — only on sliders, steppers, and similar value-based elements

### 1.6 Complete Role List

**Reference:** [AXRoleConstants.h (GitHub SDK)](https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX10.7.sdk/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXRoleConstants.h)

#### Standard Roles
| Constant | String Value |
|----------|-------------|
| `kAXApplicationRole` | `"AXApplication"` |
| `kAXSystemWideRole` | `"AXSystemWide"` |
| `kAXWindowRole` | `"AXWindow"` |
| `kAXSheetRole` | `"AXSheet"` |
| `kAXDrawerRole` | `"AXDrawer"` |
| `kAXGrowAreaRole` | `"AXGrowArea"` |
| `kAXImageRole` | `"AXImage"` |
| `kAXUnknownRole` | `"AXUnknown"` |
| `kAXButtonRole` | `"AXButton"` |
| `kAXRadioButtonRole` | `"AXRadioButton"` |
| `kAXCheckBoxRole` | `"AXCheckBox"` |
| `kAXPopUpButtonRole` | `"AXPopUpButton"` |
| `kAXMenuButtonRole` | `"AXMenuButton"` |
| `kAXTabGroupRole` | `"AXTabGroup"` |
| `kAXTableRole` | `"AXTable"` |
| `kAXColumnRole` | `"AXColumn"` |
| `kAXRowRole` | `"AXRow"` |
| `kAXOutlineRole` | `"AXOutline"` |
| `kAXBrowserRole` | `"AXBrowser"` |
| `kAXScrollAreaRole` | `"AXScrollArea"` |
| `kAXScrollBarRole` | `"AXScrollBar"` |
| `kAXRadioGroupRole` | `"AXRadioGroup"` |
| `kAXListRole` | `"AXList"` |
| `kAXGroupRole` | `"AXGroup"` |
| `kAXValueIndicatorRole` | `"AXValueIndicator"` |
| `kAXComboBoxRole` | `"AXComboBox"` |
| `kAXSliderRole` | `"AXSlider"` |
| `kAXIncrementorRole` | `"AXIncrementor"` |
| `kAXBusyIndicatorRole` | `"AXBusyIndicator"` |
| `kAXProgressIndicatorRole` | `"AXProgressIndicator"` |
| `kAXRelevanceIndicatorRole` | `"AXRelevanceIndicator"` |
| `kAXToolbarRole` | `"AXToolbar"` |
| `kAXDisclosureTriangleRole` | `"AXDisclosureTriangle"` |
| `kAXTextFieldRole` | `"AXTextField"` |
| `kAXTextAreaRole` | `"AXTextArea"` |
| `kAXStaticTextRole` | `"AXStaticText"` |
| `kAXMenuBarRole` | `"AXMenuBar"` |
| `kAXMenuBarItemRole` | `"AXMenuBarItem"` |
| `kAXMenuRole` | `"AXMenu"` |
| `kAXMenuItemRole` | `"AXMenuItem"` |
| `kAXSplitGroupRole` | `"AXSplitGroup"` |
| `kAXSplitterRole` | `"AXSplitter"` |
| `kAXColorWellRole` | `"AXColorWell"` |
| `kAXTimeFieldRole` | `"AXTimeField"` |
| `kAXDateFieldRole` | `"AXDateField"` |
| `kAXHelpTagRole` | `"AXHelpTag"` |
| `kAXMatteRole` | `"AXMatteRole"` |
| `kAXDockItemRole` | `"AXDockItem"` |
| `kAXRulerRole` | `"AXRuler"` |
| `kAXRulerMarkerRole` | `"AXRulerMarker"` |
| `kAXGridRole` | `"AXGrid"` |
| `kAXLevelIndicatorRole` | `"AXLevelIndicator"` |
| `kAXCellRole` | `"AXCell"` |
| `kAXLayoutAreaRole` | `"AXLayoutArea"` |
| `kAXLayoutItemRole` | `"AXLayoutItem"` |
| `kAXHandleRole` | `"AXHandle"` |
| `kAXPopoverRole` | `"AXPopover"` |

#### Standard Subroles
| Constant | String Value | Applied To |
|----------|-------------|-----------|
| `kAXCloseButtonSubrole` | `"AXCloseButton"` | Window close button |
| `kAXMinimizeButtonSubrole` | `"AXMinimizeButton"` | Window minimize button |
| `kAXZoomButtonSubrole` | `"AXZoomButton"` | Window zoom button |
| `kAXToolbarButtonSubrole` | `"AXToolbarButton"` | Window toolbar button |
| `kAXFullScreenButtonSubrole` | `"AXFullScreenButton"` | Window fullscreen button |
| `kAXSecureTextFieldSubrole` | `"AXSecureTextField"` | Password fields |
| `kAXTableRowSubrole` | `"AXTableRow"` | Table rows |
| `kAXOutlineRowSubrole` | `"AXOutlineRow"` | Outline/tree rows |
| `kAXUnknownSubrole` | `"AXUnknown"` | Unknown subrole |
| `kAXStandardWindowSubrole` | `"AXStandardWindow"` | Normal windows |
| `kAXDialogSubrole` | `"AXDialog"` | Dialog windows |
| `kAXSystemDialogSubrole` | `"AXSystemDialog"` | System-level dialogs (floats above all) |
| `kAXFloatingWindowSubrole` | `"AXFloatingWindow"` | Floating windows |
| `kAXSystemFloatingWindowSubrole` | `"AXSystemFloatingWindow"` | System floating windows |
| `kAXIncrementArrowSubrole` | `"AXIncrementArrow"` | Up arrow on stepper |
| `kAXDecrementArrowSubrole` | `"AXDecrementArrow"` | Down arrow on stepper |
| `kAXIncrementPageSubrole` | `"AXIncrementPage"` | Scroll page up area |
| `kAXDecrementPageSubrole` | `"AXDecrementPage"` | Scroll page down area |
| `kAXSortButtonSubrole` | `"AXSortButton"` | Column sort button |
| `kAXSearchFieldSubrole` | `"AXSearchField"` | Search fields |
| `kAXTimelineSubrole` | `"AXTimeline"` | Timeline UI |
| `kAXRatingIndicatorSubrole` | `"AXRatingIndicator"` | Star rating |
| `kAXContentListSubrole` | `"AXContentList"` | Content lists |
| `kAXDefinitionListSubrole` | `"AXDefinitionList"` | Definition lists |

#### Dock Subroles
| Constant | String Value |
|----------|-------------|
| `kAXApplicationDockItemSubrole` | `"AXApplicationDockItem"` |
| `kAXDocumentDockItemSubrole` | `"AXDocumentDockItem"` |
| `kAXFolderDockItemSubrole` | `"AXFolderDockItem"` |
| `kAXMinimizedWindowDockItemSubrole` | `"AXMinimizedWindowDockItem"` |
| `kAXURLDockItemSubrole` | `"AXURLDockItem"` |
| `kAXDockExtraDockItemSubrole` | `"AXDockExtraDockItem"` |
| `kAXTrashDockItemSubrole` | `"AXTrashDockItem"` |
| `kAXSeparatorDockItemSubrole` | `"AXSeparatorDockItem"` |
| `kAXProcessSwitcherListSubrole` | `"AXProcessSwitcherList"` |

### 1.7 Core AXUIElement Functions

| Function | Description |
|----------|-------------|
| `AXUIElementCreateApplication(pid)` | Create element for an application |
| `AXUIElementCreateSystemWide()` | Create system-wide element |
| `AXUIElementCopyAttributeNames(el, &names)` | Get all attribute names |
| `AXUIElementCopyAttributeValue(el, attr, &val)` | Get attribute value |
| `AXUIElementCopyAttributeValues(el, attr, idx, count, &vals)` | Get array slice |
| `AXUIElementGetAttributeValueCount(el, attr, &count)` | Get array attribute length |
| `AXUIElementIsAttributeSettable(el, attr, &settable)` | Check if settable |
| `AXUIElementSetAttributeValue(el, attr, val)` | Set attribute value |
| `AXUIElementCopyParameterizedAttributeNames(el, &names)` | Get parameterized attr names |
| `AXUIElementCopyParameterizedAttributeValue(el, attr, param, &val)` | Get parameterized value |
| `AXUIElementCopyActionNames(el, &names)` | Get action names |
| `AXUIElementCopyActionDescription(el, action, &desc)` | Get action description |
| `AXUIElementPerformAction(el, action)` | Perform an action |
| `AXUIElementGetPid(el, &pid)` | Get process ID |
| `AXUIElementCopyElementAtPosition(app, x, y, &el)` | Hit test at screen coords |

**Reference:** [AXUIElement.h (Apple Developer)](https://developer.apple.com/documentation/applicationservices/axuielement_h)

---

## 2. AX Notifications

### 2.1 Complete Notification List

**Reference:** [AXNotificationConstants.h (GNUstep mirror)](https://github.com/gnustep/libs-boron/blob/master/Headers/HIServices/AXNotificationConstants.h)

| Constant | String Value | Description |
|----------|-------------|-------------|
| `kAXMainWindowChangedNotification` | `"AXMainWindowChanged"` | Main window changed |
| `kAXFocusedWindowChangedNotification` | `"AXFocusedWindowChanged"` | Focused window changed |
| `kAXFocusedUIElementChangedNotification` | `"AXFocusedUIElementChanged"` | Focused element changed |
| `kAXApplicationActivatedNotification` | `"AXApplicationActivated"` | App became frontmost |
| `kAXApplicationDeactivatedNotification` | `"AXApplicationDeactivated"` | App lost frontmost |
| `kAXApplicationHiddenNotification` | `"AXApplicationHidden"` | App was hidden |
| `kAXApplicationShownNotification` | `"AXApplicationShown"` | App was shown |
| `kAXWindowCreatedNotification` | `"AXWindowCreated"` | New window created |
| `kAXWindowMovedNotification` | `"AXWindowMoved"` | Window was moved |
| `kAXWindowResizedNotification` | `"AXWindowResized"` | Window was resized |
| `kAXWindowMiniaturizedNotification` | `"AXWindowMiniaturized"` | Window minimized |
| `kAXWindowDeminiaturizedNotification` | `"AXWindowDeminiaturized"` | Window restored from minimize |
| `kAXDrawerCreatedNotification` | `"AXDrawerCreated"` | Drawer opened (legacy) |
| `kAXSheetCreatedNotification` | `"AXSheetCreated"` | Sheet appeared |
| `kAXHelpTagCreatedNotification` | `"AXHelpTagCreated"` | Tooltip appeared |
| `kAXValueChangedNotification` | `"AXValueChanged"` | Element value changed |
| `kAXUIElementDestroyedNotification` | `"AXUIElementDestroyed"` | Element was destroyed |
| `kAXElementBusyChangedNotification` | `"AXElementBusyChanged"` | Busy state changed |
| `kAXMenuOpenedNotification` | `"AXMenuOpened"` | Menu was opened |
| `kAXMenuClosedNotification` | `"AXMenuClosed"` | Menu was closed |
| `kAXMenuItemSelectedNotification` | `"AXMenuItemSelected"` | Menu item was selected |
| `kAXRowCountChangedNotification` | `"AXRowCountChanged"` | Table row count changed |
| `kAXRowExpandedNotification` | `"AXRowExpanded"` | Outline row expanded |
| `kAXRowCollapsedNotification` | `"AXRowCollapsed"` | Outline row collapsed |
| `kAXSelectedCellsChangedNotification` | `"AXSelectedCellsChanged"` | Cell selection changed |
| `kAXUnitsChangedNotification` | `"AXUnitsChanged"` | Measurement units changed |
| `kAXSelectedChildrenMovedNotification` | `"AXSelectedChildrenMoved"` | Selected children repositioned |
| `kAXSelectedChildrenChangedNotification` | `"AXSelectedChildrenChanged"` | Selection changed |
| `kAXResizedNotification` | `"AXResized"` | Generic resize |
| `kAXMovedNotification` | `"AXMoved"` | Generic move |
| `kAXCreatedNotification` | `"AXCreated"` | Generic creation |
| `kAXSelectedRowsChangedNotification` | `"AXSelectedRowsChanged"` | Row selection changed |
| `kAXSelectedColumnsChangedNotification` | `"AXSelectedColumnsChanged"` | Column selection changed |
| `kAXSelectedTextChangedNotification` | `"AXSelectedTextChanged"` | Text selection changed |
| `kAXTitleChangedNotification` | `"AXTitleChanged"` | Title changed |
| `kAXLayoutChangedNotification` | `"AXLayoutChanged"` | Layout changed (major restructure) |
| `kAXAnnouncementRequestedNotification` | `"AXAnnouncementRequested"` | VoiceOver announcement |

### 2.2 AXObserver Best Practices

**Reference:** [AXObserver (Apple Developer)](https://developer.apple.com/documentation/applicationservices/axobserver)

**Creation and setup:**
```
AXObserverCreate(pid, callback, &observer)     // Create observer for a PID
AXObserverAddNotification(observer, el, notif, refcon)   // Register for notification
AXObserverRemoveNotification(observer, el, notif)        // Unregister
AXObserverGetRunLoopSource(observer)            // Get CFRunLoopSource
CFRunLoopAddSource(runLoop, source, mode)       // Add to run loop
```

**Thread safety rules:**
1. `AXObserverCreate` must be called with a valid PID — observer is tied to one process
2. The callback fires on the thread whose run loop the observer source is attached to
3. `CFRunLoopRun()` blocks the calling thread indefinitely — always run on a background thread
4. Use `CFRunLoopRunInMode(kCFRunLoopDefaultMode, timeout, false)` in a loop instead of `CFRunLoopRun()` to allow periodic cleanup
5. CFRunLoop is generally thread-safe for adding/removing sources, but modifying run loop configuration from another thread can cause races
6. Avoid calling `CFSocketInvalidate` and `CFRunLoopStop` from different threads simultaneously — known crash source

**Known pitfalls:**
- `CFRunLoopRun()` exits immediately if there are no sources — must add observer source first
- VS Code fires `AXTitleChanged` approximately 8 times/second — needs 2-second debounce
- System-wide element does NOT support notifications — you cannot observe all apps with a single observer
- Must create separate `AXObserver` per process you want to monitor
- Callbacks on pyobjc must use `@objc.callbackFor(AXObserverCreate)` decorator — plain Python functions cause TypeError
- Observer stops working if the target process dies — no automatic notification of this
- Stale element references in callbacks can cause crashes

### 2.3 System-Wide Event Monitoring

**The system-wide AXUIElement does NOT support AXObserver notifications.** You cannot observe all apps from a single global observer.

**Workaround pattern for monitoring all apps:**
1. Use `NSWorkspace.sharedWorkspace().notificationCenter()` to monitor app launches/quits
2. Create a per-app `AXObserver` for each running application
3. Track active observers and clean up when apps quit
4. Use `NSWorkspace` notifications: `NSWorkspaceDidActivateApplicationNotification`, `NSWorkspaceDidDeactivateApplicationNotification`, `NSWorkspaceDidLaunchApplicationNotification`, `NSWorkspaceDidTerminateApplicationNotification`

**Reference:** [AXSwift Observer.swift](https://github.com/tmandry/AXSwift/blob/main/Sources/Observer.swift), [SwitchKey Accessibility Observer Pattern](https://deepwiki.com/itsuhane/SwitchKey/7.3-accessibility-observer-pattern)

---

## 3. CGWindowList APIs

### 3.1 Window Info Dictionary Keys

**Reference:** [CGWindow.h (GitHub SDK)](https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX10.8.sdk/System/Library/Frameworks/CoreGraphics.framework/Versions/A/Headers/CGWindow.h)

#### Required Keys (always present)
| Key | Type | Description |
|-----|------|-------------|
| `kCGWindowNumber` | CFNumber (int32) | Unique window ID within the user session |
| `kCGWindowStoreType` | CFNumber (int32) | Backing store type |
| `kCGWindowLayer` | CFNumber (int32) | Window layer number |
| `kCGWindowBounds` | CFDictionary | Bounds as `{X, Y, Width, Height}` dictionary |
| `kCGWindowSharingState` | CFNumber (int32) | None/ReadOnly/ReadWrite |
| `kCGWindowAlpha` | CFNumber (float) | Window alpha (0.0-1.0) |
| `kCGWindowOwnerPID` | CFNumber (int32) | Process ID of the owner |
| `kCGWindowMemoryUsage` | CFNumber (int64) | Memory usage estimate in bytes |

#### Optional Keys (may or may not be present)
| Key | Type | Description |
|-----|------|-------------|
| `kCGWindowOwnerName` | CFString | Name of the owning application |
| `kCGWindowName` | CFString | Title of the window |
| `kCGWindowIsOnscreen` | CFBoolean | Whether the window is on screen |
| `kCGWindowBackingLocationVideoMemory` | CFBoolean | Whether backing store is in VRAM |
| `kCGWindowWorkspace` | CFNumber (int32) | Workspace ID (deprecated in 10.8) |

**Important:** Starting with macOS Catalina (10.15), `kCGWindowName` may not be available without Screen Recording permission. The `kCGWindowOwnerName` is still available without extra permissions.

**Reference:** [CGWindowListCopyWindowInfo (Apple Developer)](https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo(_:_:))

### 3.2 Window List Options

| Option | Description |
|--------|-------------|
| `kCGWindowListOptionAll` | All windows in the user session, including off-screen |
| `kCGWindowListOptionOnScreenOnly` | Only on-screen windows, ordered front to back |
| `kCGWindowListOptionOnScreenAboveWindow` | On-screen windows above specified window |
| `kCGWindowListOptionOnScreenBelowWindow` | On-screen windows below specified window |
| `kCGWindowListOptionIncludingWindow` | Include the specified window |
| `kCGWindowListExcludeDesktopElements` | Exclude desktop elements (icons, wallpaper) |

### 3.3 Window Levels

Window levels determine stacking order. Higher numbers are in front. Actual numerical values are obtained at runtime via `CGWindowLevelForKey()`.

**Reference:** [CGWindowLevelKey (Apple Developer)](https://developer.apple.com/documentation/coregraphics/cgwindowlevelkey)

| Level Key | Typical Value | Description |
|-----------|--------------|-------------|
| `kCGBaseWindowLevelKey` | -2147483648 | Absolute minimum |
| `kCGMinimumWindowLevelKey` | -2147483643 | Minimum usable level |
| `kCGDesktopWindowLevelKey` | -2147483623 | Desktop background |
| `kCGDesktopIconWindowLevelKey` | -2147483603 | Desktop icons |
| `kCGBackstopMenuLevelKey` | -20 | Behind all menus |
| `kCGNormalWindowLevelKey` | 0 | Normal app windows |
| `kCGFloatingWindowLevelKey` | 3 | Floating windows |
| `kCGTornOffMenuWindowLevelKey` | 3 | Torn-off menus |
| `kCGModalPanelWindowLevelKey` | 8 | Modal panels |
| `kCGUtilityWindowLevelKey` | 19 | Utility windows |
| `kCGDockWindowLevelKey` | 20 | The Dock |
| `kCGMainMenuWindowLevelKey` | 24 | Menu bar |
| `kCGStatusWindowLevelKey` | 25 | Status bar items |
| `kCGPopUpMenuWindowLevelKey` | 101 | Popup menus |
| `kCGOverlayWindowLevelKey` | 102 | Overlay windows |
| `kCGHelpWindowLevelKey` | 200 | Help windows |
| `kCGDraggingWindowLevelKey` | 500 | Drag proxy windows |
| `kCGScreenSaverWindowLevelKey` | 1000 | Screen saver |
| `kCGAssistiveTechHighWindowLevelKey` | 1500 | Assistive tech (highest) |
| `kCGCursorWindowLevelKey` | 2147483630 | Cursor windows |
| `kCGMaximumWindowLevelKey` | 2147483631 | Absolute maximum |

**System dialog layer detection:** Gatekeeper/CoreServicesUIAgent dialogs typically appear at `kCGModalPanelWindowLevelKey` (8) or `kCGStatusWindowLevelKey` (25). SecurityAgent password prompts appear at even higher levels. To detect system dialogs, filter `CGWindowListCopyWindowInfo` results where `kCGWindowLayer > 0` and `kCGWindowOwnerName` is `"CoreServicesUIAgent"` or `"SecurityAgent"`.

### 3.4 Window Screenshots

#### CGWindowListCreateImage (Deprecated in macOS 15)
```c
CGImageRef CGWindowListCreateImage(CGRect bounds, CGWindowListOption opts, CGWindowID relWin, CGWindowImageOption imgOpts);
CGImageRef CGWindowListCreateImageFromArray(CGRect bounds, CFArrayRef windowArray, CGWindowImageOption imgOpts);
```

These functions are **obsoleted in macOS 15 (Sequoia)** — the PyObjC Quartz module fails to build with them on macOS 15.

**Reference:** [PyObjC issue #627](https://github.com/ronaldoussoren/pyobjc/issues/627)

#### Window Image Options
| Option | Description |
|--------|-------------|
| `kCGWindowImageDefault` | Standard capture with frame ornamentation |
| `kCGWindowImageBoundsIgnoreFraming` | Exclude frame/shadow from bounds |
| `kCGWindowImageShouldBeOpaque` | Force opaque with white fill |
| `kCGWindowImageOnlyShadows` | Capture only shadows |
| `kCGWindowImageBestResolution` | Best (Retina) resolution |
| `kCGWindowImageNominalResolution` | Screen-matching resolution |

#### ScreenCaptureKit (Modern Replacement)
`SCScreenshotManager` replaces `CGWindowListCreateImage` for screenshots. Requires Screen Recording permission (TCC). Uses async completion handlers.

**Key concern for Nexus:** ScreenCaptureKit is an async, callback-based Objective-C framework. Using it from pyobjc requires careful bridging. The `screencapture` command-line tool remains a practical fallback.

**Reference:** [ScreenCaptureKit (Apple Developer)](https://developer.apple.com/documentation/screencapturekit/)

---

## 4. Private Accessibility APIs

### 4.1 _AXUIElementGetWindow

Bridges AXUIElement (accessibility) to CGWindowID (window server).

```c
extern AXError _AXUIElementGetWindow(AXUIElementRef element, CGWindowID *windowID);
```

**Usage from Python/pyobjc:**
```python
import ctypes
HIServices = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/Frameworks/HIServices.framework/HIServices')
_AXUIElementGetWindow = HIServices._AXUIElementGetWindow
# Need to set argtypes/restype for proper calling
```

**Caveats:**
- Not guaranteed to work on all macOS versions
- Returns `kAXErrorFailure` for some elements (e.g., menu bar items)
- Works reliably for window-level AX elements
- Used extensively by [alt-tab-macos](https://github.com/lwouis/alt-tab-macos) and [yabai](https://github.com/koekeishiya/yabai)

**Reference:** [alt-tab-macos issue #447](https://github.com/lwouis/alt-tab-macos/issues/447), [Hammerspoon private API docs](https://github.com/Hammerspoon/hammerspoon/issues/1469)

### 4.2 AXManualAccessibility

Private attribute for programmatically enabling accessibility in Chromium/Electron apps.

```python
# Set AXManualAccessibility on the application element
AXUIElementSetAttributeValue(app_element, "AXManualAccessibility", True)
```

**Key facts:**
- Separate from `AXEnhancedUserInterface` which is reserved for VoiceOver
- `AXEnhancedUserInterface` has side effects: breaks window positioning and animations in Firefox ([Mozilla bug 1664992](https://bugzilla.mozilla.org/show_bug.cgi?id=1664992))
- `AXManualAccessibility` was added by Electron specifically to avoid these side effects ([Electron PR #10305](https://github.com/electron/electron/pull/10305))
- Chromium builds the accessibility tree asynchronously — need ~2 second wait after setting the attribute
- Some Electron versions had a bug where setting it returned an error even though it worked ([Electron issue #37465](https://github.com/electron/electron/issues/37465), [fix PR #38102](https://github.com/electron/electron/pull/38102))

### 4.3 CGSInternal / SkyLight Private APIs

The CGS (CoreGraphics Services) private APIs provide low-level window server access. SkyLight is the modern successor framework.

**Main repository:** [NUIKit/CGSInternal](https://github.com/NUIKit/CGSInternal)

#### CGSWindow Functions (Selected)
| Function | Description |
|----------|-------------|
| `CGSNewWindow()` | Create a new window |
| `CGSReleaseWindow()` | Release a window |
| `CGSSetWindowLevel()` | Set window stacking level |
| `CGSGetWindowLevel()` | Get window stacking level |
| `CGSMoveWindow()` | Move a window |
| `CGSSetWindowAlpha()` | Set window transparency |
| `CGSGetWindowAlpha()` | Get window transparency |
| `CGSSetWindowTransform()` | Apply affine transform to window |
| `CGSOrderWindow()` | Change window ordering |
| `CGSGetWindowOwner()` | Get owning connection |
| `CGSSetWindowProperty()` | Set arbitrary window property |
| `CGSGetWindowProperty()` | Get arbitrary window property |
| `CGSGetWindowCount()` | Count windows for a connection |
| `CGSGetWindowList()` | List windows for a connection |
| `CGSGetOnScreenWindowList()` | List on-screen windows |
| `CGSSetWindowTags()` | Set window tags (bit flags) |
| `CGSGetScreenRectForWindow()` | Get window bounds |
| `CGSFlushWindow()` | Flush window drawing |
| `CGSWindowIsAccelerated()` | Check if GPU accelerated |
| `CGSSystemStatusBarRegisterWindow()` | Register as status bar window |
| `CGSSetWindowShadowParameters()` | Configure window shadow |
| `CGSWindowBackdropCreateWithLevel()` | Create backdrop blur |
| `CGSSetWindowActive()` | Set window active state |
| `CGSSetMouseFocusWindow()` | Set mouse focus target |

**Reference:** [CGSWindow.h](https://github.com/NUIKit/CGSInternal/blob/master/CGSWindow.h)

#### CGSSpace Functions
| Function | Description |
|----------|-------------|
| `CGSSpaceCreate()` | Create a new Space |
| `CGSSpaceDestroy()` | Destroy a Space |
| `CGSGetActiveSpace()` | Get currently active Space |
| `CGSCopySpaces()` | List all Spaces |
| `CGSCopySpacesForWindows()` | Get Spaces containing windows |
| `CGSAddWindowsToSpaces()` | Assign windows to Spaces |
| `CGSRemoveWindowsFromSpaces()` | Remove windows from Spaces |
| `CGSManagedDisplaySetCurrentSpace()` | Switch active Space per display |
| `CGSSpaceCopyName()` / `CGSSpaceSetName()` | Get/set Space name |
| `CGSShowSpaces()` / `CGSHideSpaces()` | Show/hide Spaces |
| `CGSCopyManagedDisplaySpaces()` | Get Space info per display |

**Reference:** [CGSSpace.h](https://github.com/NUIKit/CGSInternal/blob/master/CGSSpace.h)

#### CGSConnection Functions
| Function | Description |
|----------|-------------|
| `CGSMainConnectionID()` | Get the main connection to WindowServer |
| `CGSNewConnection()` | Create new connection |
| `CGSDefaultConnectionForThread()` | Get connection for current thread |
| `CGSConnectionGetPID()` | Get PID for a connection |
| `CGSCopyConnectionProperty()` | Get connection property |
| `CGSSetConnectionProperty()` | Set connection property |
| `CGSSetUniversalOwner()` | Mark as universal owner |
| `CGSSetLoginwindowConnection()` | Mark as loginwindow connection |
| `CGSRegisterForNewConnectionNotification()` | Observe new connections |
| `CGSRegisterForConnectionDeathNotification()` | Observe connection deaths |

**Reference:** [CGSConnection.h](https://github.com/NUIKit/CGSInternal/blob/master/CGSConnection.h)

#### CGSDisplay Functions
| Function | Description |
|----------|-------------|
| `CGSMainDisplayID()` | Get primary display |
| `CGSGetNumberOfDisplays()` | Count displays |
| `CGSGetDisplayBounds()` | Get display bounds |
| `CGSCopyManagedDisplaySpaces()` | Get Space info per display |
| `CGSGetCurrentDisplayMode()` | Get active display mode |
| `CGSConfigureDisplayMode()` | Change display mode |
| `CGSGetOnlineDisplayList()` | List connected displays |
| `CGSGetActiveDisplayList()` | List active displays |

**Reference:** [CGSDisplays.h](https://github.com/NUIKit/CGSInternal/blob/master/CGSDisplays.h)

### 4.4 SkyLight Framework

SkyLight (`/System/Library/PrivateFrameworks/SkyLight.framework`) is the renamed CoreGraphicsServices framework. It handles windows, menus, animations, and cursor movement.

**Key facts:**
- WindowServer uses SkyLight internally for window compositing and event routing
- Contains packages: Windows, Connection, Event, Cursor, PortStreams, Utilities
- `SLSCopyWindowProperty()` was used to read window titles, but stopped working on Catalina
- Can create windows at the highest system level without special entitlements ([SkyLightWindow](https://github.com/Lakr233/SkyLightWindow))
- Reverse engineering via Hopper Disassembler on the dyld shared cache
- `nm` can extract symbols from the framework binary

**References:**
- [SkyLight.framework wiki](https://github.com/avaidyam/Parrot/wiki/SkyLight.framework)
- [Exploring macOS private frameworks](https://www.jviotti.com/2023/11/20/exploring-macos-private-frameworks.html)
- [WindowServer internals](https://eclecticlight.co/2020/06/08/windowserver-display-compositor-and-input-event-router/)

### 4.5 HIServices Private Functions

The HIServices framework contains the public accessibility API but also private functions:

| Function | Description |
|----------|-------------|
| `_AXUIElementGetWindow()` | Get CGWindowID from AXUIElement |
| `AXTextMarker*` functions | Private text marker navigation (used by WebKit) |
| `_AXUIElementCreateWithRemoteToken()` | Create element from remote process |

**Accessing from Python:**
```python
import ctypes
hisvc = ctypes.cdll.LoadLibrary(
    '/System/Library/Frameworks/ApplicationServices.framework/'
    'Frameworks/HIServices.framework/HIServices'
)
```

**Reference:** [Speaker Deck: Getting started with macOS private APIs](https://speakerdeck.com/niw/getting-started-with-making-macos-utility-app-using-private-apis)

---

## 5. NSAccessibility Protocol (Cocoa Side)

### 5.1 Architecture

The macOS accessibility system has two sides:

| Aspect | NSAccessibility (Cocoa) | AXUIElement (Carbon) |
|--------|------------------------|---------------------|
| **Purpose** | Implement accessibility within your app | Query/control other apps from outside |
| **Who uses it** | App developers | Assistive technologies, automation tools |
| **Scope** | Inside your own process | Cross-process |
| **Framework** | AppKit | ApplicationServices / HIServices |
| **Data model** | Protocol methods on NSView/NSCell | CFTypeRef-based C API |

**Key insight for Nexus:** We always use the AXUIElement (Carbon) API because we are an external client querying other apps. NSAccessibility is what apps use internally to expose their UI to us.

**Reference:** [Apple Accessibility Programming Guide](https://developer.apple.com/library/archive/documentation/Accessibility/Conceptual/AccessibilityMacOSX/OSXAXmodel.html), [Cocoa Accessibility Guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/Accessibility/cocoaAXIntro/cocoaAXintro.html)

### 5.2 How Apps Implement Accessibility

Standard Cocoa controls (NSButton, NSTextField, NSTableView) automatically adopt the NSAccessibility protocol. Custom controls need explicit implementation:

1. Override `accessibilityRole()` to return the appropriate role
2. Override `accessibilityLabel()`, `accessibilityValue()`, etc.
3. Override `accessibilityPerformPress()` for button-like behavior
4. Override `accessibilityChildren()` for container elements

### 5.3 Can External Tools Use NSAccessibility Directly?

**No.** NSAccessibility is an in-process protocol. External tools must go through the AXUIElement C API, which communicates with the target process via Mach messages. The flow is:

```
Your tool → AXUIElementCopyAttributeValue() → Mach IPC → Target app's NSAccessibility → Response → Your tool
```

### 5.4 Additional NSAccessibility Attributes

NSAccessibility in AppKit defines additional string attributes beyond what is in HIServices:
- `NSAccessibilityChildrenInNavigationOrder` — same children as AXChildren but in navigation/tab order
- `NSAccessibilityCustomContent` — custom content for VoiceOver (added in recent macOS)
- Various web-related attributes for WKWebView accessibility

---

## 6. Accessibility Permission Deep Dive

### 6.1 TCC Database

**References:**
- [TCC.db deep dive (Rainforest QA)](https://www.rainforestqa.com/blog/macos-tcc-db-deep-dive)
- [macOS TCC (HackTricks)](https://book.hacktricks.wiki/en/macos-hardening/macos-security-and-privilege-escalation/macos-security-protections/macos-tcc/index.html)

#### Database Locations
| Database | Path | Scope |
|----------|------|-------|
| System | `/Library/Application Support/com.apple.TCC/TCC.db` | System-wide (requires root) |
| User | `~/Library/Application Support/com.apple.TCC/TCC.db` | Per-user |

#### Schema
```sql
CREATE TABLE access (
    service         TEXT NOT NULL,        -- e.g., "kTCCServiceAccessibility"
    client          TEXT NOT NULL,        -- Bundle ID or absolute path
    client_type     INTEGER NOT NULL,     -- 0=bundle ID, 1=path
    auth_value      INTEGER NOT NULL,     -- 0=denied, 1=unknown, 2=allowed, 3=limited
    auth_reason     INTEGER NOT NULL,     -- How permission was set
    auth_version    INTEGER NOT NULL,
    csreq           BLOB,                -- Code signing requirement (prevents impersonation)
    policy_id       INTEGER,
    indirect_object_identifier_type  INTEGER,
    indirect_object_identifier       TEXT NOT NULL DEFAULT "UNUSED",
    indirect_object_code_identity    BLOB,
    flags           INTEGER,
    last_modified   INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER))
);
```

#### auth_value Meanings
| Value | Meaning |
|-------|---------|
| 0 | Access denied |
| 1 | Unknown (not yet decided) |
| 2 | Access allowed |
| 3 | Limited access |

#### auth_reason Codes
| Code | Meaning |
|------|---------|
| 1 | Error |
| 2 | User Consent (user clicked "Allow") |
| 3 | User Set (changed in System Settings) |
| 4 | System Set |
| 5 | Service Policy |
| 6 | MDM Policy |
| 7 | Override Policy |
| 8 | Missing usage string |
| 9 | Prompt Timeout |

#### Key Services for Nexus
| Service | Description | Required? |
|---------|-------------|-----------|
| `kTCCServiceAccessibility` | Control computer (AX API) | **Yes** |
| `kTCCServiceScreenCapture` | Screen recording/screenshots | For screenshots |
| `kTCCServicePostEvent` | Send keystrokes/mouse events | For pyautogui |
| `kTCCServiceSystemPolicyAllFiles` | Full disk access | Not needed |

### 6.2 AXIsProcessTrusted

**Reference:** [AXIsProcessTrustedWithOptions (Apple Developer)](https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions), [Accessibility Permission blog](https://jano.dev/apple/macos/swift/2025/01/08/Accessibility-Permission.html)

#### AXIsProcessTrusted() Caching Behavior
- **Caches per process** — the result is cached once per process lifetime
- A process that starts before permission is granted will return `false` even after the user grants permission
- **Workaround:** Spawn a new process to re-check, or call `AXIsProcessTrustedWithOptions()` which does a fresh check
- The caching is done in the TCC client-side library, not in tccd

#### kAXTrustedCheckOptionPrompt
```python
from ApplicationServices import AXIsProcessTrustedWithOptions
from CoreFoundation import CFDictionaryCreate, kCFBooleanTrue

options = {kAXTrustedCheckOptionPrompt: kCFBooleanTrue}
result = AXIsProcessTrustedWithOptions(options)
```

**Behavior:**
- If `true`: Shows a system dialog "APP_NAME would like to control this computer using accessibility features" with "Open System Settings" and "Deny" buttons
- If `false`: Only checks, does not prompt
- App Sandbox must be OFF for the dialog to appear directly

#### Forcing Permission Re-check
There is **no clean API** to force a re-check. Workarounds:
1. Restart the process
2. Call `AXIsProcessTrustedWithOptions()` instead of `AXIsProcessTrusted()`
3. Query TCC.db directly via sqlite3 (requires SIP disabled for writes)

### 6.3 MDM and Configuration Profiles

**MDM can grant accessibility permission silently:**
- `com.apple.TCC.configuration-profile-policy` payload
- `Services > Accessibility > Allowed` with the app's bundle ID and code requirement
- `auth_reason = 6` (MDM Policy) in TCC.db
- Users cannot revoke MDM-granted permissions through System Settings

### 6.4 TCCd Daemon Architecture

**Reference:** [tccd process journey](https://medium.com/@boutnaru/the-macos-process-journey-tccd-transparency-consent-and-control-daemon-9ac60b950bbe)

- **Location:** `/System/Library/PrivateFrameworks/TCC.framework/Support/tccd` (NOT `/usr/libexec/tccd`)
- **System daemon:** `com.apple.tccd.system` (runs as root)
- **User agent:** `com.apple.tccd` (runs per user)
- **Communication:** XPC dictionary-based API via the private TCC.framework
- **Permission inheritance:** Child processes inherit from parent. This is why Terminal/VS Code gets the permission, not Python itself.

---

## 7. macOS Version Differences

### 7.1 macOS Sonoma (14) — Released September 2023

**Accessibility changes:**
- `kAXExtrasMenuBarAttribute` ("AXExtrasMenuBar") — access to the extras/status menu bar, separate from the main menu bar
- `NSAccessibilityChildrenInNavigationOrder` — tab-order-aware children list
- ScreenCaptureKit deprecation warnings for CGWindowListCreateImage began appearing in betas (were removed in 14.0 release, reappeared in later betas)
- SCScreenshotManager introduced as the official screenshot API replacement

### 7.2 macOS Sequoia (15) — Released September 2024

**Major changes:**
- **CGWindowListCreateImage officially obsoleted** — build fails with pyobjc Quartz module ([PyObjC issue #627](https://github.com/ronaldoussoren/pyobjc/issues/627))
- **Screen recording permission prompts every reboot** (originally weekly, changed to monthly in 15.1) ([9to5Mac article](https://9to5mac.com/2024/08/06/macos-sequoia-screen-recording-privacy-prompt/))
- **Persistent Content Capture entitlement** — Apple provides a special entitlement to suppress recurring prompts, but only for approved apps ([Michael Tsai blog](https://mjtsai.com/blog/2024/08/08/sequoia-screen-recording-prompts-and-the-persistent-content-capture-entitlement/))
- **SCContentSharingPicker** — new system-provided window picker that grants screen capture permission automatically (user picks what to share, so no broad permission needed)
- `CGWindowListCopyWindowInfo` behavior changes: in macOS 26 beta, all status items report as belonging to Apple's Control Center ([Feedback issue #679](https://github.com/feedback-assistant/reports/issues/679))
- Screen recording TCC check now triggers for `CGWindowListCopyWindowInfo` when requesting window names (was already true in Catalina+)

### 7.3 Implications for Nexus

| Feature | Status |
|---------|--------|
| AXUIElement API | Stable, no changes |
| CGWindowListCopyWindowInfo | Works but kCGWindowName needs Screen Recording permission |
| CGWindowListCreateImage | **Broken** on Sequoia 15+ — must use screencapture CLI or ScreenCaptureKit |
| AXObserver | Stable, no changes |
| TCC accessibility | Stable, permission model unchanged |
| Screen recording | Recurring permission prompts on Sequoia — user friction |

---

## 8. Process-Specific Accessibility

### 8.1 Processes That Expose AX Elements

| Process | AX Support | Notes |
|---------|-----------|-------|
| **Finder** | Full | Rich tree with file browser, sidebar, toolbar |
| **Dock** | Full | AXDockItem roles with subroles (app, folder, trash, etc.) |
| **SystemUIServer** | Partial | Menu extras/status items accessible. Manages Notification Center |
| **Control Center** | Partial | Status items accessible via SystemUIServer's extras menu bar |
| **Safari** | Full | Very rich tree (200+ elements) including web content |
| **Chrome** | Full | Needs AXManualAccessibility to enable. Rich tree with web content |
| **VS Code** | Full | Electron app, needs AXManualAccessibility. Content at depth 14-20 |
| **Terminal** | Full | Standard Cocoa app |
| **TextEdit** | Full | Standard Cocoa document app |
| **System Settings** | Full | SwiftUI-based but well-accessible |
| **Preview** | Full | Standard Cocoa document app |
| **Xcode** | Full | Complex but well-structured tree |
| **Microsoft Teams** | Partial | Electron, needs manual accessibility enable |
| **Slack** | Partial | Electron, needs manual accessibility enable |

### 8.2 Processes That DON'T Expose AX Elements

| Process | Why | Workaround |
|---------|-----|-----------|
| **CoreServicesUIAgent** | Gatekeeper/security dialogs run in a special system agent. Exposes NO AX elements to external tools. | Detect via CGWindowListCopyWindowInfo (look for its PID/name + window layer), then use coordinate-based clicking via screenshot analysis |
| **SecurityAgent** | Password/authentication dialogs. Intentionally isolated for security. No AX elements. | None reliable. These dialogs are security-critical. |
| **loginwindow** | Login screen. Runs before user session. | Not accessible from user-space tools |
| **WindowServer** | Compositor process. No UI elements. | N/A |
| **Docker Desktop** | Electron app but tree stays empty even with AXManualAccessibility | Coordinate clicking via screenshots (known blind spot) |

### 8.3 CoreServicesUIAgent Deep Dive

**Reference:** [CoreServicesUIAgent internals (Scott Knight)](https://knight.sc/reverse%20engineering/2019/12/24/coreservicesuiagent-internals.html)

CoreServicesUIAgent (`/System/Library/CoreServices/CoreServicesUIAgent.app`) is a launch agent that provides GUI dialogs for system frameworks:

**Mach services:**
- `com.apple.coreservices.code-evaluation` (NSXPCListener)
- `com.apple.coreservices.quarantine-resolver` (C-based XPC)

**Message handlers:**
| Handler | Purpose |
|---------|---------|
| `CSUIQuarantineMessageHandler` | Gatekeeper malware dialogs |
| `LSLaunchErrorHandler` | App launch error dialogs |
| `CSUILSOpenHandler` | Remote app launching |
| `CSUICheckAccessHandler` | File access verification |
| `CSUIChangeDefaultHandlerHandler` | Default app change prompts |

**Detection strategy for Nexus:**
1. Poll `CGWindowListCopyWindowInfo()` for windows owned by PID matching "CoreServicesUIAgent"
2. Check `kCGWindowLayer > 0` (system dialogs are above normal level)
3. Use screenshot analysis + coordinate clicking as fallback
4. Consider OCR (e.g., Vision framework) to read dialog text from screenshots

### 8.4 Dock Accessibility

The Dock exposes a full AX tree with specialized subroles:
- `AXApplicationDockItem` — running/pinned apps
- `AXDocumentDockItem` — document shortcuts
- `AXFolderDockItem` — folder shortcuts (Downloads, etc.)
- `AXMinimizedWindowDockItem` — minimized window previews
- `AXTrashDockItem` — Trash
- `AXSeparatorDockItem` — section separators

The Dock's AX tree can be accessed via `AXUIElementCreateApplication(dock_pid)`.

### 8.5 NotificationCenter / Control Center

- NotificationCenter is managed by `usernoted` process (previously SystemUIServer)
- Control Center items appear in the extras menu bar, accessible via `kAXExtrasMenuBarAttribute` on the application element
- Status items from third-party apps may report as belonging to "Control Center" in `CGWindowListCopyWindowInfo` on newer macOS versions
- Notification banners may not be accessible via AX API — they are rendered by the system notification subsystem

---

## 9. XPC and macOS IPC

### 9.1 Accessibility-Related XPC Services

**Reference:** [com.apple.hiservices-xpcservice (Apple Forums)](https://developer.apple.com/forums/thread/113858)

| Service | Location | Purpose |
|---------|----------|---------|
| `com.apple.hiservices-xpcservice` | Inside HIServices.framework | Internal accessibility XPC service |
| `com.apple.tccd` | TCC.framework/Support/tccd | Permission enforcement (user-level) |
| `com.apple.tccd.system` | TCC.framework/Support/tccd | Permission enforcement (system-level) |
| `com.apple.accessibility.mediaaccessibilityd` | System | Media accessibility (captions, etc.) |
| `com.apple.VoiceOver` | System | VoiceOver assistive technology |

### 9.2 HIServices XPC Service

**Path:** `/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/XPCServices/com.apple.hiservices-xpcservice.xpc/Contents/MacOS/com.apple.hiservices-xpcservice`

The HIServices framework contains interfaces for:
- Accessibility
- Internet Config
- Pasteboard
- Process Manager
- Translation Manager

The XPC service handles internal communication for accessibility API calls. When you call `AXUIElementCopyAttributeValue()`, it internally goes through:

```
Your process → HIServices → XPC → Target app's accessibility implementation → Response
```

### 9.3 Can Accessibility Data Be Obtained via XPC Directly?

**Not practically.** The AXUIElement API is the supported interface. The underlying XPC/Mach message protocol is private and undocumented. Attempting to bypass the API and send XPC messages directly would be:
1. Fragile across macOS versions
2. Blocked by code signing requirements
3. Subject to TCC enforcement regardless

### 9.4 Mach Messages (Underlying IPC)

The accessibility API ultimately uses Mach messages for cross-process communication:
1. `AXUIElementCopyAttributeValue()` → packages request as Mach message
2. Message sent to target app's Mach port
3. Target app's accessibility implementation processes the request
4. Response sent back as Mach message
5. Result unpacked and returned to caller

This is why accessibility API calls have measurable latency (~1-5ms per call) and why batch operations (walking the full tree) benefit from caching.

---

## Appendix A: Useful GitHub Repositories

| Repository | Description | URL |
|-----------|-------------|-----|
| **NUIKit/CGSInternal** | Private CoreGraphics/SkyLight headers | https://github.com/NUIKit/CGSInternal |
| **phracker/MacOSX-SDKs** | Historical macOS SDK headers | https://github.com/phracker/MacOSX-SDKs |
| **tmandry/AXSwift** | Swift wrapper for AX API | https://github.com/tmandry/AXSwift |
| **steipete/AXorcist** | Swift AX query tool | https://github.com/steipete/AXorcist |
| **lwouis/alt-tab-macos** | Window switcher using private APIs | https://github.com/lwouis/alt-tab-macos |
| **Hammerspoon/hammerspoon** | Lua-based macOS automation | https://github.com/Hammerspoon/hammerspoon |
| **asmagill/hs._asm.axuielement** | Hammerspoon AX element module | https://github.com/asmagill/hs._asm.axuielement |
| **appium/appium-for-mac** | Appium driver with PFAssistive headers | https://github.com/appium/appium-for-mac |
| **eeejay/pyax** | Python AX client library | https://github.com/eeejay/pyax |
| **koekeishiya/yabai** | Tiling window manager using private APIs | https://github.com/koekeishiya/yabai |
| **Lakr233/SkyLightWindow** | SkyLight framework window creation | https://github.com/Lakr233/SkyLightWindow |
| **ronaldoussoren/pyobjc** | Python-ObjC bridge | https://github.com/ronaldoussoren/pyobjc |

## Appendix B: Key Apple Documentation Links

- [AXUIElement.h](https://developer.apple.com/documentation/applicationservices/axuielement_h)
- [AXAttributeConstants.h](https://developer.apple.com/documentation/applicationservices/axattributeconstants_h)
- [AXActionConstants.h](https://developer.apple.com/documentation/applicationservices/axactionconstants_h)
- [AXRoleConstants.h](https://developer.apple.com/documentation/applicationservices/axroleconstants_h)
- [AXNotificationConstants.h](https://developer.apple.com/documentation/applicationservices/axnotificationconstants_h)
- [CGWindowListCopyWindowInfo](https://developer.apple.com/documentation/coregraphics/cgwindowlistcopywindowinfo(_:_:))
- [CGWindowLevelKey](https://developer.apple.com/documentation/coregraphics/cgwindowlevelkey)
- [ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit/)
- [Accessibility Programming Guide](https://developer.apple.com/library/archive/documentation/Accessibility/Conceptual/AccessibilityMacOSX/)
- [NSAccessibility Protocol](https://developer.apple.com/documentation/appkit/nsaccessibility)

## Appendix C: Nexus-Specific Action Items

Based on this research, priority improvements for Nexus:

### High Priority
1. **Add `AXIdentifier` to element output** — when present, this is the most stable identifier for elements across app versions
2. **Use `kAXExtrasMenuBarAttribute`** — access Control Center and status menu items
3. **Add `AXScrollToVisible` action** — scroll elements into view before interacting
4. **Implement `AXBoundsForRange`** — get precise screen coordinates for text ranges
5. **Fix screenshot path for Sequoia** — CGWindowListCreateImage is broken, migrate to `screencapture` CLI or ScreenCaptureKit

### Medium Priority
6. **Detect system dialogs** — poll CGWindowListCopyWindowInfo for CoreServicesUIAgent windows at elevated layer levels
7. **Use `AXManualAccessibility` more broadly** — try on all Electron apps, not just known bundle IDs
8. **Leverage `AXSelectedTextRange` settability** — move cursor position in text fields programmatically
9. **Add AXTextMarker support** — for precise text navigation in WebKit-based apps
10. **Add `AXEnhancedUserInterface` as fallback** — for non-Electron apps that only respond to VoiceOver detection

### Low Priority / Research
11. **Explore `_AXUIElementGetWindow`** — bridge AX elements to CGWindowIDs for screenshot targeting
12. **Investigate CGSInternal** — Space management for multi-desktop scenarios
13. **Monitor TCC changes** — Sequoia's screen recording prompts may affect screenshot workflows
14. **Profile AX API latency** — measure per-call overhead to optimize tree walking
15. **Research ScreenCaptureKit from pyobjc** — async APIs are harder but may be necessary long-term
