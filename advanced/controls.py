#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from functools import partial
from collections import OrderedDict, defaultdict
import copy
from uuid import uuid4

# python3 compatibility
from six.moves import range
from six import text_type as unicode, string_types as basestring

try:
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (QApplication, Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
                          QLabel, QGroupBox, QToolButton, QPushButton, QScrollArea, QComboBox,
                          QDialog, QDialogButtonBox, QTableWidget, QAbstractItemView, QCheckBox,
                          QIcon, QSizePolicy, pyqtSignal, QSize)

except ImportError:
    from PyQt4 import QtGui
    from PyQt4.Qt import (QApplication, Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
                          QLabel, QGroupBox, QToolButton, QPushButton, QScrollArea, QComboBox,
                          QDialog, QDialogButtonBox, QTableWidget, QAbstractItemView, QCheckBox,
                          QIcon, QSizePolicy, pyqtSignal, QSize)

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog

from calibre_plugins.find_duplicates.common_utils import (
        SizePersistedDialog, ReadOnlyTableWidgetItem, get_icon,
)
from calibre_plugins.find_duplicates.advanced.algorithms import _all_algorithms
from calibre_plugins.find_duplicates.advanced.common import truncate
from calibre_plugins.find_duplicates.advanced.templates import TemplateBox, TemplateSettingsButton, TEMPLATE_PREFIX, TEMPLATE_ERROR
from calibre_plugins.find_duplicates.advanced.algo_settings import SettingsButton
from calibre_plugins.find_duplicates.advanced.sort import SortDialog

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/contorls.py - exception when loading translations")
    pass

class AlgorithmTable(QTableWidget):
    def __init__(self, parent, header_labels, hidden_cols, sortable=True):
        QTableWidget.__init__(self, parent)
        self.header_labels = header_labels
        self.hidden_cols = hidden_cols
        self.setSortingEnabled(sortable)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setDefaultSectionSize(self.verticalHeader().minimumSectionSize())
        self.settings_cache = parent.settings_cache
        parent_dialog = parent.parent_dialog
        self.gui = parent_dialog.gui
        self.db = parent_dialog.db
        try:
            self.target_db = getattr(parent_dialog, 'target_db')
        except AttributeError:
            self.target_db = None

    def populate_table(self, tbl_rows):
        self.clear()
        self.setRowCount(len(tbl_rows))
        if not hasattr(self, 'header_labels'):
            self.header_labels = [str(col) for col in range(1, len(tbl_rows[0])+1)]
        self.setColumnCount(len(self.header_labels))
        self.setHorizontalHeaderLabels(self.header_labels)
        self.horizontalHeader().setStretchLastSection(True)

        # populate rows
        for row_idx, tbl_row in enumerate(tbl_rows):
            self.populate_table_row(row_idx, tbl_row)

        # apply tooltips
        algo_col = self.header_labels.index(_('Name'))
        for row in range(self.rowCount()):
            table_item = self.item(row, algo_col)
            algo = table_item.text()
            if algo.startswith(TEMPLATE_PREFIX):
                tooltip = algo.lstrip(TEMPLATE_PREFIX)
            else:
                tooltip = _all_algorithms[algo].get('description', '')
            if tooltip:
                table_item.setToolTip(tooltip)
            
        # hide columns
        for col in self.hidden_cols:
            idx = self.header_labels.index(col)
            self.setColumnHidden(idx, True)

        self.resizeColumnsToContents()

    def populate_table_row(self, row, tbl_row):
        for col, col_data in enumerate(tbl_row):
            if isinstance(col_data, basestring):
                col_data = ReadOnlyTableWidgetItem(col_data)
            self.setItem(row, col, col_data)
        if _('Settings') in self.header_labels:
            self.add_settings_button(row)

    def remove_row(self):
        rows = sorted(self.selectionModel().selectedRows())
        for selrow in reversed(rows):
            self.removeRow(selrow.row())

    def take_rows(self):
        rows = sorted(self.selectionModel().selectedRows())
        for row in rows:
            yield [ self.takeItem(row.row(), column) for column in range(self.columnCount()) ]

    def add_row(self, tbl_row):
        sortable = self.isSortingEnabled()
        try:
            self.setSortingEnabled(False)
            row_idx = self.rowCount()
            self.insertRow(row_idx)
            self.populate_table_row(row_idx, tbl_row)
        finally:
            self.setSortingEnabled(sortable)

    def move_rows_up(self):
        rows = sorted(self.selectionModel().selectedRows())
        for selrow in rows:
            old_idx = selrow.row()
            if old_idx > 0:
                new_idx = old_idx - 1
                tbl_row = [ self.takeItem(old_idx, column) for column in range(self.columnCount()) ]
                # delete before inserting to idx change
                self.removeRow(old_idx)
                self.insertRow(new_idx)
                self.populate_table_row(new_idx, tbl_row)
                self.setCurrentItem(self.item(new_idx,0))

    def move_rows_down(self):
        rows = sorted(self.selectionModel().selectedRows())
        for selrow in rows:
            old_idx = selrow.row()
            if old_idx < (self.rowCount() - 1):
                new_idx = old_idx + 1
                tbl_row = [ self.takeItem(old_idx, column) for column in range(self.columnCount()) ]
                # delete before inserting to idx change
                self.removeRow(old_idx)
                self.insertRow(new_idx)
                self.populate_table_row(new_idx, tbl_row)
                self.setCurrentItem(self.item(new_idx,0))

    def add_settings_button(self, row):
        settings_col = self.header_labels.index(_('Settings'))
        algo_col = self.header_labels.index(_('Name'))
        lookup_col = self.header_labels.index('lookup_key')
        table_item = self.item(row, algo_col)
        algorithm = table_item.text()
        lookup_key = self.item(row, lookup_col).text()
        if algorithm.startswith(TEMPLATE_PREFIX):
            settings_button = TemplateSettingsButton(table_item, self.gui, self.db, self.target_db)
            self.setCellWidget(row, settings_col, settings_button)
        else:
            settings_metadata = copy.deepcopy(_all_algorithms[algorithm].get('settings_metadata'))
            settings = self.settings_cache[lookup_key]
            if settings_metadata:
                for item in settings_metadata:
                    value = settings.get(item['name'])
                    if value:
                        item['value'] = value
                settings_button = SettingsButton(lookup_key, settings_metadata, self.settings_cache)
                self.setCellWidget(row, settings_col, settings_button)
                self.resizeColumnsToContents()

class AlgorithmDialog(SizePersistedDialog):
    def __init__(self, parent_dialog, chosen_algos=[]):
        SizePersistedDialog.__init__(self, parent_dialog, 'Find Duplicates plugin:algorithm dialog')
        self.settings_cache = defaultdict(dict)
        self.chosen_rows = self.algos_to_rows(chosen_algos)
        self.avail_tbl_header_labels = [_('Name')]
        self.chosen_tbl_header_labels = ['lookup_key', _('Name'),_('Settings')]
        self.avail_tbl_hidden_cols = []
        self.chosen_tbl_hidden_cols = ['lookup_key']
        self.parent_dialog = parent_dialog
        self.gui = parent_dialog.gui
        self.db = parent_dialog.db
        try:
            self.target_db = getattr(parent_dialog, 'target_db')
        except AttributeError:
            self.target_db = None
        self._initialise_layout()
        self.resize_dialog()
        self.populate()

    def _initialise_layout(self):
        self.setWindowTitle(_('Choose Algorithms'))
        l = QGridLayout()
        self.setLayout(l)

        avail_lbl = QLabel(_('Available Algorithms:'), self)
        avail_lbl.setStyleSheet('QLabel { font-weight: bold; }')
        l.addWidget(avail_lbl, 0, 0, 1, 1)

        chosen_lbl = QLabel(_('Chosen Algorithms:'), self)
        chosen_lbl.setStyleSheet('QLabel { font-weight: bold; }')
        l.addWidget(chosen_lbl, 0, 2, 1, 1)

        self.avail_tbl = AlgorithmTable(self, self.avail_tbl_header_labels, self.avail_tbl_hidden_cols)
        l.addWidget(self.avail_tbl, 1, 0, 1, 1)

        move_button_layout = QVBoxLayout()
        l.addLayout(move_button_layout, 1, 1, 1, 1)

        self.add_btn = QToolButton(self)
        self.add_btn.setIcon(get_icon('plus.png'))
        self.add_btn.setToolTip(_('Add the selected algorithm'))
        self.remove_btn = QToolButton(self)
        self.remove_btn.setIcon(get_icon('minus.png'))
        self.remove_btn.setToolTip(_('Remove the selected algorithm'))

        move_button_layout.addStretch(1)
        move_button_layout.addWidget(self.add_btn)
        move_button_layout.addWidget(self.remove_btn)
        move_button_layout.addStretch(1)
        
        self.chosen_tbl = AlgorithmTable(self, self.chosen_tbl_header_labels, self.chosen_tbl_hidden_cols, sortable=False)
        l.addWidget(self.chosen_tbl, 1, 2, 1, 1)

        self.add_btn.clicked.connect(partial(self._transfer_rows, self.avail_tbl, self.chosen_tbl))
        self.remove_btn.clicked.connect(partial(self._transfer_rows, self.chosen_tbl, self.avail_tbl))

        sort_button_layout = QVBoxLayout()
        l.addLayout(sort_button_layout, 1, 3, 1, 1)

        self.add_template_btn = QToolButton(self)
        self.add_template_btn.setIcon(get_icon('template_funcs.png'))
        self.add_template_btn.setToolTip(_('Add template'))
        self.add_template_btn.clicked.connect(self._add_template)
        # disable for calibre < 3.0
        from calibre.constants import numeric_version as calibre_version
        if calibre_version < (3,0,0):
            self.add_template_btn.setVisible(False)
        
        self.up_btn = QToolButton(self)
        self.up_btn.setIcon(get_icon('arrow-up.png'))
        self.up_btn.setToolTip(_('Move the selected item up'))
        self.up_btn.clicked.connect(self._move_rows_up)
        self.down_btn = QToolButton(self)
        self.down_btn.setIcon(get_icon('arrow-down.png'))
        self.down_btn.setToolTip(_('Move the selected item down'))
        self.down_btn.clicked.connect(self._move_rows_down)
        sort_button_layout.addWidget(self.add_template_btn)
        sort_button_layout.addStretch(1)
        sort_button_layout.addWidget(self.up_btn)
        sort_button_layout.addWidget(self.down_btn)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        l.addWidget(self.button_box, 2, 2, 1, 4)

        for tbl in [self.avail_tbl, self.chosen_tbl]:
            tbl.itemPressed.connect(partial(self.table_item_pressed, tbl))
        
        for btn in [self.add_btn, self.remove_btn, self.up_btn, self.down_btn]:
            btn.clicked.connect(self._refresh_btns_state)

        self._refresh_btns_state()

    def algos_to_rows(self, algos):
        rows = []
        for algo in algos:
            name = algo['name']
            settings = algo['settings']
            lookup_key = self.create_lookup_key()
            rows.append([lookup_key, name, ''])
            self.settings_cache[lookup_key] = settings
        return rows

    def _move_rows_up(self):
        self.chosen_tbl.move_rows_up()

    def _move_rows_down(self):
        self.chosen_tbl.move_rows_down()

    def create_lookup_key(self):
        key = unicode(uuid4())
        self.settings_cache[key] = {}
        return key        

    def default_col_value(self, header):
        if header == 'lookup_key':
            return self.create_lookup_key()
        return ''

    def remodel_row(self, row, from_tbl, to_tbl):
        new_row = []
        for header in to_tbl.header_labels:
            try:
                idx = from_tbl.header_labels.index(header)
                item = row[idx]
            except ValueError:
                item = ReadOnlyTableWidgetItem(self.default_col_value(header))
            new_row.append(item)
        return new_row

    def _transfer_rows(self, from_tbl, to_tbl):
        rows = from_tbl.take_rows()
        for row in rows:
            from_tbl.remove_row()
            row = self.remodel_row(row, from_tbl, to_tbl)
            to_tbl.add_row(row)                
        to_tbl.resizeColumnsToContents()

    def _add_template(self):
        d = TemplateBox(self, self.gui, self.db, self.target_db)
        if d.exec_() == d.Accepted:
            template = TEMPLATE_PREFIX + d.template
            name_col = self.chosen_tbl.header_labels.index(_('Name'))
            settings_col = self.chosen_tbl.header_labels.index(_('Settings'))
            tbl_row = [ ReadOnlyTableWidgetItem('') for col in self.chosen_tbl.header_labels]
            template_item = ReadOnlyTableWidgetItem(template)
            tbl_row[name_col] = template_item
            settings_button = TemplateSettingsButton(template_item, self.gui, self.db, self.target_db)
            self.chosen_tbl.add_row(tbl_row)
            self.chosen_tbl.setCellWidget(self.chosen_tbl.rowCount()-1, settings_col, settings_button)
            self.chosen_tbl.resizeColumnsToContents()

    def get_chosen_algorithms(self):        
        algo_dicts = []
        algo_col = self.chosen_tbl.header_labels.index(_('Name'))
        lookup_col = self.chosen_tbl.header_labels.index('lookup_key')
        for row in range(self.chosen_tbl.rowCount()):
            algorithm = self.chosen_tbl.item(row, algo_col).text().strip()
            lookup_key = self.chosen_tbl.item(row, lookup_col).text().strip()
            settings = self.settings_cache[lookup_key]
            algo_dicts.append({'name': algorithm, 'settings': settings})
        
        return algo_dicts

    def table_item_pressed(self, tbl):
        if tbl == self.avail_tbl:
            self.chosen_tbl.clearSelection()
        else:
            self.avail_tbl.clearSelection()
        self._refresh_btns_state()

    def _refresh_btns_state(self):
        for btn in [self.add_btn, self.remove_btn, self.up_btn, self.down_btn]:
            btn.setDisabled(True)
        if self.avail_tbl.selectedItems() != []:
            self.add_btn.setEnabled(True)
        if self.chosen_tbl.selectedItems() != []:
            self.remove_btn.setEnabled(True)
            self.up_btn.setEnabled(self.chosen_tbl.currentRow() != 0)
            self.down_btn.setEnabled(self.chosen_tbl.currentRow() < self.chosen_tbl.rowCount() - 1)

    def _accept_clicked(self):
        
        if len(self.get_chosen_algorithms()) == 0:
            error_dialog(self, _('No algorithms selected'), _('You must select at least one algorithm.'), show=True)
            return
        
        self.accept()

    def populate(self):
        chosen_algos_names = [x[1] for x in self.chosen_rows]
        available_algos_names = set(_all_algorithms.keys()) - set(chosen_algos_names)
        sorted_available_algos_names = [ key for key in _all_algorithms.keys() if key in available_algos_names ]
        self.avail_tbl.populate_table([ [x] for x in sorted_available_algos_names ])
        #self.avail_tbl.sortItems(0, Qt.AscendingOrder)
        self.chosen_tbl.populate_table(self.chosen_rows)

class AlgorithmControl(QGroupBox):
    
    match_rule_updated = pyqtSignal(bool)
    
    def __init__(self, parent, chosen_algos=[], single_mode=False):
        self.possible_cols = parent.possible_cols
        self.single_mode = single_mode
        self.chosen_algos = chosen_algos
        self.parent_container = parent
        self.parent_dialog = self.parent_container.parent_dialog 
        self._init_controls()

    def _init_controls(self):
        QGroupBox.__init__(self)
        
        l = QGridLayout()
        self.setLayout(l)

        row_idx = 0
        if not self.single_mode:
            remove_label = QLabel('<a href="close">✕</a>')
            remove_label.setToolTip(_('Remove'))
            remove_label.linkActivated.connect(self._remove)
            l.addWidget(remove_label, row_idx, 1, 1, 1, Qt.AlignRight)
            row_idx += 1

        gb1 = QGroupBox(_('Column:'))
        gb1_l = QHBoxLayout()
        gb1.setLayout(gb1_l)
        self.col_combo_box = QComboBox()
        self.col_combo_box.addItems(self.possible_cols.keys())
        self.col_combo_box.setCurrentIndex(-1)
        self.col_combo_box.currentTextChanged.connect(self._field_changed)
        gb1_l.addWidget(self.col_combo_box)
        l.addWidget(gb1, row_idx, 0, 1, 1)

        gb2 = QGroupBox(_('Algorithms:'))
        gb2_l = QHBoxLayout()
        gb2.setLayout(gb2_l)

        self.algos_label = QLabel(_('0 Algorithms Chosen'))
        algos_button = QToolButton()
        algos_button.setIcon(get_icon('gear.png'))
        algos_button.setToolTip(_('Add or remove algorithms'))
        algos_button.clicked.connect(self._add_remove_algos)
        gb2_l.addWidget(self.algos_label)
        gb2_l.addWidget(algos_button)
        l.addWidget(gb2, row_idx, 1, 1, 1)
        row_idx += 1

        if not self.single_mode:
            self.multiply_check = QCheckBox(_('Match any of the items'))
            self.multiply_check.setToolTip(_(
                'For fields with multiple items, match with books that any one of the items in this field.\n'
                'if unchecked, books match only when they match on all the items in the field.'
            ))
            self.names_check = QCheckBox(_('contains names').format(self.col_combo_box.currentText()))
            self.names_check.setToolTip(_(
                'Check if composite column contains names'
            ))            
            self.multiply_check.hide()
            self.names_check.hide()
            l.addWidget(self.multiply_check, row_idx, 0, 1, 1)
            l.addWidget(self.names_check, row_idx, 1, 1, 1)
            row_idx += 1
        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def apply_match_rule(self, match_rule):
        chosen_algos = match_rule.get('algos', [])
        if len(chosen_algos) > 0:
            self.update_chosen_algos(chosen_algos)
        field = match_rule.get('field')
        multiply = match_rule.get('multiply', True)
        has_names = match_rule.get('composite_has_names', False)
        if field:
            idx = self.col_combo_box.findText(field)
            if idx != -1:
                self.col_combo_box.setCurrentIndex(idx)
                self._field_changed(self.col_combo_box.currentText())
            if not self.single_mode:
                self.multiply_check.setChecked(multiply)
                self.names_check.setChecked(has_names)
        self.match_rule_updated.emit(self.isComplete()) 

    def _remove(self):
        if self.parent_container.controls_layout.count() == 1:
            error_dialog(
                self,
                _('Cannot delete rule'),
                _('You must have at least one matching rule to proceed'),
                show=True
            )
            return
        container = self.parent_container
        self.setParent(None)
        self.deleteLater()
        
        container.match_rules_updated.emit(container.isComplete() and not container.controls_layout.count() == 0)

    def update_chosen_algos(self, chosen_algos):
        self.chosen_algos = chosen_algos
        algos_no = len(self.chosen_algos)
        try:
            first_algo_name = self.chosen_algos[0]['name']
            if first_algo_name.startswith(TEMPLATE_PREFIX):
                first_algo_name = 'TEMPLATE'
        except:
            first_algo_name = ''
        if algos_no == 0:
            text = _('0 Algorithms Chosen')
        elif algos_no == 1:
            text = '{}'.format(truncate(first_algo_name, length=30))
        else:
            text = _('{} + {} others').format(truncate(first_algo_name), algos_no-1)
        self.algos_label.setText(text)
        
        self.match_rule_updated.emit(self.isComplete())

    def _add_remove_algos(self):
        d = AlgorithmDialog(self.parent_dialog, self.chosen_algos)
        if d.exec_() == d.Accepted:
            self.update_chosen_algos(chosen_algos=d.get_chosen_algorithms())

    def _field_changed(self, field):
        if not self.single_mode:
            multiply_status = self.possible_cols[field]['is_multiple'] != {}
            self.multiply_check.setEnabled(multiply_status)
            self.multiply_check.setChecked(multiply_status)
            if multiply_status:
                self.multiply_check.show()
            else:
                self.multiply_check.hide()
            
            name_status = multiply_status and ( self.possible_cols[field]['datatype'] == 'composite' )
            self.names_check.setChecked(False)
            self.names_check.setEnabled(name_status)
            if name_status:
                self.names_check.show()
            else:
                self.names_check.hide()

        self.match_rule_updated.emit(self.isComplete())

    def isComplete(self):
        '''returns True only if a field and algorithm are chosen'''
        if self.col_combo_box.currentText() == '':
            return False
        if not self.chosen_algos:
            return False
        return True
    
    def get_match_rule(self):
        res = {}
        res['field'] = self.col_combo_box.currentText()
        if not self.single_mode:
            res['multiply'] = self.multiply_check.isChecked()
            res['composite_has_names'] = self.names_check.isChecked()
        res['algos'] = self.chosen_algos
        return res

class ControlsContainer(QWidget):

    match_rules_updated = pyqtSignal(bool)
    
    def __init__(self, parent_dialog, single_mode=False, has_sort=False):
        self.single_mode = single_mode
        self.parent_dialog = parent_dialog
        self.possible_cols = parent_dialog.possible_cols
        self.gui = parent_dialog.gui
        self.has_sort = has_sort
        self.sort_filters = {}
        self._init_controls()

    def _init_controls(self):
        QWidget.__init__(self)
        l = QVBoxLayout()
        self.setLayout(l)
        
        if not self.single_mode:
            hl1 = QHBoxLayout()
            clear_button = QPushButton(_('Clear'))
            clear_button.setToolTip(_('Clear all match rules'))
            clear_button.setIcon(get_icon('clear_left.png'))
            clear_button.clicked.connect(self.reset)
            clear_button.clicked.connect(self.match_rules_updated)
            hl1.addWidget(clear_button)
            hl1.addStretch(1)

            if self.has_sort:
                sort_button = QPushButton(_('Duplicates sort'), self)
                sort_button.setIcon(QIcon(I('sort.png')))
                sort_button.setToolTip(_('Configure sort filters for books inside duplicate groups'))
                sort_button.clicked.connect(self._sort_button_clicked)
                hl1.addWidget(sort_button)
                hl1.addStretch(1)

            add_button = QPushButton(_('Add Match Rules'))
            add_button.setToolTip(_('Add a rule containing a field and one or more match algorithm/template(s).'))
            add_button.setIcon(get_icon('plus.png'))
            add_button.clicked.connect(self.add_control)
            hl1.addWidget(add_button)
            l.addLayout(hl1)

        w = QWidget(self)
        self.controls_layout = QVBoxLayout()
        self.controls_layout.setSizeConstraint(self.controls_layout.SetMinAndMaxSize)
        w.setLayout(self.controls_layout)
        
        scroll = QScrollArea()
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        scroll.setObjectName('myscrollarea')
        scroll.setStyleSheet('#myscrollarea {background-color: transparent}')
        scroll.setWidget(w)
         
        l.addWidget(scroll)
        
        self._add_control(match_rule={})

    def isComplete(self):
        '''return True if all controls have fields and algorithms set'''
        for idx in range(self.controls_layout.count()):
            control = self.controls_layout.itemAt(idx).widget()
            if not control.isComplete():
                return False
        return True

    def _add_control(self, match_rule={}):
        control = AlgorithmControl(self, single_mode=self.single_mode)
        control.match_rule_updated.connect(self.match_rules_updated)
        if match_rule:
            control.apply_match_rule(match_rule)
        self.controls_layout.addWidget(control)
        control.match_rule_updated.emit(control.isComplete())

    def add_control(self):
        if not self.isComplete():
            error_dialog(
                self,
                _('Incomplete Match Rule'),
                _('You must complete the previous match rule(s) before adding any new rules.'),
                show=True
            )
            return
        self._add_control(match_rule={})

    def _sort_button_clicked(self):
        d = SortDialog(self.gui, self.sort_filters)
        if d.exec_() == d.Accepted:
            self.sort_filters = d.sort_filters
            print('Find Duplicate: debug: sort_filters: {}'.format(self.sort_filters))

    def reset(self, possible_cols={}, add_empty_control=True):
        if possible_cols:
            self.possible_cols = possible_cols
        # remove controls in reverse order
        for idx in reversed(range(self.controls_layout.count())):
            control = self.controls_layout.itemAt(idx).widget()
            control.setParent(None)
            control.deleteLater()
        if add_empty_control:
            self._add_control(match_rule={})
        self.sort_filters = {}
        self.match_rules_updated.emit(self.isComplete() and not self.controls_layout.count() == 0)

    def get_match_rules(self):
        match_rules = []
        for idx in range(self.controls_layout.count()):
            control = self.controls_layout.itemAt(idx).widget()
            match_rules.append(control.get_match_rule())
        return match_rules

    def get_rules_and_filters(self):
        match_rules = self.get_match_rules()
        return {
            'match_rules': match_rules,
            'sort_filters': self.sort_filters
        }

