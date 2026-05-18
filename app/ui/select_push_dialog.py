"""Pre-push dialog: tree of campaigns/adsets/ads with checkboxes for selective push."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QCheckBox,
)

from app.models.campaign_data import CampaignData


_ID_ROLE = Qt.ItemDataRole.UserRole


class SelectPushDialog(QDialog):
    """
    Displays a checkable tree of campaigns → ad sets → ads (only those with FB IDs).
    The user unchecks items they don't want to push.

    Result is available via .selected_ids (set[str] of local object IDs).
    Returns None if the user cancelled.
    """

    def __init__(self, campaigns: list[CampaignData], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select What to Push")
        self.setMinimumSize(600, 550)
        self.setModal(True)

        self._campaigns = campaigns
        self.selected_ids: set[str] | None = None
        self.preview_only: bool = False

        self._setup_ui()
        self._populate(campaigns)

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(
                "Check the campaigns, ad sets, and ads you want to push to the API.\n"
                "Objects without a Facebook ID (not yet uploaded) are shown but cannot be pushed."
            )
        )

        # Select all / none row
        sel_row = QHBoxLayout()
        self.select_all_chk = QCheckBox("Select all")
        self.select_all_chk.setChecked(True)
        self.select_all_chk.toggled.connect(self._toggle_all)
        sel_row.addWidget(self.select_all_chk)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        sel_row.addStretch()
        sel_row.addWidget(self.count_label)
        layout.addLayout(sel_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Campaign / Ad Set / Ad")
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.preview_btn = QPushButton("Preview Push")
        self.preview_btn.setToolTip(
            "Validate changes against the API without making any updates."
        )
        self.preview_btn.clicked.connect(self._accept_preview)
        self.push_btn = QPushButton("Push Selected")
        self.push_btn.clicked.connect(self._accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.preview_btn)
        btn_row.addWidget(self.push_btn)
        layout.addLayout(btn_row)

    def _populate(self, campaigns: list[CampaignData]) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        for campaign in campaigns:
            camp_item = self._make_item(
                campaign.name or "(unnamed campaign)",
                campaign.id,
                has_fb_id=bool(campaign.fb_campaign_id),
                extra=campaign.fb_campaign_id or "no FB ID",
            )
            self.tree.addTopLevelItem(camp_item)
            for adset in campaign.ad_sets:
                adset_item = self._make_item(
                    adset.name or "(unnamed ad set)",
                    adset.id,
                    has_fb_id=bool(adset.fb_adset_id),
                    extra=adset.fb_adset_id or "no FB ID",
                )
                camp_item.addChild(adset_item)
                for ad in adset.ads:
                    ad_item = self._make_item(
                        ad.name or "(unnamed ad)",
                        ad.id,
                        has_fb_id=bool(ad.fb_ad_id),
                        extra=ad.fb_ad_id or "no FB ID",
                    )
                    adset_item.addChild(ad_item)
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self._update_count()

    def _make_item(
        self, label: str, local_id: str, has_fb_id: bool, extra: str
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"{label}  ({extra})"])
        item.setData(0, _ID_ROLE, local_id)
        if has_fb_id:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setForeground(0, item.foreground(0))  # keep default; greyed via color below
            item.setForeground(0, __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor("#666"))
        return item

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Cascade check state to children."""
        if column != 0:
            return
        state = item.checkState(0)
        self.tree.blockSignals(True)
        self._set_children_check(item, state)
        self.tree.blockSignals(False)
        self._update_count()

    def _set_children_check(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)
            self._set_children_check(child, state)

    def _toggle_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                top.setCheckState(0, state)
            self._set_children_check(top, state)
        self.tree.blockSignals(False)
        self._update_count()

    def _collect_checked(self) -> set[str]:
        ids: set[str] = set()

        def walk(item: QTreeWidgetItem) -> None:
            if (
                item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                and item.checkState(0) == Qt.CheckState.Checked
            ):
                ids.add(item.data(0, _ID_ROLE))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return ids

    def _update_count(self) -> None:
        ids = self._collect_checked()
        self.count_label.setText(f"{len(ids)} object(s) selected")

    def _accept(self) -> None:
        self.selected_ids = self._collect_checked()
        self.preview_only = False
        self.accept()

    def _accept_preview(self) -> None:
        self.selected_ids = self._collect_checked()
        self.preview_only = True
        self.accept()
