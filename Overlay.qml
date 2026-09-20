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
  property int selectedIndex: 0
  property bool cursorActive: false
  property string statusText: ""
  property bool catalogBusy: false
  property int searchSerial: 0
  property int applySerial: 0
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
  property int cardWidth: Math.min(Style.space(680), panel.width - Style.gapsOut * 2)
  property int cardHeight: Math.min(Style.space(760), panel.height - Style.gapsOut * 2)
  property int rowHeight: Math.max(Style.space(58), Style.font.body + Style.font.caption + Style.spacing.rowPaddingX * 2)
  readonly property string selectedSummary: {
    var rows = root.rowData
    var index = root.selectedIndex
    if (!rows || index < 0 || index >= rows.length) return ""
    var row = rows[index]
    return row ? String(row.summary || "") : ""
  }

  component Metric: Row {
    property string glyph: ""
    property string value: ""
    property bool active: false
    spacing: Style.space(5)
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

  function open(payloadJson) {
    root.opened = true
    root.filterText = ""
    root.categoryFilter = ""
    root.selectedIndex = 0
    root.cursorActive = true
    root.statusText = "Updating catalog…"
    root.disarmPointer()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
    root.refreshCatalog(false)
  }

  function close() {
    root.opened = false
    debounce.stop()
  }

  function dismiss() {
    root.opened = false
    debounce.stop()
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "oliverlukschander.super-plugin-search")
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function setFilter(nextFilter) {
    root.filterText = nextFilter
    root.selectedIndex = 0
    root.cursorActive = true
    root.disarmPointer()
    debounce.restart()
  }

  function setCategory(value) {
    var next = String(value || "")
    if (next === root.categoryFilter) {
      Qt.callLater(function() { keyCatcher.forceActiveFocus() })
      return
    }
    root.categoryFilter = next
    root.selectedIndex = 0
    root.cursorActive = true
    root.disarmPointer()
    root.requestSearch()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
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
        summary: String(row.description || ""),
        icon: String(row.icon || "󰐱"),
        repo: String(row.repo || ""),
        listingUrl: String(row.listingUrl || ""),
        installUrl: String(row.installUrl || ""),
        canInstall: !!row.canInstall,
        installed: !!row.installed,
        verified: !!row.verified,
        starsText: String(row.starsText || ""),
        heartsText: String(row.heartsText || ""),
        copiesText: String(row.copiesText || "")
      }
      data.push(item)
      displayModel.append({
        pluginId: item.pluginId,
        name: item.name,
        detail: item.detail,
        icon: item.icon,
        installed: item.installed,
        starsText: item.starsText,
        heartsText: item.heartsText,
        copiesText: item.copiesText
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
    var command = [root.python, "-I", root.searchScript, "--query", root.filterText]
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
    var row = root.rowAt(index)
    if (!row) return
    if (row.installed) {
      root.notify("Already installed", row.name)
      return
    }
    if (row.installUrl) {
      root.dismiss()
      Quickshell.execDetached([
        root.omarchyPath + "/bin/omarchy-launch-floating-terminal-with-presentation",
        root.python + " -I " + root.installScript + " " + row.installUrl
      ])
      return
    }
    root.notify("Can't install this listing", row.name)
  }

  function openRepo(index) {
    var row = root.rowAt(index)
    if (row && row.repo) root.openUrl(row.repo)
  }

  function openListing(index) {
    var row = root.rowAt(index)
    if (row && row.listingUrl) root.openUrl(row.listingUrl)
  }

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
        focus: true

        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          if (event.key === Qt.Key_Escape) {
            if (root.filterText) root.setFilter("")
            else if (root.categoryFilter) root.setCategory("")
            else root.dismiss()
            event.accepted = true
          } else if (event.key === Qt.Key_R && event.modifiers === Qt.ControlModifier) {
            root.refreshCatalog(true)
            event.accepted = true
          } else if (event.key === Qt.Key_O && event.modifiers === Qt.ControlModifier) {
            root.openRepo(root.selectedIndex)
            event.accepted = true
          } else if (event.key === Qt.Key_L && event.modifiers === Qt.ControlModifier) {
            root.openListing(root.selectedIndex)
            event.accepted = true
          } else if (Util.editsFilter(event, root.filterText)) {
            root.setFilter(Util.editedFilter(event, root.filterText))
            event.accepted = true
          } else if (event.key === Qt.Key_Up) {
            root.select(-1)
            event.accepted = true
          } else if (event.key === Qt.Key_Down) {
            root.select(1)
            event.accepted = true
          } else if (event.key === Qt.Key_PageUp) {
            root.select(-10)
            event.accepted = true
          } else if (event.key === Qt.Key_PageDown) {
            root.select(10)
            event.accepted = true
          } else if (event.key === Qt.Key_Home) {
            root.selectAbsolute(0)
            event.accepted = true
          } else if (event.key === Qt.Key_End) {
            root.selectAbsolute(displayModel.count - 1)
            event.accepted = true
          } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (root.cursorActive) root.activateIndex(root.selectedIndex)
            else if (displayModel.count > 0) root.cursorActive = true
            event.accepted = true
          } else if (event.text && event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127) {
            if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
              return
            root.setFilter(root.filterText + event.text)
            event.accepted = true
          }
        }
      }

      Item {
        id: content
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset

        Rectangle {
          id: header
          anchors.top: parent.top
          anchors.left: parent.left
          anchors.right: parent.right
          height: root.headerHeight
          radius: root.cornerRadius
          color: "transparent"

          Text {
            textFormat: Text.PlainText
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: root.filterText || "Search plugins…"
            color: root.foreground
            opacity: root.filterText ? 1 : 0.58
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            elide: Text.ElideRight
          }
        }

        Flow {
          id: categoryFlow
          anchors.top: header.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.topMargin: visible ? root.contentSpacing : 0
          height: visible ? implicitHeight : 0
          spacing: Style.spacing.sm
          visible: categoryModel.count > 1

          Repeater {
            model: categoryModel

            delegate: Button {
              required property string categoryId
              required property string label

              text: label
              selected: root.categoryFilter === categoryId
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
              onClicked: root.setCategory(categoryId)
            }
          }
        }

        Rectangle {
          id: catDivider
          anchors.top: categoryFlow.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.topMargin: visible ? root.contentSpacing : 0
          height: visible ? Style.spacing.hairline : 0
          visible: categoryFlow.visible
          color: Util.alpha(root.foreground, 0.2)
        }

        Column {
          id: descFooter
          visible: displayModel.count > 0 && root.selectedSummary.length > 0
          width: parent.width
          height: visible ? implicitHeight : 0
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          spacing: root.contentSpacing

          Rectangle {
            width: parent.width
            height: Style.spacing.hairline
            color: Util.alpha(root.foreground, 0.2)
          }

          Text {
            width: parent.width
            textFormat: Text.PlainText
            text: root.selectedSummary
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
            maximumLineCount: 4
            elide: Text.ElideRight
          }
        }

        Item {
          id: listArea
          anchors.top: catDivider.bottom
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: descFooter.top
          anchors.topMargin: root.contentSpacing
          anchors.bottomMargin: descFooter.visible ? root.contentSpacing : 0

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
              required property bool installed
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
                spacing: Style.space(12)
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter

                Metric { glyph: "󰓎"; value: row.starsText; active: row.hasCursor }
                Metric { glyph: "󰣐"; value: row.heartsText; active: row.hasCursor }
                Metric { glyph: "󰉉"; value: row.copiesText; active: row.hasCursor }

                Text {
                  visible: row.installed
                  textFormat: Text.PlainText
                  text: "󰄬"
                  color: row.hasCursor ? root.selectedText : root.foreground
                  opacity: row.hasCursor ? 0.92 : 0.38
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.iconSmall
                  verticalAlignment: Text.AlignVCenter
                }
              }

              Column {
                id: contentColumn
                anchors.left: iconText.right
                anchors.leftMargin: Style.space(6)
                anchors.right: metrics.left
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
              textFormat: Text.PlainText
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: root.catalogBusy
                ? "Updating catalog…"
                : (root.filterText ? ("No matches for “" + root.filterText + "”") : (root.statusText || "No plugins"))
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
