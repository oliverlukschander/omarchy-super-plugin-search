import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui
import "SearchModel.js" as SearchModel

Item {
  id: root

  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  property var shell: null
  property var manifest: null

  property bool opened: false
  property string filterText: ""
  property bool filterMute: false
  property int modeIndex: 0
  readonly property var modeIds: ["popular", "new", "installed", "updates"]
  readonly property var modeLabels: ["Popular", "New", "Installed", "Updates"]
  property int selectedIndex: 0
  property bool cursorActive: false
  property string statusText: ""
  property bool catalogBusy: false
  property bool removeBusy: false
  property bool deleteConfirmOpen: false
  property var deleteTarget: null
  property string removeError: ""
  property int searchSerial: 0
  property bool searchPending: false
  property string categoryFilter: ""
  property var rowData: []

  readonly property string pluginDir: (root.manifest && root.manifest.__sourceDir)
    ? String(root.manifest.__sourceDir).replace(/\/$/, "")
    : (Quickshell.env("HOME") + "/.config/omarchy/plugins/oliverlukschander.super-plugin-search")
  readonly property string python: "/usr/bin/python3"
  readonly property string searchScript: root.pluginDir + "/scripts/search.py"
  readonly property string catalogScript: root.pluginDir + "/scripts/catalog.py"
  readonly property string installScript: root.pluginDir + "/scripts/install.py"

  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color border: Color.menu.border
  property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  property color scrim: Color.menu.scrim
  property color selectedBackground: Color.menu.selectedBackground
  property color selectedText: Color.menu.selectedText
  property var selectedBorderSpec: Border.surfaceSpec("menu", "selected-border", Color.menu.selectedBorder, 0)
  readonly property int cornerRadius: Style.cornerRadius
  property string fontFamily: Style.font.menuFamily
  property int contentMargin: Style.spacing.panelPadding
  property int headerHeight: Math.max(Style.space(34), Style.font.title + Style.spacing.controlPaddingY * 2)
  property int contentSpacing: Style.spacing.md
  property int cardWidth: Math.min(Style.space(1080), panel.width - Style.gapsOut * 2)
  property int previewWidth: Style.space(420)
  property int shotHeight: Math.max(Style.space(280), Math.round(root.cardHeight * 0.5))
  property int cardHeight: Math.min(Style.space(760), panel.height - Style.gapsOut * 2)
  property int rowHeight: Math.max(Style.space(58), Style.font.body + Style.font.caption + Style.spacing.rowPaddingX * 2)

  readonly property var selectedRow: {
    var rows = root.rowData
    var index = root.selectedIndex
    if (!rows || index < 0 || index >= rows.length) return null
    return rows[index]
  }
  readonly property string selectedPreview: root.selectedRow ? String(root.selectedRow.previewUrl || "") : ""
  property string previewFile: ""
  property string previewWanted: ""

  onSelectedPreviewChanged: root.cacheSelectedPreview()

  function cacheSelectedPreview() {
    var url = root.selectedPreview
    if (url === root.previewWanted && root.previewFile.length > 0) return
    root.previewWanted = url
    if (root.previewFile.length > 0 && previewProc.url !== url) root.previewFile = ""
    if (!url || previewProc.running) return
    root.fetchPreview()
  }

  function fetchPreview() {
    var url = root.previewWanted
    if (!url || previewProc.running) return
    previewProc.url = url
    previewProc.command = [root.python, "-I", root.searchScript, "--cache-preview", url]
    previewProc.running = true
  }

  component Metric: Item {
    property string glyph: ""
    property string value: ""
    property bool active: false

    implicitWidth: Style.space(52)
    implicitHeight: Style.font.bodySmall

    Row {
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(4)
      visible: value.length > 0

      Text {
        textFormat: Text.PlainText
        text: glyph
        color: active ? root.selectedText : root.foreground
        opacity: active ? 0.92 : 0.38
        font.family: root.fontFamily
        font.pixelSize: Style.font.iconSmall
        verticalAlignment: Text.AlignVCenter
      }

      Text {
        textFormat: Text.PlainText
        text: value
        color: active ? root.selectedText : root.foreground
        opacity: active ? 0.92 : 0.45
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        font.weight: Font.Medium
        verticalAlignment: Text.AlignVCenter
      }
    }
  }

  component Choice: Button {
    bordered: true
    focusable: false
    foreground: root.foreground
    background: "transparent"
    accent: root.selectedText
    fontFamily: root.fontFamily
    fontSize: Style.font.bodySmall
    iconSize: Style.font.iconSmall
    horizontalPadding: Style.space(8)
    verticalPadding: Style.space(3)
  }

  function open(payloadJson) {
    root.opened = true
    root.modeIndex = 0
    root.categoryFilter = ""
    root.selectedIndex = 0
    root.cursorActive = true
    root.deleteConfirmOpen = false
    root.deleteTarget = null
    root.statusText = "Updating catalog…"
    root.filterMute = true
    root.filterText = ""
    queryField.text = ""
    root.filterMute = false
    root.disarmPointer()
    Qt.callLater(function() { queryField.forceActiveFocus() })
    root.refreshCatalog(false)
  }

  function close() {
    root.opened = false
    root.deleteConfirmOpen = false
    debounce.stop()
  }

  function dismiss() {
    root.close()
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "oliverlukschander.super-plugin-search")
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function setFilter(nextFilter) {
    var next = String(nextFilter || "")
    root.filterMute = true
    if (queryField.text !== next) queryField.text = next
    root.filterMute = false
    if (root.filterText === next && queryField.text === next) {
      root.selectedIndex = 0
      debounce.restart()
      return
    }
    root.filterText = next
    root.selectedIndex = 0
    root.cursorActive = true
    root.disarmPointer()
    debounce.restart()
  }

  function setMode(index) {
    var next = Math.max(0, Math.min(index, root.modeIds.length - 1))
    if (next === root.modeIndex) {
      queryField.forceActiveFocus()
      return
    }
    root.modeIndex = next
    root.selectedIndex = 0
    root.cursorActive = true
    root.disarmPointer()
    root.requestSearch()
    queryField.forceActiveFocus()
  }

  function cycleMode(delta) {
    var count = root.modeIds.length
    root.setMode((root.modeIndex + delta + count) % count)
  }

  function setCategory(value) {
    var next = String(value || "")
    if (next === root.categoryFilter) {
      queryField.forceActiveFocus()
      return
    }
    root.categoryFilter = next
    root.selectedIndex = 0
    root.cursorActive = true
    root.disarmPointer()
    root.requestSearch()
    queryField.forceActiveFocus()
  }

  function applyCategories(raw) {
    var names = SearchModel.parseRows(raw)
    categoryModel.clear()
    categoryModel.append({ categoryId: "", label: "All" })
    for (var i = 0; i < names.length; i++) {
      var name = String(names[i] || "")
      if (name) categoryModel.append({ categoryId: name, label: name })
    }
  }

  function disarmPointer() {
    pointerGate.reset()
  }

  function selectFromPointer(index, item, mouse) {
    if (!pointerGate.moved(item, mouse)) return
    root.cursorActive = true
    root.selectedIndex = index
  }

  function select(delta) {
    if (displayModel.count === 0) return
    root.disarmPointer()
    if (!root.cursorActive) {
      root.cursorActive = true
      root.selectedIndex = delta < 0 ? displayModel.count - 1 : 0
    } else {
      root.selectedIndex = (root.selectedIndex + delta + displayModel.count) % displayModel.count
    }
    resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
  }

  function selectAbsolute(index) {
    if (displayModel.count === 0) return
    root.disarmPointer()
    root.cursorActive = true
    root.selectedIndex = Math.max(0, Math.min(index, displayModel.count - 1))
    resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
  }

  function fullSha(value) {
    return /^[0-9a-f]{40}$/.test(String(value || ""))
  }

  function applyRows(raw, serial) {
    if (serial !== root.searchSerial) return
    var rows = SearchModel.parseRows(raw)
    var data = []
    displayModel.clear()
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i] || {}
      var item = {
        pluginId: String(row.pluginId || ""),
        name: String(row.name || ""),
        detail: String(row.detail || ""),
        description: String(row.description || ""),
        version: String(row.version || ""),
        previewUrl: String(row.previewUrl || ""),
        manualSetup: !!row.manualSetup,
        statusLabel: String(row.statusLabel || ""),
        actionText: String(row.actionText || ""),
        hint: String(row.hint || ""),
        enterAction: String(row.enterAction || ""),
        icon: String(row.icon || "󰐱"),
        repo: String(row.repo || ""),
        listingUrl: String(row.listingUrl || ""),
        installUrl: String(row.installUrl || ""),
        installCommit: String(row.installCommit || ""),
        canInstall: !!row.canInstall,
        canUpdate: !!row.canUpdate,
        canRemove: !!row.canRemove,
        installed: !!row.installed
      }
      data.push(item)
      displayModel.append({
        pluginId: item.pluginId,
        name: item.name,
        detail: item.detail,
        icon: item.icon,
        statusLabel: item.statusLabel,
        starsText: String(row.starsText || ""),
        heartsText: String(row.heartsText || ""),
        copiesText: String(row.copiesText || "")
      })
    }
    root.rowData = data
    if (displayModel.count === 0) root.selectedIndex = 0
    else if (root.selectedIndex >= displayModel.count) root.selectedIndex = displayModel.count - 1
    else if (root.selectedIndex < 0) root.selectedIndex = 0
    Qt.callLater(function() {
      if (displayModel.count > 0)
        resultList.positionViewAtIndex(root.selectedIndex, ListView.Contain)
    })
  }

  function requestSearch() {
    root.searchSerial++
    if (searchProc.running) {
      root.searchPending = true
      return
    }
    root.startSearch()
  }

  function startSearch() {
    root.searchPending = false
    searchProc.searchSerial = root.searchSerial
    var command = [
      root.python, "-I", root.searchScript,
      "--query", root.filterText,
      "--mode", root.modeIds[root.modeIndex]
    ]
    if (root.categoryFilter)
      command = command.concat(["--category", root.categoryFilter])
    searchProc.command = command
    searchProc.running = true
  }

  function refreshCatalog(force) {
    root.catalogBusy = true
    if (!root.statusText) root.statusText = "Updating catalog…"
    catalogProc.command = force
      ? [root.python, "-I", root.catalogScript, "--force"]
      : [root.python, "-I", root.catalogScript]
    catalogProc.running = false
    catalogProc.running = true
  }

  function notify(headline, description) {
    var cmd = [root.omarchyPath + "/bin/omarchy-notification-send", "-g", "󰐱", headline]
    if (description) cmd.push(description)
    Quickshell.execDetached(cmd)
  }

  function openUrl(url) {
    if (!url) return
    Quickshell.execDetached([root.omarchyPath + "/bin/omarchy-launch-webapp", url])
  }

  function rowAt(index) {
    if (index < 0 || index >= root.rowData.length) return null
    return root.rowData[index]
  }

  function activateIndex(index) {
    if (root.deleteConfirmOpen || root.removeBusy) return
    var row = root.rowAt(index)
    if (!row) return
    if ((row.enterAction === "install" || row.enterAction === "update")
        && row.installUrl && root.fullSha(row.installCommit)) {
      var command = root.python + " -I " + root.installScript
      if (row.enterAction === "update") command += " update"
      command += " " + row.installUrl + " " + row.installCommit
      root.dismiss()
      Quickshell.execDetached([
        root.omarchyPath + "/bin/omarchy-launch-floating-terminal-with-presentation",
        command
      ])
      return
    }
    if (row.enterAction === "uninstall") {
      root.requestDeleteSelected()
      return
    }
    if (row.enterAction === "builtin") {
      root.notify("Built in", row.name)
      return
    }
    root.notify("Can't install this listing", row.name)
  }

  function requestDeleteSelected() {
    if (root.deleteConfirmOpen || root.removeBusy) return
    var row = root.rowAt(root.selectedIndex)
    if (!row || !row.canRemove) return
    root.deleteTarget = { pluginId: row.pluginId, name: row.name }
    deleteConfirm.selectedIndex = 1
    root.deleteConfirmOpen = true
  }

  function cancelDelete() {
    root.deleteConfirmOpen = false
    root.deleteTarget = null
    deleteConfirm.selectedIndex = 1
    root.disarmPointer()
    Qt.callLater(function() { queryField.forceActiveFocus() })
  }

  function confirmDelete() {
    var target = root.deleteTarget
    root.deleteConfirmOpen = false
    if (!target || !target.pluginId || root.removeBusy) return
    root.removeBusy = true
    root.removeError = ""
    removeProc.command = [root.python, "-I", root.installScript, "remove", target.pluginId]
    removeProc.running = true
  }

  function openRepo(index) {
    var row = root.rowAt(index)
    if (row && row.repo) root.openUrl(row.repo)
  }

  function openListing(index) {
    var row = root.rowAt(index)
    if (row && row.listingUrl) root.openUrl(row.listingUrl)
  }

  function handleKey(name) {
    if (!root.opened || root.deleteConfirmOpen) return
    if (name === "tab") root.cycleMode(1)
    else if (name === "backtab") root.cycleMode(-1)
    else if (name === "up") root.select(-1)
    else if (name === "down") root.select(1)
    else if (name === "pageup") root.select(-10)
    else if (name === "pagedown") root.select(10)
    else if (name === "return") {
      if (root.cursorActive) root.activateIndex(root.selectedIndex)
      else if (displayModel.count > 0) root.cursorActive = true
    } else if (name === "escape") {
      if (root.filterText) root.setFilter("")
      else if (root.categoryFilter) root.setCategory("")
      else root.dismiss()
    } else if (name === "delete") root.requestDeleteSelected()
    else if (name === "refresh") root.refreshCatalog(true)
    else if (name === "repo") root.openRepo(root.selectedIndex)
    else if (name === "listing") root.openListing(root.selectedIndex)
  }

  onDeleteConfirmOpenChanged: {
    if (root.deleteConfirmOpen) keyCatcher.forceActiveFocus()
    else if (root.opened) queryField.forceActiveFocus()
  }
  onOpenedChanged: if (!opened) { deleteConfirmOpen = false; deleteTarget = null }

  ListModel { id: displayModel }
  ListModel { id: categoryModel }

  PointerMoveGate {
    id: pointerGate
    referenceItem: card
  }

  Timer {
    id: debounce
    interval: 80
    repeat: false
    onTriggered: root.requestSearch()
  }

  Process {
    id: catalogProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var status = SearchModel.parseStatus(text)
        if (status.ok) {
          root.statusText = ""
        } else {
          root.statusText = status.error
            ? "Couldn't reach plugins.omarchy.org"
            : "Couldn't update catalog"
        }
      }
    }
    onExited: {
      root.catalogBusy = false
      categoriesProc.running = false
      categoriesProc.command = [root.python, "-I", root.searchScript, "--categories"]
      categoriesProc.running = true
      root.requestSearch()
    }
  }

  Process {
    id: categoriesProc
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyCategories(text)
    }
  }

  Process {
    id: searchProc
    property int searchSerial: 0
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyRows(text, searchProc.searchSerial)
    }
    onExited: {
      if (root.searchPending) root.startSearch()
    }
  }

  Process {
    id: previewProc
    property string url: ""
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (previewProc.url !== root.previewWanted) return
        root.previewFile = String(text || "").trim()
      }
    }
    onExited: {
      if (root.previewWanted && root.previewWanted !== previewProc.url)
        root.fetchPreview()
    }
  }

  Process {
    id: removeProc
    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.removeError = String(text || "").trim()
    }
    onExited: function(exitCode) {
      root.removeBusy = false
      var failed = root.removeError
      var name = (root.deleteTarget && root.deleteTarget.name) || ""
      root.removeError = ""
      root.deleteTarget = null
      if (exitCode === 0) root.requestSearch()
      else root.notify("Couldn't remove plugin", failed || name)
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omarchy-super-plugin-search"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: root.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      width: root.cardWidth
      height: root.cardHeight
      radius: root.cornerRadius
      anchors.centerIn: parent
      color: root.background
      borderSpec: root.borderSpec
      padding: root.contentMargin

      MouseArea { anchors.fill: parent; onClicked: {} }

      Item {
        id: keyCatcher
        anchors.fill: parent
        z: root.deleteConfirmOpen ? 20 : 0
        focus: root.deleteConfirmOpen

        Keys.onPressed: function(event) {
          if (root.deleteConfirmOpen && deleteConfirm.handleKey(event))
            event.accepted = true
        }

        ConfirmDialog {
          id: deleteConfirm
          anchors.fill: parent
          opened: root.deleteConfirmOpen
          z: 10
          message: "Do you want to uninstall " + ((root.deleteTarget && root.deleteTarget.name) || "") + "?"
          confirmText: "Uninstall"
          background: root.background
          foreground: root.foreground
          scrim: root.scrim
          selectedBackground: root.selectedBackground
          selectedText: root.selectedText
          fontFamily: root.fontFamily
          cornerRadius: root.cornerRadius
          onCanceled: root.cancelDelete()
          onConfirmed: root.confirmDelete()
        }
      }

      Item {
        id: content
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset

        Column {
          id: previewPane
          anchors.top: parent.top
          anchors.bottom: parent.bottom
          anchors.left: parent.left
          width: displayModel.count > 0 ? root.previewWidth : 0
          visible: width > 0
          clip: true
          spacing: root.contentSpacing

          Item {
            id: shotFrame
            width: parent.width
            height: root.selectedPreview.length > 0 ? root.shotHeight : 0
            visible: height > 0

            Image {
              id: previewImage
              anchors.fill: parent
              fillMode: Image.PreserveAspectFit
              source: root.previewFile.length > 0 ? ("file://" + root.previewFile) : ""
              visible: source != "" && status !== Image.Error
              sourceSize.width: 960
              sourceSize.height: 960
            }
          }

          Column {
            id: detailColumn
            width: parent.width
            spacing: Style.space(4)

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.selectedRow ? String(root.selectedRow.description || "") : ""
              visible: text.length > 0
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              wrapMode: Text.WordWrap
              maximumLineCount: 6
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.selectedRow ? String(root.selectedRow.version || "") : ""
              visible: text.length > 0
              color: root.foreground
              opacity: 0.52
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: "Manual setup"
              visible: root.selectedRow && root.selectedRow.manualSetup
              color: root.foreground
              opacity: 0.52
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.selectedRow ? String(root.selectedRow.actionText || "") : ""
              visible: text.length > 0
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              elide: Text.ElideRight
            }

            Text {
              width: parent.width
              textFormat: Text.PlainText
              text: root.selectedRow ? String(root.selectedRow.hint || "") : ""
              visible: text.length > 0
              color: root.foreground
              opacity: 0.52
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              elide: Text.ElideRight
            }
          }
        }

        Item {
          id: browser
          anchors.top: parent.top
          anchors.bottom: parent.bottom
          anchors.left: previewPane.right
          anchors.right: parent.right
          anchors.leftMargin: previewPane.visible ? root.contentSpacing : 0

        BorderSurface {
          id: queryBox
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          height: root.headerHeight
          radius: root.cornerRadius
          clip: true
          color: Style.controlFill(queryField.activeFocus, false, root.foreground, root.selectedText)
          borderSpec: Border.controlSpec(queryField.activeFocus ? "focus" : "normal", root.foreground, root.selectedText)

          Text {
            visible: queryField.text.length === 0 && String(queryField.preeditText || "").length === 0
            text: "Search plugins…"
            color: root.foreground
            opacity: 0.58
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: Style.spacing.controlPaddingX + Border.left(queryBox.borderSpec)
          }

          TextInput {
            id: queryField
            anchors.fill: parent
            anchors.leftMargin: Style.spacing.controlPaddingX + Border.left(queryBox.borderSpec)
            anchors.rightMargin: Style.spacing.controlPaddingX + Border.right(queryBox.borderSpec)
            verticalAlignment: TextInput.AlignVCenter
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            color: root.foreground
            clip: true
            selectByMouse: true
            selectionColor: Style.selectionFillFor(root.foreground, root.selectedText)
            selectedTextColor: root.foreground
            activeFocusOnTab: false

            onTextChanged: {
              if (root.filterMute || text === root.filterText) return
              root.filterText = text
              root.selectedIndex = 0
              root.cursorActive = true
              root.disarmPointer()
              debounce.restart()
            }

            Keys.onPressed: function(event) {
              if (root.deleteConfirmOpen) {
                if (deleteConfirm.handleKey(event)) event.accepted = true
                return
              }
              var ctrl = event.modifiers === Qt.ControlModifier
              if (event.key === Qt.Key_Escape) {
                root.handleKey("escape")
                event.accepted = true
              } else if (event.key === Qt.Key_Backtab || (event.key === Qt.Key_Tab && (event.modifiers & Qt.ShiftModifier))) {
                root.handleKey("backtab")
                event.accepted = true
              } else if (event.key === Qt.Key_Tab) {
                root.handleKey("tab")
                event.accepted = true
              } else if (event.key === Qt.Key_Up) {
                root.handleKey("up")
                event.accepted = true
              } else if (event.key === Qt.Key_Down) {
                root.handleKey("down")
                event.accepted = true
              } else if (event.key === Qt.Key_PageUp) {
                root.handleKey("pageup")
                event.accepted = true
              } else if (event.key === Qt.Key_PageDown) {
                root.handleKey("pagedown")
                event.accepted = true
              } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.handleKey("return")
                event.accepted = true
              } else if (event.key === Qt.Key_Delete) {
                root.handleKey("delete")
                event.accepted = true
              } else if (ctrl && event.key === Qt.Key_R) {
                root.handleKey("refresh")
                event.accepted = true
              } else if (ctrl && event.key === Qt.Key_O) {
                root.handleKey("repo")
                event.accepted = true
              } else if (ctrl && event.key === Qt.Key_L) {
                root.handleKey("listing")
                event.accepted = true
              }
            }
          }
        }

        Row {
          id: modeRow
          anchors.top: queryBox.bottom
          anchors.left: parent.left
          anchors.topMargin: root.contentSpacing
          spacing: Style.spacing.sm

          Choice { text: "Popular"; selected: root.modeIndex === 0; onClicked: root.setMode(0) }
          Choice { text: "New"; selected: root.modeIndex === 1; onClicked: root.setMode(1) }
          Choice { text: "Installed"; selected: root.modeIndex === 2; onClicked: root.setMode(2) }
          Choice { text: "Updates"; selected: root.modeIndex === 3; onClicked: root.setMode(3) }
        }

        Flickable {
          id: categoryStrip
          anchors.top: modeRow.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.topMargin: visible ? root.contentSpacing : 0
          height: visible ? Math.max(categoryRow.implicitHeight, Style.space(1)) : 0
          contentWidth: categoryRow.implicitWidth
          contentHeight: height
          flickableDirection: Flickable.HorizontalFlick
          boundsBehavior: Flickable.StopAtBounds
          clip: true
          visible: categoryModel.count > 1

          Row {
            id: categoryRow
            spacing: Style.spacing.sm

            Repeater {
              model: categoryModel

              delegate: Choice {
                required property string categoryId
                required property string label

                text: label
                selected: root.categoryFilter === categoryId
                onClicked: root.setCategory(categoryId)
              }
            }
          }

          WheelHandler {
            onWheel: function(event) {
              var delta = event.angleDelta.x !== 0 ? event.angleDelta.x : event.angleDelta.y
              var maxX = Math.max(0, categoryStrip.contentWidth - categoryStrip.width)
              categoryStrip.contentX = Math.max(0, Math.min(maxX, categoryStrip.contentX - delta))
            }
          }
        }

        Rectangle {
          id: catDivider
          anchors.top: categoryStrip.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.topMargin: visible ? root.contentSpacing : 0
          height: visible ? Style.spacing.hairline : 0
          visible: categoryStrip.visible
          color: Util.alpha(root.foreground, 0.2)
        }

        Item {
          id: listArea
          anchors.top: catDivider.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          anchors.topMargin: root.contentSpacing

          ListView {
            id: resultList
            anchors.fill: parent
            model: displayModel
            clip: true
            spacing: Style.spacing.xs
            boundsBehavior: Flickable.StopAtBounds
            visible: displayModel.count > 0

            delegate: BorderSurface {
              id: row
              required property int index
              required property string name
              required property string detail
              required property string icon
              required property string statusLabel
              required property string starsText
              required property string heartsText
              required property string copiesText

              readonly property bool hasCursor: root.cursorActive && index === root.selectedIndex

              width: ListView.view.width
              height: root.rowHeight
              radius: root.cornerRadius
              color: hasCursor ? root.selectedBackground : "transparent"
              borderSpec: hasCursor ? root.selectedBorderSpec : Border.none()

              Text {
                id: iconText
                textFormat: Text.PlainText
                text: row.icon
                color: row.hasCursor ? root.selectedText : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.iconLarge
                width: Style.space(36)
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                anchors.left: parent.left
                anchors.leftMargin: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
              }

              Row {
                id: metrics
                spacing: Style.space(8)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter

                Metric { glyph: "󰓎"; value: row.starsText; active: row.hasCursor }
                Metric { glyph: "󰣐"; value: row.heartsText; active: row.hasCursor }
                Metric { glyph: "󰉉"; value: row.copiesText; active: row.hasCursor }
              }

              Text {
                id: statusMark
                textFormat: Text.PlainText
                width: Style.space(108)
                text: row.statusLabel
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
                color: row.hasCursor ? root.selectedText : root.foreground
                opacity: 0.52
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                anchors.right: metrics.left
                anchors.rightMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
              }

              Column {
                id: contentColumn
                anchors.left: iconText.right
                anchors.leftMargin: Style.space(6)
                anchors.right: statusMark.left
                anchors.rightMargin: Style.space(12)
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.space(3)

                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: row.name
                  color: row.hasCursor ? root.selectedText : root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.heading
                  font.weight: Font.Medium
                  elide: Text.ElideRight
                }

                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: row.detail
                  visible: text.length > 0
                  color: root.foreground
                  opacity: 0.52
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  elide: Text.ElideRight
                }
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onPositionChanged: function(mouse) {
                  root.selectFromPointer(row.index, row, mouse)
                }
                onClicked: {
                  root.cursorActive = true
                  root.selectedIndex = row.index
                  root.activateIndex(row.index)
                }
              }
            }
          }

          Column {
            anchors.centerIn: parent
            spacing: Style.space(8)
            visible: displayModel.count === 0
            width: parent.width - Style.space(24)

            Text {
              text: "󰈉"
              color: root.selectedText
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.displayLarge
              horizontalAlignment: Text.AlignHCenter
              width: parent.width
            }

            Text {
              textFormat: Text.PlainText
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: root.catalogBusy
                ? "Updating catalog…"
                : (root.filterText ? ("No matches for “" + root.filterText + "”") : (root.statusText || "Nothing here yet"))
              color: root.foreground
              opacity: 0.7
              font.family: root.fontFamily
              font.pixelSize: Style.font.title
              wrapMode: Text.WordWrap
            }
          }
        }
        }
      }
    }
  }
}
