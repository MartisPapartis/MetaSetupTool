"""Mixin for the Promoted Object form section shared by campaign and ad set editors."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox

from app.models.enums import PixelEvent


class _PromotedObjectMixin:
    """Provides helpers for the Promoted Object UI section.

    The host widget must already have these attributes set up in its ``_setup_ui``:
      ``pixel_id_combo``, ``pixel_event_combo``, ``custom_event_name_edit``,
      ``app_id_combo``, ``object_store_url_edit``
    """

    # ── static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _set_combo_by_id(combo: QComboBox, id_value: str) -> None:
        """Select the item whose stored data matches id_value, or fall back to typed text."""
        if not id_value:
            combo.setCurrentIndex(0)
            return
        for i in range(combo.count()):
            if combo.itemData(i) == id_value:
                combo.setCurrentIndex(i)
                return
        combo.setCurrentText(id_value)

    @staticmethod
    def _get_combo_id(combo: QComboBox) -> str:
        """Return the stored ID from combo data, falling back to typed text."""
        data = combo.currentData()
        if data:
            return str(data)
        return combo.currentText().strip()

    # ── slot ──────────────────────────────────────────────────────────────────

    def _on_pixel_event_changed(self, _index: int) -> None:
        is_other = self.pixel_event_combo.currentData() == PixelEvent.OTHER.value
        self.custom_event_name_edit.setVisible(is_other)

    # ── populate resource dropdowns ───────────────────────────────────────────

    def _repopulate_promo_combos(
        self,
        pixels: list[dict],
        apps: list[dict],
        *,
        current_pixel: str = "",
        current_app: str = "",
    ) -> None:
        """Rebuild pixel and app combos, preserving the current selection."""
        self.pixel_id_combo.clear()
        self.pixel_id_combo.addItem("", "")
        for p in pixels:
            label = f"{p['name']}  ({p['id']})" if p.get("name") else p["id"]
            self.pixel_id_combo.addItem(label, p["id"])
        self._set_combo_by_id(self.pixel_id_combo, current_pixel)

        self.app_id_combo.clear()
        self.app_id_combo.addItem("", "")
        for a in apps:
            label = f"{a['name']}  ({a['id']})" if a.get("name") else a["id"]
            self.app_id_combo.addItem(label, a["id"])
        self._set_combo_by_id(self.app_id_combo, current_app)

    # ── load / commit ─────────────────────────────────────────────────────────

    def _load_promo_fields(self, promo: dict) -> None:
        """Populate the promoted-object widgets from a promo dict."""
        self._set_combo_by_id(self.pixel_id_combo, promo.get("pixel_id", ""))
        event_val = promo.get("custom_event_type", "")
        idx = self.pixel_event_combo.findData(event_val)
        self.pixel_event_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.custom_event_name_edit.setText(promo.get("custom_event_str", ""))
        self.custom_event_name_edit.setVisible(event_val == PixelEvent.OTHER.value)
        self._set_combo_by_id(self.app_id_combo, promo.get("application_id", ""))
        self.object_store_url_edit.setText(promo.get("object_store_url", ""))

    def _commit_promo_fields(self) -> dict:
        """Read promoted-object widgets and return a payload dict (omits empty fields)."""
        promo: dict = {}
        pixel_id = self._get_combo_id(self.pixel_id_combo)
        event_val = self.pixel_event_combo.currentData()
        app_id = self._get_combo_id(self.app_id_combo)
        store_url = self.object_store_url_edit.text().strip()
        if pixel_id:
            promo["pixel_id"] = pixel_id
        if event_val:
            promo["custom_event_type"] = event_val
            if event_val == PixelEvent.OTHER.value:
                custom_name = self.custom_event_name_edit.text().strip()
                if custom_name:
                    promo["custom_event_str"] = custom_name
        if app_id:
            promo["application_id"] = app_id
        if store_url:
            promo["object_store_url"] = store_url
        return promo
