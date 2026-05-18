"""Campaign hierarchy tree widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
)

from app.models.campaign_data import SessionData, CampaignData, AdSetData, AdData

# Custom roles
_ID_ROLE = Qt.ItemDataRole.UserRole
_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1

NODE_CAMPAIGN = "campaign"
NODE_ADSET = "adset"
NODE_AD = "ad"


def _make_item(label: str, node_type: str, node_id: str) -> QTreeWidgetItem:
    item = QTreeWidgetItem([label])
    item.setData(0, _ID_ROLE, node_id)
    item.setData(0, _TYPE_ROLE, node_type)
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
    return item


class CampaignTreeWidget(QTreeWidget):
    node_renamed = pyqtSignal(str, str, str)  # node_type, node_id, new_name
    # node_type, node_id, old_parent_id, new_parent_id, new_index
    node_moved = pyqtSignal(str, str, str, str, int)

    action_add_campaign = pyqtSignal()
    action_add_adset = pyqtSignal()
    action_add_ad = pyqtSignal()
    action_duplicate = pyqtSignal()
    action_remove = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Structure")
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemChanged.connect(self._on_item_changed)
        self._ignore_change = False
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._dragged_item: QTreeWidgetItem | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_session(self, session: SessionData) -> None:
        self._ignore_change = True
        self.clear()
        for campaign in session.campaigns:
            camp_item = self._add_campaign_item(campaign)
            for adset in campaign.ad_sets:
                adset_item = self._add_adset_item(camp_item, adset)
                for ad in adset.ads:
                    self._add_ad_item(adset_item, ad)
        self.expandAll()
        self._ignore_change = False

    def add_campaign(self, campaign: CampaignData) -> QTreeWidgetItem:
        self._ignore_change = True
        item = self._add_campaign_item(campaign)
        self.expandAll()
        self._ignore_change = False
        return item

    def add_adset(
        self, parent_campaign_id: str, adset: AdSetData
    ) -> QTreeWidgetItem | None:
        camp_item = self._find_item(parent_campaign_id)
        if camp_item is None:
            return None
        self._ignore_change = True
        item = self._add_adset_item(camp_item, adset)
        camp_item.setExpanded(True)
        self._ignore_change = False
        return item

    def add_ad(self, parent_adset_id: str, ad: AdData) -> QTreeWidgetItem | None:
        adset_item = self._find_item(parent_adset_id)
        if adset_item is None:
            return None
        self._ignore_change = True
        item = self._add_ad_item(adset_item, ad)
        adset_item.setExpanded(True)
        self._ignore_change = False
        return item

    def remove_selected(self) -> tuple[str, str] | None:
        """Remove the currently selected item. Returns (node_type, node_id) or None."""
        item = self.currentItem()
        if item is None:
            return None
        node_type = item.data(0, _TYPE_ROLE)
        node_id = item.data(0, _ID_ROLE)
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            idx = self.indexOfTopLevelItem(item)
            self.takeTopLevelItem(idx)
        return node_type, node_id

    def select_by_id(self, node_id: str) -> None:
        item = self._find_item(node_id)
        if item:
            self.setCurrentItem(item)

    def get_selected_items(self) -> list[tuple[str, str]]:
        """Return list of (node_type, node_id) for all selected items."""
        return [
            (item.data(0, _TYPE_ROLE), item.data(0, _ID_ROLE))
            for item in self.selectedItems()
        ]

    def get_selected_items_with_context(self) -> list[tuple[str, str, str, str]]:
        """Return (node_type, node_id, camp_id, adset_id) for each selected item."""
        result = []
        for item in self.selectedItems():
            node_type = item.data(0, _TYPE_ROLE)
            node_id = item.data(0, _ID_ROLE)
            if node_type == NODE_CAMPAIGN:
                result.append((node_type, node_id, node_id, ""))
            elif node_type == NODE_ADSET:
                parent = item.parent()
                camp_id = parent.data(0, _ID_ROLE) if parent else ""
                result.append((node_type, node_id, camp_id, ""))
            elif node_type == NODE_AD:
                adset_item = item.parent()
                camp_item = adset_item.parent() if adset_item else None
                adset_id = adset_item.data(0, _ID_ROLE) if adset_item else ""
                camp_id = camp_item.data(0, _ID_ROLE) if camp_item else ""
                result.append((node_type, node_id, camp_id, adset_id))
        return result

    def get_selected_ids(self) -> tuple[str, str, str]:
        """Return (campaign_id, adset_id, ad_id) for the currently selected item."""
        item = self.currentItem()
        if item is None:
            return "", "", ""
        node_type = item.data(0, _TYPE_ROLE)
        node_id = item.data(0, _ID_ROLE)

        if node_type == NODE_CAMPAIGN:
            return node_id, "", ""
        if node_type == NODE_ADSET:
            parent = item.parent()
            camp_id = parent.data(0, _ID_ROLE) if parent else ""
            return camp_id, node_id, ""
        if node_type == NODE_AD:
            adset_item = item.parent()
            camp_item = adset_item.parent() if adset_item else None
            adset_id = adset_item.data(0, _ID_ROLE) if adset_item else ""
            camp_id = camp_item.data(0, _ID_ROLE) if camp_item else ""
            return camp_id, adset_id, node_id
        return "", "", ""

    def update_item_label(self, node_id: str, new_label: str) -> None:
        item = self._find_item(node_id)
        if item:
            self._ignore_change = True
            item.setText(0, new_label)
            self._ignore_change = False

    # ------------------------------------------------------------------
    # Search / filter
    # ------------------------------------------------------------------

    def filter(self, query: str) -> None:
        """Show only nodes whose name contains *query* (case-insensitive).
        Parent nodes are shown whenever any descendant matches.
        Clears the filter (shows everything) when *query* is empty."""
        q = query.strip().lower()
        self._ignore_change = True
        for i in range(self.topLevelItemCount()):
            self._apply_filter(self.topLevelItem(i), q)
        self._ignore_change = False

    def _apply_filter(self, item: QTreeWidgetItem, query: str) -> bool:
        matches = not query or query in item.text(0).lower()
        any_child_visible = False
        for i in range(item.childCount()):
            if self._apply_filter(item.child(i), query):
                any_child_visible = True
        visible = matches or any_child_visible
        item.setHidden(not visible)
        if visible:
            item.setExpanded(True)
        return visible

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def startDrag(self, supported_actions) -> None:  # pylint: disable=invalid-name
        """Capture the item being dragged before Qt loses track of it."""
        self._dragged_item = self.currentItem()
        super().startDrag(supported_actions)
        self._dragged_item = None

    def _effective_drop_parent(self, event) -> QTreeWidgetItem | None:
        """Return the item that will become the new parent after this drop.

        dropIndicatorPosition() is only reliable after super() has processed the
        event, so we compute the position manually from the mouse coordinates.
        """
        pt = event.position().toPoint()
        drop_item = self.itemAt(pt)
        if drop_item is None:
            return None
        rect = self.visualItemRect(drop_item)
        margin = max(2, rect.height() // 4)
        if pt.y() < rect.top() + margin or pt.y() > rect.bottom() - margin:
            # Cursor is near the top/bottom edge — drop will land beside the item,
            # making its parent the new parent.
            return drop_item.parent()
        # Cursor is on the item itself.
        return drop_item

    def _drop_is_valid(self, dragged: QTreeWidgetItem, event) -> bool:
        node_type = dragged.data(0, _TYPE_ROLE)
        effective_parent = self._effective_drop_parent(event)
        if effective_parent is None:
            return False
        parent_type = effective_parent.data(0, _TYPE_ROLE)
        if node_type == NODE_ADSET:
            return parent_type == NODE_CAMPAIGN
        if node_type == NODE_AD:
            return parent_type == NODE_ADSET
        return False

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # pylint: disable=invalid-name
        dragged = self._dragged_item
        if dragged is None or not self._drop_is_valid(dragged, event):
            event.ignore()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # pylint: disable=invalid-name
        dragged = self._dragged_item
        if dragged is None or not self._drop_is_valid(dragged, event):
            event.ignore()
            return

        node_type = dragged.data(0, _TYPE_ROLE)
        node_id = dragged.data(0, _ID_ROLE)
        old_parent = dragged.parent()
        old_parent_id = old_parent.data(0, _ID_ROLE) if old_parent else ""

        super().dropEvent(event)

        new_parent = dragged.parent()
        new_parent_id = new_parent.data(0, _ID_ROLE) if new_parent else ""
        new_index = new_parent.indexOfChild(dragged) if new_parent else 0

        self.node_moved.emit(node_type, node_id, old_parent_id, new_parent_id, new_index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_campaign_item(self, campaign: CampaignData) -> QTreeWidgetItem:
        item = _make_item(
            campaign.name or "(unnamed campaign)", NODE_CAMPAIGN, campaign.id
        )
        self.addTopLevelItem(item)
        return item

    def _add_adset_item(
        self, parent: QTreeWidgetItem, adset: AdSetData
    ) -> QTreeWidgetItem:
        item = _make_item(adset.name or "(unnamed ad set)", NODE_ADSET, adset.id)
        parent.addChild(item)
        return item

    def _add_ad_item(self, parent: QTreeWidgetItem, ad: AdData) -> QTreeWidgetItem:
        item = _make_item(ad.name or "(unnamed ad)", NODE_AD, ad.id)
        parent.addChild(item)
        return item

    def _find_item(self, node_id: str) -> QTreeWidgetItem | None:
        def search(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            if item.data(0, _ID_ROLE) == node_id:
                return item
            for i in range(item.childCount()):
                result = search(item.child(i))
                if result:
                    return result
            return None

        for i in range(self.topLevelItemCount()):
            result = search(self.topLevelItem(i))
            if result:
                return result
        return None

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._ignore_change or column != 0:
            return
        node_type = item.data(0, _TYPE_ROLE)
        node_id = item.data(0, _ID_ROLE)
        new_name = item.text(0)
        self.node_renamed.emit(node_type, node_id, new_name)

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        menu = QMenu(self)
        if item is None:
            menu.addAction("Add Campaign").triggered.connect(self.action_add_campaign)
        else:
            # If the right-clicked item isn't already selected, replace the selection
            if item not in self.selectedItems():
                self.clearSelection()
                self.setCurrentItem(item)

            selected = self.selectedItems()
            node_type = item.data(0, _TYPE_ROLE)

            # "Add child" actions only apply to a single item
            if len(selected) == 1:
                if node_type == NODE_CAMPAIGN:
                    menu.addAction("Add Ad Set").triggered.connect(self.action_add_adset)
                elif node_type == NODE_ADSET:
                    menu.addAction("Add Ad").triggered.connect(self.action_add_ad)

            menu.addAction("Duplicate").triggered.connect(self.action_duplicate)
            menu.addSeparator()
            count = len(selected)
            remove_label = f"Remove {count} items" if count > 1 else "Remove"
            menu.addAction(remove_label).triggered.connect(self.action_remove)
        menu.exec(self.viewport().mapToGlobal(pos))
