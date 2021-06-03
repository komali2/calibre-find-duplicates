#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict, defaultdict

# python 3 compatibility
from six.moves import range

from calibre import prints
from calibre.constants import DEBUG

import calibre_plugins.find_duplicates.matching as matching
from calibre_plugins.find_duplicates.advanced.common import get_cols

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/algorithms.py - exception when loading translations")
    pass

#======================

def identical_title_match(title, mi, **kwargs):
    lang = kwargs.get('lang', None)
    return matching.identical_title_match(title, lang=lang)

def similar_title_match(title, mi, **kwargs):
    lang = kwargs.get('lang', None)
    return matching.similar_title_match(title, lang=lang)

def soundex_title_match(title, mi, soundex_length=6, **kwargs):
    lang = kwargs.get('lang', None)
    matching.set_title_soundex_length(soundex_length)
    return matching.soundex_title_match(title, lang=lang)

def fuzzy_title_match(title, mi, **kwargs):
    lang = kwargs.get('lang', None)
    return matching.fuzzy_title_match(title, lang=lang)

def identical_authors_match(author, mi, **kwargs):
    ahash, rev_ahash = matching.identical_authors_match(author)
    return ahash

def similar_authors_match(author, mi, **kwargs):
    author_tokens = list(matching.get_author_tokens(author))
    ahash = ' '.join(author_tokens)
    return ahash

def soundex_authors_match(author, mi, soundex_length=8, **kwargs):
    # Convert to an equivalent of "similar" author first before applying the soundex
    author_tokens = list(matching.get_author_tokens(author))
    if len(author_tokens) <= 1:
        return matching.soundex(''.join(author_tokens))
    # We will put the last name at front as want the soundex to focus on surname
    new_author_tokens = [author_tokens[-1]]
    new_author_tokens.extend(author_tokens[:-1])
    ahash = matching.soundex(''.join(new_author_tokens), soundex_length)
    return ahash

def fuzzy_authors_match(author, mi, **kwargs):
    ahash, rev_ahash = matching.fuzzy_authors_match(author)
    return ahash

def rev_similar_authors_match(author, mi, **kwargs):
    author_tokens = list(matching.get_author_tokens(author))
    rev_ahash = ''
    if len(author_tokens) > 1:
        author_tokens = author_tokens[1:] + author_tokens[:1]
        rev_ahash = ' '.join(author_tokens)
    return rev_ahash

def rev_soundex_authors_match(author, mi, soundex_length=8, **kwargs):
    # Convert to an equivalent of "similar" author first before applying the soundex
    author_tokens = list(matching.get_author_tokens(author))
    if len(author_tokens) <= 1:
        return ''
    # We will put the last name at front as want the soundex to focus on surname
    rev_ahash = matching.soundex(''.join(author_tokens), soundex_length)
    return rev_ahash

def identical_series_match(series, mi, **kwargs):
    return matching.identical_title_match(series)

def similar_series_match(series, mi, **kwargs):
    return matching.similar_series_match(series)

def soundex_series_match(series, mi, soundex_length=6, **kwargs):
    matching.set_series_soundex_length(soundex_length)
    return matching.soundex_series_match(series)

def fuzzy_series_match(series, mi, **kwargs):
    return matching.fuzzy_series_match(series)

def identical_publisher_match(publisher, mi, **kwargs):
    return matching.identical_title_match(publisher)

def similar_publisher_match(publisher, mi, **kwargs):
    return matching.similar_publisher_match(publisher)

def soundex_publisher_match(publisher, mi, soundex_length=6, **kwargs):
    matching.set_publisher_soundex_length(soundex_length)
    return matching.soundex_publisher_match(publisher)

def fuzzy_publisher_match(publisher, mi, **kwargs):
    return matching.fuzzy_publisher_match(publisher)

def identical_tags_match(tags, mi, **kwargs):
    return matching.identical_title_match(tags)

def similar_tags_match(tags, mi, **kwargs):
    return matching.similar_tags_match(tags)

def soundex_tags_match(tags, mi, soundex_length=4, **kwargs):
    matching.set_tags_soundex_length(soundex_length)
    return matching.soundex_tags_match(tags)

def fuzzy_tags_match(tags, mi, **kwargs):
    return matching.fuzzy_tags_match(tags)

#====================
# Algorithm Factories
#====================

def identical_algorithm_factory(field, db, reverse=False):
    return globals()['identical_{}_match'.format(get_cols(db)[field]['delegate'])]

def similar_algorithm_factory(field, db, reverse=False):
    if reverse:
        return globals()['rev_similar_{}_match'.format(get_cols(db)[field]['delegate'])]
    else:
        return globals()['similar_{}_match'.format(get_cols(db)[field]['delegate'])]

def soundex_algorithm_factory(field, db, reverse=False):
    if reverse:
        return globals()['rev_soundex_{}_match'.format(get_cols(db)[field]['delegate'])]
    else:
        return globals()['soundex_{}_match'.format(get_cols(db)[field]['delegate'])]

def fuzzy_algorithm_factory(field, db, reverse=False):
    return globals()['fuzzy_{}_match'.format(get_cols(db)[field]['delegate'])]

#====================

PLUGIN_ALGORITHMS = OrderedDict()

PLUGIN_ALGORITHMS[_('Identical Match')] = {
    'function': identical_algorithm_factory,
    'description': _('Case insensitive exact match'),
    'is_factory': True
}

PLUGIN_ALGORITHMS[_('Similar Match')] = {
    'function': similar_algorithm_factory,
    'description': _('Removal of common punctuation and prefixes'),
    'is_factory': True,
    'reverse': True
}

PLUGIN_ALGORITHMS[_('Soundex Match')] = {
    'function': soundex_algorithm_factory,
    'description': _('Phonetic representation of names'),
    'is_factory': True,
    'settings_metadata': [
            {
            'name': 'soundex_length',
            'label': _('Soundex length'),
            'type': 'int',
            'value': 6,
            'range': (1,100)
        }
    ],
    'reverse': True
}

PLUGIN_ALGORITHMS[_('Fuzzy Match')] = {
    'function': fuzzy_algorithm_factory,
    'description': _("Remove all punctuation, subtitles and any words after 'and', 'or' or 'aka'"),
    'is_factory': True
}


_all_algorithms = OrderedDict()
for k in PLUGIN_ALGORITHMS.keys():
    _all_algorithms[k] = PLUGIN_ALGORITHMS[k]
    _all_algorithms[k]['type'] = 'PI'

## enable user defined functions {
## DISCLAIMER: UNCOMMENT AND RUN THIS CODE AT YOUR OWN RISK
#try:
#    import os, sys
#    mod_path = os.environ.get('CALIBRE_FD_USER')
#    if mod_path and os.path.exists(mod_path):
#        sys.path.append(mod_path)
#        from fd_user_defined import USER_ALGORITHMS
#        # USER_ALGORITHMS should follow the format of PLUGIN_ALGORITHMS.
#        # user defined functions have this signature: func(val, mi, **kwargs).
#        # Any additional options are added before kwargs and must have a default value
#        # e.g. soundex_tags_match(tags, mi, soundex_length=4, **kwargs)
#        # These additional settings are presented to the user through the settings button
#        # For more on this, look at how soundex match define this in PLUGIN_ALGORITHMS
#        # Also have a look at SettingsDialog for types supported.
#        # Factories have different signature func(field_name, db).
#        # Factories are used for builtin algorithms as the original plugin defines
#        # different functions for different columns. Factories produces the appropriate
#        # function at runtime based on the selected column.
#        for k in USER_ALGORITHMS.keys():
#            if k not in PLUGIN_ALGORITHMS.keys():
#                _all_algorithms[k] = USER_ALGORITHMS[k]
#                _all_algorithms[k]['type'] = 'USER'
#except Exception as e:
#    print(e)
##}
