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
    from PyQt5 import QtWidgets as QtGui
    from PyQt5.Qt import (Qt, QGridLayout, QHBoxLayout, QVBoxLayout, QToolButton,
                          QDialog, QSizePolicy, QSize)

except ImportError:
    from PyQt4 import QtGui
    from PyQt4.Qt import (Qt, QGridLayout, QHBoxLayout, QVBoxLayout, QToolButton,
                          QDialog, QSizePolicy, QSize)

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog

from calibre_plugins.find_duplicates.common_utils import get_icon
from calibre_plugins.find_duplicates.advanced.common import TEMPLATE_PREFIX, TEMPLATE_ERROR

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/templates.py - exception when loading translations")
    pass

def dummy_metadata(db):
    fm = db.new_api.field_metadata
    mi = Metadata(_('Title'), [_('Author')])
    mi.author_sort = _('Author Sort')
    mi.series = ngettext('Series', 'Series', 1)
    mi.series_index = 3
    mi.rating = 4.0
    mi.tags = [_('Tag 1'), _('Tag 2')]
    mi.languages = ['eng']
    mi.id = 1
    mi.set_all_user_metadata(fm.custom_field_metadata())
    for col in mi.get_all_user_metadata(False):
        mi.set(col, (col,), 0)
    return mi

def get_metadata_object(gui):
    db = gui.current_db
    try:
        current_row = gui.library_view.currentIndex()
        book_id = gui.library_view.model().id(current_row)
        mi = db.new_api.get_proxy_metadata(book_id)
    except Exception as e:
        if DEBUG:
            prints('Action Chains: get_metadata_object: exception trying to get mi from current row')
        try:
            book_id = list(db.all_ids())[0]
            mi = db.new_api.get_proxy_metadata(book_id)
        except:
            mi = dummy_metadata(db)
    return mi

def check_template(template, db, gui, target_db=None, print_error=True):
    error_msgs = [
        TEMPLATE_ERROR,
        'unknown function',
        'unknown identifier',
        'unknown field',
        'assign requires the first parameter be an id',
        'missing closing parenthesis',
        'incorrect number of arguments for function',
        'expression is not function or constant'
    ]
    all_errors = ''
    book_id = list(db.all_ids())[0]
    mi = db.new_api.get_proxy_metadata(book_id)
    if not (template.startswith('{') or template.startswith('program:')):
        if print_error:
            all_errors += 'Template must start with { or program:'
            error_dialog(
            gui,
            _('Template Error'),
            _('Templates must be either enclosed within curly brackets, or starts with: "program:"'),
            show=True
        )
        return False, all_errors
    output = SafeFormat().safe_format(template, mi, TEMPLATE_ERROR, mi)
    for msg in error_msgs:
        if output.lower().find(msg.lower()) != -1:
            all_errors += output + '\n'
            if print_error:
                error_dialog(
                gui,
                _('Template Error'),
                _('Running the template returned an error:\n{}').format(output.lstrip(TEMPLATE_ERROR)),
                show=True
            )
            return False, all_errors
    if target_db:
        book_id = list(target_db.all_ids())[0]
        mi = db.new_api.get_proxy_metadata(book_id)
        output = SafeFormat().safe_format(template, mi, TEMPLATE_ERROR, mi)
        for msg in error_msgs:
            if output.lower().find(msg.lower()) != -1:
                all_errors += output + '\n'
                if print_error:
                    error_dialog(
                        gui,
                        _('Target Library Template Error'),
                        _('Running the template in target library returned an error:\n{}').format(output.lstrip(TEMPLATE_ERROR)),
                        show=True
                    )
                return False, all_errors
    return True, all_errors

class TemplateBox(TemplateDialog):
    def __init__(
        self,
        parent,
        gui,
        db,
        target_db,
        template_text=''
    ):
        self.gui = gui
        self.db = db
        self.target_db = target_db
        mi = get_metadata_object(self.gui)
        
        if not template_text:
            text = _('Enter a template to test using data from the selected book')
            text_is_placeholder = True
            window_title = _('Add template')
        else:
            text = None
            text_is_placeholder = False
            window_title = _('Edit Template')
        TemplateDialog.__init__(
            self,
            parent,
            text,
            mi=mi,
            text_is_placeholder=text_is_placeholder
        )
        self.setWindowTitle(window_title)
        if template_text:
            self.textbox.insertPlainText(template_text)

    def accept(self):
        self.template = unicode(self.textbox.toPlainText()).rstrip()
        is_success, all_errors = check_template(self.template, self.db, self, self.target_db)
        if is_success:
            QDialog.accept(self)

class TemplateSettingsButton(QToolButton):
    def __init__(self, template_table_item, gui, db, target_db):
        QToolButton.__init__(self)
        self.template_table_item = template_table_item
        self.gui = gui
        self.db = db
        self.target_db = target_db
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setMaximumWidth(30)
        self.setIcon(get_icon('template_funcs.png'))
        self.setToolTip(_('Edit Template'))
        self.clicked.connect(self._clicked)
    
    def _clicked(self):
        template_text = self.template_table_item.text().strip().lstrip(TEMPLATE_PREFIX)
        d = TemplateBox(self, self.gui, self.db, self.target_db, template_text=template_text)
        if d.exec_() == d.Accepted:
            template = TEMPLATE_PREFIX + d.template
            self.template_table_item.setText(template)
