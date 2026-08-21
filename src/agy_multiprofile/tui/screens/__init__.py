"""
TUI screens package.
"""

from agy_multiprofile.tui.screens.backups_screen import BackupsModal
from agy_multiprofile.tui.screens.doctor_screen import DoctorModal
from agy_multiprofile.tui.screens.help_screen import HelpModal
from agy_multiprofile.tui.screens.modals import (
    CloneProfileModal,
    ConfirmActionModal,
    CreateProfileModal,
    RenameProfileModal,
    SwitchConfirmModal,
)
from agy_multiprofile.tui.screens.trash_screen import TrashModal

__all__ = [
    "CreateProfileModal",
    "SwitchConfirmModal",
    "CloneProfileModal",
    "RenameProfileModal",
    "ConfirmActionModal",
    "BackupsModal",
    "TrashModal",
    "DoctorModal",
    "HelpModal",
]
