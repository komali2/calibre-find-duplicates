#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

try:
    from PyQt5.Qt import (QGridLayout, QLabel, QDialogButtonBox, QPlainTextEdit, QCheckBox,
                          QWidget, QSize, QSizePolicy, QPainter)

except ImportError:
    from PyQt4.Qt import (QGridLayout, QLabel, QDialogButtonBox, QPlainTextEdit, QCheckBox,
                          QWidget, QSize, QSizePolicy, QPainter)

from functools import partial
from collections import OrderedDict, defaultdict
import re
import traceback

# python3 compatibility
from six.moves import range
from six import text_type as unicode, string_types as basestring

from calibre.gui2.dialogs.message_box import MessageBox
from calibre.ebooks.metadata.book.formatter import SafeFormat

TEMPLATE_PREFIX = 'TEMPLATE: '
TEMPLATE_ERROR = 'FD template error'

def truncate(string, length=22):
    return (string[:length] + '...') if len(string) > length else string

def to_list(string, sep=','):
    if string:
        return [a.strip().replace('|',',') for a in string.split(sep)]
    return []

STANDARD_FIELD_KEYS = [
    'title',
    'authors',
    'tags',
    'series',
    'languages',
    'publisher',
    'pubdate',
    'rating',
    'timestamp'
]

def get_cols(db):
    custom_fields = sorted([k for k,v in db.field_metadata.custom_field_metadata().items() if v['datatype'] not in ['comments']])
    all_metadata = OrderedDict()
    for field in STANDARD_FIELD_KEYS + custom_fields:
        all_metadata[field] = db.field_metadata.all_metadata()[field]
    return update_metadata(all_metadata)


def update_metadata(metadata):
    for column, meta in metadata.items():
        if column == 'publisher':
            meta['icon_name'] = 'publisher.png'
            meta['delegate'] = 'publisher'
            meta['soundex_length'] = 6
        elif meta['datatype'] == 'series':
            meta['icon_name'] = 'series.png'
            meta['delegate'] = 'series'
            meta['soundex_length'] = 6
        elif meta['is_multiple'] != {}:
            if column == 'authors' or meta['display'].get('is_names'):
                meta['icon_name'] = 'user_profile.png'
                meta['delegate'] = 'authors'
                meta['soundex_length'] = 8
            else:
                meta['icon_name'] = 'tags.png'
                meta['delegate'] = 'tags'
                meta['soundex_length'] = 4
        else:
            meta['icon_name'] = 'column.png'
            meta['delegate'] = 'title'
            meta['soundex_length'] = 6
    return metadata


class RestoreError(Exception):
    def __init__(self, error_msg):
        self.error_msg = error_msg

def do_udpate_mi(mi, field_name, value, all_metadata):
    if field_name.startswith('identifier:'):
        # 'identifier:' has no entry in all_metadata and would raise an exception
        pass
    # all composite fields (even those where ['is_multiple'] != {}) are of string type
    elif not all_metadata[field_name]['datatype'] == 'composite':
        if all_metadata[field_name]['is_multiple'] != {}:
            # for fields with multiple items, when we update a single item, we must put it in a list
            # because mi expect multiple value field, if you don't do this it will treat the string
            # value as iterable and split it into letters.
            value = [value]
    setattr(mi, field_name, value)

def algorithm_caller(algorithm, field_name, hash_, all_metadata, mi, settings, **kwargs):
    if not hasattr(algorithm, '__call__'):
        # handle the code for templates here
        
        # update the mi to presist the hash as this the only way a template can see the result of the previous algorithm/template
        do_udpate_mi(mi, field_name, hash_, all_metadata)

        template = algorithm.lstrip(TEMPLATE_PREFIX)
        hash_ = SafeFormat().safe_format(template, mi, TEMPLATE_ERROR, mi)
    else:
        kwargs2 = OrderedDict()
        kwargs2.update(settings)
        kwargs2.update(kwargs)
        hash_ = algorithm(hash_, mi, **kwargs2)
    return hash_

def get_field_value(book_id, db, field_name, mi):
    # LibraryDatabase2 does not support: field_value = db.new_api.field_for(field_name, book_id)        
    if field_name == 'title':
        field_value = db.title(book_id, index_is_id=True)
    elif field_name == 'authors':
        field_value = to_list(db.authors(book_id, index_is_id=True))
    elif field_name == 'tags':
        field_value = to_list(db.tags(book_id, index_is_id=True))
    elif field_name == 'series':
        field_value = db.series(book_id, index_is_id=True)
    elif field_name == 'publisher':
        field_value = db.publisher(book_id, index_is_id=True)
    elif field_name == 'pubdate':
        field_value = db.pubdate(book_id, index_is_id=True)
    elif field_name == 'timestamp':
        field_value = db.timestamp(book_id, index_is_id=True)
    elif field_name == 'rating':
        field_value = db.rating(book_id, index_is_id=True)
    elif field_name == 'languages':
        field_value = to_list(db.languages(book_id, index_is_id=True))
    elif field_name.startswith('#'):
        label = db.field_metadata.all_metadata()[field_name]['label']
        field_value = db.get_custom(book_id, label, index_is_id=True)
    elif field_name.startswith('identifier:'):
        identifier_type = field_name.split(':')[-1]
        identifiers = self.db.get_identifiers(book_id, index_is_id=True)
        field_value = identifiers.get(identifier_type)

    return field_value

def composite_to_list(field_name, field_value, db, composite_has_names):
    all_metadata = db.field_metadata.all_metadata()

    #{ compoiste fields with multiple items are currently returned as string, convert to list with items
    if all_metadata[field_name]['datatype'] == 'composite':
        # test first, maybe it will change in future calibre releases
        if isinstance(field_value, basestring):
            if composite_has_names:
                SEP = '&'
            else:
                SEP = all_metadata[field_name]['is_multiple']['list_to_ui']
            field_value = to_list(field_value, sep=SEP)
    #}
    return field_value

# copied from calibre.gui2.dialogs.message_box
# cannot import because it is absent in calibre 2.x
# https://www.mobileread.com/forums/showpost.php?p=4090981&postcount=820
class Icon(QWidget):

    def __init__(self, parent=None, size=None):
        QWidget.__init__(self, parent)
        self.pixmap = None
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.size = size or 64

    def set_icon(self, qicon):
        self.pixmap = qicon.pixmap(self.size, self.size)
        self.update()

    def sizeHint(self):
        return QSize(self.size, self.size)

    def paintEvent(self, ev):
        if self.pixmap is not None:
            x = (self.width() - self.size) // 2
            y = (self.height() - self.size) // 2
            p = QPainter(self)
            p.drawPixmap(x, y, self.size, self.size, self.pixmap)

class MessageBox2(MessageBox):
    def setup_ui(self):
        self.setObjectName("Dialog")
        self.resize(497, 235)
        self.gridLayout = l = QGridLayout(self)
        l.setObjectName("gridLayout")
        self.icon_widget = Icon(self)
        l.addWidget(self.icon_widget)
        self.msg = la = QLabel(self)
        la.setWordWrap(True), la.setMinimumWidth(400)
        la.setOpenExternalLinks(True)
        la.setObjectName("msg")
        l.addWidget(la, 0, 1, 1, 1)
        self.det_msg = dm = QPlainTextEdit(self)
        dm.setReadOnly(True)
        dm.setObjectName("det_msg")
        l.addWidget(dm, 1, 0, 1, 2)
        self.bb = bb = QDialogButtonBox(self)
        bb.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.setObjectName("bb")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 3, 0, 1, 2)
        self.toggle_checkbox = tc = QCheckBox(self)
        tc.setObjectName("toggle_checkbox")
        l.addWidget(tc, 2, 0, 1, 2)

def confirm_with_details(parent, title, msg, det_msg='',
        show_copy_button=True):
    d = MessageBox2(MessageBox.INFO, title, msg, det_msg, parent=parent,
                    show_copy_button=show_copy_button)

    return d.exec_() == d.Accepted
