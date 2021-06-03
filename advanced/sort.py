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
from datetime import datetime

# python3 compatibility
from six.moves import range
from six import text_type as unicode, string_types as basestring

try:
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (QApplication, Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
                          QLabel, QGroupBox, QToolButton, QPushButton, QScrollArea, QComboBox,
                          QRadioButton, QDialog, QDialogButtonBox, QCheckBox, QSizePolicy)

except ImportError:
    from PyQt4 import QtGui
    from PyQt4.Qt import (QApplication, Qt, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout,
                          QLabel, QGroupBox, QToolButton, QPushButton, QScrollArea, QComboBox,
                          QRadioButton, QDialog, QDialogButtonBox, QCheckBox, QSizePolicy)

from calibre import prints
from calibre.constants import DEBUG
from calibre.gui2 import error_dialog
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.ebooks.metadata.book.base import Metadata
from calibre.utils.date import parse_date, UNDEFINED_DATE

from calibre_plugins.find_duplicates.common_utils import SizePersistedDialog, get_icon
from calibre_plugins.find_duplicates.advanced.common import truncate, get_cols, get_field_value
from calibre_plugins.find_duplicates.advanced.templates import TemplateBox, TemplateSettingsButton, check_template, TEMPLATE_PREFIX, TEMPLATE_ERROR
from calibre_plugins.find_duplicates.advanced.common import RestoreError

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/sort.py - exception when loading translations")
    pass

def get_sort_value(db, field_name, template_type, mi_map, book_id):
    if field_name == 'id':
        value = book_id
    elif field_name.startswith(TEMPLATE_PREFIX):
        template = field_name.lstrip(TEMPLATE_PREFIX)
        mi = mi_map[book_id]
        value = SafeFormat().safe_format(template, mi, TEMPLATE_ERROR, mi)
        
        # format template output to suitable type
        types = {
            'number': [float, 0.0],
            'date': [parse_date, UNDEFINED_DATE]
        }
        if template_type:
            type_ = types.get(template_type)
            if type_:
                try:
                    type_func = types[template_type][0]
                    value = type_func(value)
                except:
                    value = types[template_type][1]
        #
    else:
        value = get_field_value(book_id, db, field_name, mi=None)
        if isinstance(value, list):
            sep = db.field_metadata.all_metadata()[field_name]['is_multiple']['list_to_ui']
            value = sep.join(value)
    # list.sort fails if it receives nontype
    if type(value) == type(None):
        value = ''
    return value

def check_sort_filter(sort_filter, possible_cols, db, gui):
    '''
    check sort filter for errors
    '''
    book_id = list(db.all_ids())[0]
    mi = db.new_api.get_proxy_metadata(book_id)
    has_errors = False
    field = sort_filter['field']
    if field.startswith(TEMPLATE_PREFIX):
        is_success, all_errors = check_template(field.lstrip(TEMPLATE_PREFIX), db, gui, None, print_error=False)
        if not is_success:
            has_errors = True
            if DEBUG:
                prints('Find Duplicates: tepmlate: "{}" returned this error: {}'.format(field, all_errors))
    else: 
        if not field in possible_cols.keys():
            has_errors = True
            if DEBUG:
                prints('Find Duplicates: cannot add column to sort filter: {}, possible columns: {}'.format(field, possible_cols.keys()))

    return has_errors

def sort_filters_has_templates(sort_filters):
    for sort_filter in sort_filters:
        field = sort_filter['field']
        if field.startswith(TEMPLATE_PREFIX):
            return True
    return False

class SortControl(QGroupBox):
    
    def __init__(self, parent, template_mode=False):
        self.possible_cols = parent.possible_cols
        self.template_mode = template_mode
        self.template = ''
        self.parent_container = parent
        self.gui = parent.gui
        self.db = self.gui.current_db
        self.parent_dialog = self.parent_container.parent_dialog 
        self._init_controls()

    def _init_controls(self):
        QGroupBox.__init__(self)
        
        l = QGridLayout()
        self.setLayout(l)

        row_idx = 0
        remove_label = QLabel('<a href="close">✕</a>')
        remove_label.setToolTip(_('Remove'))
        remove_label.linkActivated.connect(self._remove)
        l.addWidget(remove_label, row_idx, 1, 1, 1, Qt.AlignRight)
        row_idx += 1

        gb1 = QGroupBox('')
        gb1_l = QVBoxLayout()
        gb1.setLayout(gb1_l)

        if self.template_mode:
            gb1_text = _('Template:')
            self.template_button = QPushButton(_('Edit/View Template'), self)
            self.template_button.clicked.connect(self._edit_template)
            #
            type_layout = QHBoxLayout()
            self.button_text = QRadioButton(_('Text'), self)
            type_layout.addWidget(self.button_text)
            self.button_text.setChecked(True)
            self.button_number = QRadioButton(_('Number'), self)
            type_layout.addWidget(self.button_number)
            self.button_number.setChecked(False)
            self.button_date = QRadioButton(_('Date'), self)
            type_layout.addWidget(self.button_date)
            self.button_date.setChecked(False)
            #
            gb1_l.addWidget(self.template_button)
            gb1_l.addLayout(type_layout)
        else:
            gb1_text = _('Column:')
            self.col_combo_box = QComboBox()
            self.col_combo_box.addItems(self.possible_cols.keys())
            self.col_combo_box.setCurrentIndex(-1)
            gb1_l.addWidget(self.col_combo_box)
            
        gb1.setTitle(gb1_text)
        l.addWidget(gb1, row_idx, 0, 1, 1)


        gb2 = QGroupBox(_('Sort direction'), self)
        gb2_l = QVBoxLayout()
        gb2.setLayout(gb2_l)

        self.button_ascend = QRadioButton(_('Ascending'), self)
        gb2_l.addWidget(self.button_ascend)
        self.button_ascend.setChecked(True)
        self.button_descend = QRadioButton(_('Descending'), self)
        gb2_l.addWidget(self.button_descend)
        self.button_descend.setChecked(False)

        l.addWidget(gb2, row_idx, 1, 1, 1)
        row_idx += 1

        l.setColumnStretch(0, 1)        
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

    def apply_sort_filter(self, sort_filter):
        field = sort_filter['field']
        is_reversed = sort_filter['is_reversed']
        if self.template_mode:
            self.template = field
            template_type = sort_filter.get('template_type')
            for button, text in [(self.button_text,None),(self.button_number,'number'),(self.button_date,'date')]:
                button.setChecked(template_type == text)
        else:
            self.col_combo_box.setCurrentText(field)
        self.button_ascend.setChecked(not is_reversed)
        self.button_descend.setChecked(is_reversed)

    def _remove(self):
        self.setParent(None)
        self.deleteLater()

    def isComplete(self):
        '''returns True only if a field and direction are chosen'''
        if self.template_mode:
            if not self.template:
                return False
        else:
            if self.col_combo_box.currentText() == '':
                return False
        return True

    def _edit_template(self):
        template_text = self.template.lstrip(TEMPLATE_PREFIX)
        d = TemplateBox(self, self.gui, self.db, None, template_text=template_text)
        if d.exec_() == d.Accepted:
            template = TEMPLATE_PREFIX + d.template
            self.template = d.template
    
    def get_sort_filter(self):
        template_type = None
        if self.template_mode:
            field = TEMPLATE_PREFIX + self.template
            for button, text in [(self.button_text,None),(self.button_number,'number'),(self.button_date,'date')]:
                if button.isChecked():
                    template_type = text
                    break
        else:
            field = self.col_combo_box.currentText()
        is_reversed = self.button_descend.isChecked()
        return { 'field': field, 'is_reversed': is_reversed, 'template_type': template_type }

class SortControlsContainer(QWidget):
    
    def __init__(self, parent_dialog):
        self.parent_dialog = parent_dialog
        self.gui = parent_dialog.gui
        self.db = self.gui.current_db
        self.possible_cols = parent_dialog.possible_cols
        self._init_controls()

    def _init_controls(self):
        QWidget.__init__(self)
        l = QVBoxLayout()
        self.setLayout(l)
        
        hl1 = QHBoxLayout()
        clear_button = QPushButton(_('Clear'))
        clear_button.setToolTip(_('Clear all filters'))
        clear_button.setIcon(get_icon('clear_left.png'))
        clear_button.clicked.connect(self.reset)
        hl1.addWidget(clear_button)
        hl1.addStretch(1)
        add_template_button = QPushButton(_('Add Template'))
        add_template_button.setToolTip(_('Add a template whose result is used as a sort filter'))
        add_template_button.setIcon(get_icon('template_funcs.png'))
        add_template_button.clicked.connect(partial(self.add_control, True))
        hl1.addWidget(add_template_button)
        hl1.addStretch(1)
        add_button = QPushButton(_('Add Sort Filter'))
        add_button.setToolTip(_('Add a column to sort by'))
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
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll.setObjectName('myscrollarea')
        scroll.setStyleSheet('#myscrollarea {background-color: transparent}')
        scroll.setWidget(w)
         
        l.addWidget(scroll)
        
        self._add_control(sort_filter={})

    def isComplete(self):
        '''return True if all controls have fields and algorithms set'''
        for idx in range(self.controls_layout.count()):
            control = self.controls_layout.itemAt(idx).widget()
            if not control.isComplete():
                return False
        return True

    def _add_control(self, sort_filter={}):
        control = SortControl(self)
        if sort_filter:
            control.apply_sort_filter(sort_filter)
        self.controls_layout.addWidget(control)

    def _add_template_control(self, sort_filter={}):
        if not sort_filter:
            d = TemplateBox(self, self.gui, self.db, None, template_text='')
            if d.exec_() == d.Accepted:
                template = TEMPLATE_PREFIX + d.template
                #self.template = d.template
                #control.template = template
                sort_filter = {'field': template.lstrip(TEMPLATE_PREFIX), 'is_reversed': False}
            else:
                return
        control = SortControl(self, template_mode=True)
        control.apply_sort_filter(sort_filter)
        self.controls_layout.addWidget(control)

    def add_control(self, template_mode=False):
        if not self.isComplete():
            error_dialog(
                self,
                _('Incomplete Sort Filter'),
                _('You must complete the previous sort filter(s) to proceed.'),
                show=True
            )
            return
        if template_mode:
            self._add_template_control(sort_filter={})
        else:
            self._add_control(sort_filter={})

    def reset(self, add_empty_control=True):
        # remove controls in reverse order
        for idx in reversed(range(self.controls_layout.count())):
            control = self.controls_layout.itemAt(idx).widget()
            control.setParent(None)
            control.deleteLater()
        if add_empty_control:
            self._add_control(sort_filter={})

    def get_sort_filters(self):
        all_filters = []
        for idx in range(self.controls_layout.count()):
            control = self.controls_layout.itemAt(idx).widget()
            all_filters.append(control.get_sort_filter())
        return all_filters


class SortDialog(SizePersistedDialog):
    def __init__(self, gui, sort_filters=[]):
        SizePersistedDialog.__init__(self, gui, 'Sort Dialog')
        self.gui = gui
        self.db = gui.current_db
        self.possible_cols = self.get_possible_cols()
        self._init_controls()
        self.resize_dialog()
        self.restore_sort_filters(sort_filters)

    def _init_controls(self):
        self.setWindowTitle(_('Sort duplicate groups'))
        l = QVBoxLayout()
        self.setLayout(l)

        self.container = SortControlsContainer(self)
        l.addWidget(self.container, 1)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._accept_clicked)
        self.button_box.rejected.connect(self.reject)
        l.addWidget(self.button_box,)
        
        self.resize(500, 600)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
    def get_possible_cols(self):
        return get_cols(self.db)

    def restore_sort_filters(self, sort_filters):
        error_msg = ''

        if not sort_filters:
            return True

        self.container.reset(add_empty_control=False)

        for idx, sort_filter in enumerate(sort_filters, 1):
            has_errors = check_sort_filter(sort_filter, self.possible_cols, self.db, self.gui)
            
            if has_errors:
                error_msg += _('Error in sort filter No. {}: {}').format(idx, sort_filter) + '\n'
            else:
                field = sort_filter['field']
                if field.startswith(TEMPLATE_PREFIX):
                    self.container._add_template_control(sort_filter)
                else:
                    self.container._add_control(sort_filter)

        if error_msg:
            raise RestoreError(error_msg)
        else:
            return True

    def _accept_clicked(self):
        if not self.container.isComplete():
            error_dialog(
                self,
                _('Sort filters not complete'),
                _('You must complete sort filters'),
                show=True
            )
            return
        self.sort_filters = self.container.get_sort_filters()
        self.accept()
