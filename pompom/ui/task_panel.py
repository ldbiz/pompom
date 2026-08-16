"""Task queue panel and task editing widgets."""

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..models.tasks import Task, TaskQueue
from ..settings import AppSettings
from .theme import PANEL_STYLE, paint_floating_panel
from .window_utils import (
    apply_window_behavior,
    init_floating_window,
    schedule_desktop_sync,
)


class _EntryLineEdit(QLineEdit):
    """Line edit that reports Escape so entry can be cancelled with the keyboard."""

    escaped = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.escaped.emit()
            return
        super().keyPressEvent(event)


class TaskEntryArea(QWidget):
    """Inline multi-row entry area shown inside the task panel."""

    finished = Signal()   # commit typed tasks
    cancelled = Signal()  # discard typed tasks (Esc / Cancel)
    geometry_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(4)
        self._edits: list[QLineEdit] = []

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._rows_container)
        self._scroll.setMaximumHeight(150)
        layout.addWidget(self._scroll)

        hint = QLabel("Enter for another line · Esc to cancel")
        hint.setStyleSheet("color: #7A5A5A; font-size: 10px;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self._on_done)
        btn_row.addWidget(done_btn)
        layout.addLayout(btn_row)

        self.hide()

    def reset(self) -> None:
        for edit in self._edits:
            edit.deleteLater()
        self._edits.clear()
        self._add_row()

    def show_and_focus(self) -> None:
        self.reset()
        self.show()
        self._focus_edit(self._edits[0])

    def _focus_edit(self, edit: QLineEdit) -> None:
        edit.setFocus()
        # The scroll area's size hint does not update the already-sized floating
        # panel when rows are added. Resize it explicitly, then reveal the edit
        # after both the entry and panel layouts have settled.
        QTimer.singleShot(0, lambda: self._reveal_edit(edit))

    def _reveal_edit(self, edit: QLineEdit) -> None:
        if edit not in self._edits:
            return
        self._rows_layout.activate()
        content_height = self._rows_layout.sizeHint().height()
        frame_height = self._scroll.frameWidth() * 2
        self._scroll.setFixedHeight(min(150, content_height + frame_height))
        self.updateGeometry()
        self.geometry_changed.emit()
        QTimer.singleShot(
            0, lambda: self._scroll.ensureWidgetVisible(edit, 0, 8)
        )

    def _add_row(self, text: str = "") -> QLineEdit:
        edit = _EntryLineEdit(text)
        edit.setPlaceholderText("Task description…")
        edit.returnPressed.connect(self._on_return_pressed)
        edit.escaped.connect(self._on_cancel)
        self._rows_layout.addWidget(edit)
        self._edits.append(edit)
        return edit

    def _on_return_pressed(self) -> None:
        edit = self.sender()
        if not isinstance(edit, QLineEdit):
            return
        idx = self._edits.index(edit)
        if idx == len(self._edits) - 1:
            self._focus_edit(self._add_row())
        else:
            self._focus_edit(self._edits[idx + 1])

    def titles(self) -> list[str]:
        return [e.text().strip() for e in self._edits if e.text().strip()]

    def _on_done(self) -> None:
        self.finished.emit()

    def _on_cancel(self) -> None:
        self.cancelled.emit()


class TaskEditDialog(QDialog):
    """Small dialog to edit a task's title."""

    def __init__(self, task: Task, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Task")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self._title_edit = QLineEdit(task.title)
        self._title_edit.textChanged.connect(self._on_text_changed)
        layout.addRow("Title:", self._title_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setEnabled(bool(task.title.strip()))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)
        self.adjustSize()

    def _on_text_changed(self, text: str) -> None:
        self._ok_btn.setEnabled(bool(text.strip()))

    @property
    def title(self) -> str:
        return self._title_edit.text().strip()


class TaskItemWidget(QWidget):
    """Row widget for a single task in the task list."""

    toggled = Signal(int, bool)   # (index, done)
    edit_requested = Signal(int)  # (index,)
    remove_requested = Signal(int)

    def __init__(self, task: Task, index: int, is_current: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._index = index

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        self._check = QCheckBox()
        self._check.setChecked(task.done)
        self._check.toggled.connect(lambda checked: self.toggled.emit(self._index, checked))
        layout.addWidget(self._check)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        title_label = QLabel()
        title_label.setToolTip(task.title or "(untitled)")
        fm = QFontMetrics(title_label.font())
        display = task.title or "(untitled)"
        elided = fm.elidedText(display, Qt.TextElideMode.ElideRight, 140)
        title_label.setText(elided)
        title_label.setStyleSheet(
            "color: #DDD0D0; font-weight: 600;"
            if is_current else
            "color: #B0A0A0;"
        )
        if task.done:
            title_label.setStyleSheet(
                title_label.styleSheet() + " text-decoration: line-through; color: #706060;"
            )
        text_col.addWidget(title_label)

        layout.addLayout(text_col)
        layout.addStretch()

        # Icon-only row actions: readable glyphs, zero padding so the shared
        # panel stylesheet doesn't crush them inside the button.
        icon_btn_style = (
            "QPushButton { padding: 0; font-size: 13px; min-width: 0; }"
        )

        edit_btn = QPushButton("✎")
        edit_btn.setFixedSize(22, 22)
        edit_btn.setStyleSheet(icon_btn_style)
        edit_btn.setToolTip("Edit")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._index))
        layout.addWidget(edit_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 22)
        del_btn.setStyleSheet(icon_btn_style)
        del_btn.setToolTip("Remove")
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self._index))
        layout.addWidget(del_btn)


class TaskPanel(QWidget):
    """Floating task queue panel; appears alongside the main timer widget."""

    task_changed = Signal()   # emitted whenever the queue is mutated
    closed = Signal()         # emitted when the user dismisses the panel
    user_moved = Signal()     # emitted when the user drags the panel

    def __init__(
        self,
        task_queue: TaskQueue,
        settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tq = task_queue
        self._settings = settings
        self.setObjectName("TaskPanel")

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        init_floating_window(self, always_on_top=settings.always_on_top())
        self.setFixedWidth(230)
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        # Inner opaque container so children paint correctly
        self._inner = QWidget(self)
        self._inner.setObjectName("TaskPanel")
        self._inner.setStyleSheet("QWidget#TaskPanel { background: #1E1010; border-radius: 10px; }")
        inner_layout = QVBoxLayout(self._inner)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(6)
        outer.addWidget(self._inner)

        # Title row
        title_row = QHBoxLayout()
        lbl = QLabel("Tasks")
        lbl.setObjectName("header")
        lbl.setStyleSheet("QLabel { color: #9A7070; font-size: 12px; font-weight: 500; background: transparent; }")
        title_row.addWidget(lbl)
        title_row.addStretch()

        self._shuffle_btn = QPushButton("⇄ Shuffle")
        self._shuffle_btn.setCheckable(True)
        self._shuffle_btn.setChecked(task_queue.shuffle_mode)
        self._shuffle_btn.setFixedHeight(20)
        self._shuffle_btn.toggled.connect(self._toggle_shuffle)
        title_row.addWidget(self._shuffle_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("QPushButton { padding: 0; }")
        close_btn.clicked.connect(self._dismiss)
        title_row.addWidget(close_btn)
        inner_layout.addLayout(title_row)

        # Task list
        self._list = QListWidget()
        self._list.setSpacing(1)
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner_layout.addWidget(self._list)

        self._empty_label = QLabel("No tasks yet — click + Add")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #7A5A5A; font-size: 10px; padding: 12px 4px;")
        self._empty_label.setWordWrap(True)
        inner_layout.addWidget(self._empty_label)

        self._entry_area = TaskEntryArea(self._inner)
        self._entry_area.finished.connect(self._finish_entry)
        self._entry_area.cancelled.connect(self._cancel_entry)
        self._entry_area.geometry_changed.connect(self._resize_for_entry)
        inner_layout.addWidget(self._entry_area)

        self._add_btn = QPushButton("+ Add")
        self._add_btn.clicked.connect(self._start_entry)

        self._clear_done_btn = QPushButton("Delete completed tasks")
        self._clear_done_btn.clicked.connect(self._delete_completed)

        ctrl_col = QVBoxLayout()
        ctrl_col.setSpacing(4)
        ctrl_col.addWidget(self._add_btn)
        ctrl_col.addWidget(self._clear_done_btn)
        inner_layout.addLayout(ctrl_col)

        self._refresh_list()

        # Drag support
        self._dragging = False
        self._drag_offset = QPoint()

    def apply_window_behavior(self) -> None:
        """Apply always-on-top / virtual-desktop settings."""
        apply_window_behavior(
            self,
            always_on_top=self._settings.always_on_top(),
            show_on_all_desktops=self._settings.show_on_all_desktops(),
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        schedule_desktop_sync(
            self, show_on_all_desktops=self._settings.show_on_all_desktops()
        )

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        paint_floating_panel(painter, QRectF(self.rect()))

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_dragging = self._dragging
        self._dragging = False
        if was_dragging:
            self.user_moved.emit()
        event.accept()

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_list()

    def _dismiss(self) -> None:
        self.closed.emit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        self._list.clear()
        has_tasks = bool(self._tq.tasks)
        self._list.setVisible(has_tasks)
        self._empty_label.setVisible(not has_tasks)
        for i, task in enumerate(self._tq.tasks):
            item = QListWidgetItem(self._list)
            w = TaskItemWidget(task, i, i == self._tq.current_index)
            w.toggled.connect(self._on_task_toggled)
            w.edit_requested.connect(self._on_edit_task)
            w.remove_requested.connect(self._on_remove_task)
            item.setSizeHint(w.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, w)
        # Adjust height to content, capped at 300 px
        if has_tasks:
            row_h = self._list.sizeHintForRow(0) if self._tq.tasks else 0
            row_h = row_h if row_h > 0 else 32
            self._list.setFixedHeight(min(300, max(60, len(self._tq.tasks) * (row_h + 3) + 8)))
        else:
            self._list.setFixedHeight(0)
        self._clear_done_btn.setEnabled(any(t.done for t in self._tq.tasks))
        self.adjustSize()
        self._clamp_to_screen()

    def _toggle_shuffle(self, checked: bool) -> None:
        self._tq.shuffle_mode = checked
        self.task_changed.emit()

    def _start_entry(self) -> None:
        self._add_btn.hide()
        self._entry_area.show_and_focus()
        self.adjustSize()
        self._clamp_to_screen()

    def _resize_for_entry(self) -> None:
        """Keep the active entry viewport inside the resized floating panel."""
        self.adjustSize()
        self._clamp_to_screen()

    def _finish_entry(self) -> None:
        titles = self._entry_area.titles()
        self._entry_area.hide()
        self._add_btn.show()
        if titles:
            for title in titles:
                self._tq.add(Task(title=title))
            self._refresh_list()
            self.task_changed.emit()
        self.adjustSize()
        self._clamp_to_screen()

    def _cancel_entry(self) -> None:
        self._entry_area.hide()
        self._add_btn.show()
        self.adjustSize()
        self._clamp_to_screen()

    def _clamp_to_screen(self) -> None:
        """Keep the whole panel within the visible screen after it resizes."""
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        geo = self.frameGeometry()
        x, y = geo.x(), geo.y()
        if geo.right() > avail.right():
            x = avail.right() - geo.width()
        if x < avail.left():
            x = avail.left()
        if geo.bottom() > avail.bottom():
            y = avail.bottom() - geo.height()
        if y < avail.top():
            y = avail.top()
        if (x, y) != (geo.x(), geo.y()):
            self.move(x, y)

    def _delete_completed(self) -> None:
        if self._tq.remove_completed():
            self._refresh_list()
            self.task_changed.emit()

    def _on_task_toggled(self, index: int, done: bool) -> None:
        if 0 <= index < len(self._tq.tasks):
            self._tq.tasks[index].done = done
            self._refresh_list()
            self.task_changed.emit()

    def _on_edit_task(self, index: int) -> None:
        if not (0 <= index < len(self._tq.tasks)):
            return
        task = self._tq.tasks[index]
        dlg = TaskEditDialog(task=task, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task.title = dlg.title
            self._refresh_list()
            self.task_changed.emit()

    def _on_remove_task(self, index: int) -> None:
        self._tq.remove(index)
        self._refresh_list()
        self.task_changed.emit()

