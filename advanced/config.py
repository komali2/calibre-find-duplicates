#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import copy

from calibre_plugins.find_duplicates.config import (KEY_SHOW_ALL_GROUPS, KEY_SORT_GROUPS_TITLE,
    KEY_SHOW_VARIATION_BOOKS, set_library_config)
from calibre_plugins.find_duplicates.config import get_library_config as get_library_config_orig


KEY_ADVANCED_MODE = 'advancedMode'
KEY_BOOK_DUPLICATES = 'bookDuplicates'
KEY_LIBRARY_DUPLICATES = 'libraryDuplicates'
KEY_METADATA_VARIATIONS = 'metadataVariations'
KEY_LIBRARIES_LOC_LIST = 'librariesList'
KEY_LAST_SETTINGS = 'lastSettings'
KEY_SAVED_SETTINGS = 'savedSettings'
KEY_RESTORE_LAST_SETTINGS = 'restoreLastSettings'
KEY_SAVED_SETTINGS_SCHEMA = 'findDuplicatesSavedSettingsSchema'
DEFAULT_SETTINGS_SCHEMA = 1.0

ADVANCED_MODE_DEFAULTS = {
    KEY_BOOK_DUPLICATES: {
        KEY_SHOW_ALL_GROUPS: True,
        KEY_SORT_GROUPS_TITLE: False,
        KEY_LAST_SETTINGS: {}
    },
    KEY_LIBRARY_DUPLICATES: {
        KEY_LIBRARIES_LOC_LIST: [],
        KEY_LAST_SETTINGS: {}
    },
    KEY_METADATA_VARIATIONS: {
        KEY_SHOW_VARIATION_BOOKS: False,
        KEY_LAST_SETTINGS: {}
    },
#    KEY_RESTORE_LAST_SETTINGS: False,
    KEY_SAVED_SETTINGS: {}
}

def get_missing_values_from_defaults(default_settings, settings):
    '''add keys present in default_settings and absent in setting'''
    for k, default_value in default_settings.items():
        try:
            setting_value = settings[k]
            if isinstance(setting_value, dict):
                get_missing_values_from_defaults(default_value, setting_value)
        except KeyError:
            settings[k] = copy.deepcopy(default_value)

def get_library_config(db):
    library_config = get_library_config_orig(db)
    if not library_config.get(KEY_ADVANCED_MODE):
        library_config[KEY_ADVANCED_MODE] = copy.deepcopy(ADVANCED_MODE_DEFAULTS)
    else:
        get_missing_values_from_defaults(ADVANCED_MODE_DEFAULTS, library_config[KEY_ADVANCED_MODE])
    return library_config
