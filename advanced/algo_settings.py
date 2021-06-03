#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from functools import partial
from collections import OrderedDict, defaultdict
import re
import traceback
import copy
import json

# python3 compatibility
from six.moves import range
from six import text_type as unicode, string_types as basestring

try:
    from PyQt5.Qt import (Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel,
                          QToolButton, QDialog, QDialogButtonBox, QComboBox, QLineEdit,
                          QCheckBox, QSpinBox, QDoubleSpinBox, QSizePolicy, QIcon)

except ImportError:
    from PyQt4.Qt import (Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel,
                          QToolButton, QDialog, QDialogButtonBox, QComboBox, QLineEdit,
                          QCheckBox, QSpinBox, QDoubleSpinBox, QSizePolicy, QIcon)

from calibre import prints
from calibre_plugins.find_duplicates.common_utils import get_icon

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/algos_settings.py - exception when loading translations")
    pass

#=================
# Settings Widgets
#=================

class SettingsSpin(QWidget):
    def __init__(self, name, value, range_=None, label=None, step=1):
        QWidget.__init__(self)
        self.name = name
        if not label:
            label = name
        layout = QHBoxLayout()
        self.setLayout(layout)
        lbl = QLabel('{}: '.format(label), self)
        self.spin = QSpinBox(self)
        if range_:
            minimum, maximum = range_
            self.spin.setMinimum(minimum)
            self.spin.setMaximum(maximum)
        #self.spin.setSingleStep(step)
        self.spin.setValue(value)
        layout.addWidget(lbl)
        layout.addWidget(self.spin)

    def get_setting(self):
        value = int(unicode(self.spin.value()))
        return self.name, value

class SettingsDSpin(QWidget):
    def __init__(self, name, value, range_=None, label=None, step=1):
        QWidget.__init__(self)
        self.name = name
        if not label:
            label = name
        layout = QHBoxLayout()
        self.setLayout(layout)
        lbl = QLabel('{}: '.format(label), self)
        self.spin = QDoubleSpinBox(self)
        if range_:
            minimum, maximum = range_
            self.spin.setMinimum(minimum)
            self.spin.setMaximum(maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        layout.addWidget(lbl)
        layout.addWidget(self.spin)

    def get_setting(self):
        value = float(unicode(self.spin.value()))
        return self.name, value

class SettingsCheck(QWidget):
    def __init__(self, name, value, label=None):
        QWidget.__init__(self)
        self.name = name
        if not label:
            label = name
        layout = QHBoxLayout()
        self.setLayout(layout)
        self.check = QCheckBox(label)
        self.check.setChecked(value)
        layout.addWidget(self.check)

    def get_setting(self):
        value = self.check.isChecked()
        return self.name, value

class SettingsLine(QWidget):
    def __init__(self, name, value, label=None):
        QWidget.__init__(self)
        self.name = name
        if not label:
            label = name
        layout = QHBoxLayout()
        self.setLayout(layout)
        lbl = QLabel('{}: '.format(label), self)
        self.ledit = QLineEdit(self)
        self.ledit.setText(value)
        layout.addWidget(lbl)
        layout.addWidget(self.ledit)

    def get_setting(self):
        value = self.ledit.text()
        return self.name, value

class SettingsCombo(QWidget):
    def __init__(self, name, value, items, label=None):
        QWidget.__init__(self)
        self.name = name
        if not label:
            label = name
        layout = QHBoxLayout()
        self.setLayout(layout)
        lbl = QLabel('{}: '.format(label), self)
        self.combo = QComboBox(self)
        self.combo.addItems(items)
        self.combo.setCurrentIndex(-1)
        if value:
            self.combo.setCurrentText(value)
        layout.addWidget(lbl)
        layout.addWidget(self.combo)

    def get_setting(self):
        value = self.combo.currentText()
        return self.name, value

class SettingsButton(QToolButton):
    def __init__(self, lookup_key, settings_metadata, settings_cache):
        QToolButton.__init__(self)
        self.settings_metadata = settings_metadata
        self.lookup_key = lookup_key
        self.settings_cache = settings_cache
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setMaximumWidth(30)
        self.setIcon(get_icon('gear.png'))
        self.setToolTip(_('Change algorithms settings'))
        self.clicked.connect(self._clicked)
    
    def _clicked(self):
        d = SettingsDialog(self, self.settings_metadata)
        if d.exec_() == d.Accepted:
            self.settings_cache[self.lookup_key] = d.settings

#=====================

class SettingsDialog(QDialog):
    def __init__(self, parent, settings):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Settings'))
        self.build_dialog(settings)

    def build_dialog(self, settings):
        l =  QGridLayout()
        self.setLayout(l)
        self.controls_layout = QVBoxLayout()
        l.addLayout(self.controls_layout, 0, 0, 1, 1)
        for setting in settings:
            typ = setting['type']
            name = setting['name']
            if not re.match(r'^[a-zA-Z0-9_]+$', name):
                raise ValueError(_('Name must contain only letters, numbers, undersocres'))
            value = setting['value']
            range_ = setting.get('range')
            label = setting.get('label')
            if typ == 'int':
                if not range_[0] < value < range_[1]:
                    raise ValueError(_('Value for SettingSpin must be between {} and {}').format(range_[0], range_[1]))
                widget = SettingsSpin(name, value, range_, label)
            elif typ == 'float':
                if not range_[0] < value < range_[1]:
                    raise ValueError(_('Value for SettingSpin must be between {} and {}').format(range_[0], range_[1]))
                widget = SettingsDSpin(name, value, range_, label)
            elif typ == 'bool':
                if not isinstance(value, bool):
                    raise ValueError(_('Value for SettingCheck must be of type bool'))
                widget = SettingsCheck(name, value, label)
            elif typ == 'str':
                widget = SettingsLine(name, value, label)
            elif typ == 'enum':
                if value:
                    if value not in range_:
                        raise ValueError(_('Value for SettingCombo must be in {}').format(range_))
                widget = SettingsCombo(name, value, range_, label)
            self.controls_layout.addWidget(widget)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        l.addWidget(self.button_box, 1, 0, 1, 1)

    def get_settings(self):
        settings = {}
        for idx in range(self.controls_layout.count()):
            widget = self.controls_layout.itemAt(idx).widget()
            name, val = widget.get_setting()
            settings[name] = val
        return settings

    def _accept_clicked(self):
        self.settings = self.get_settings()
        self.accept()
