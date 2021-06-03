#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

import re
import traceback
import copy

# python3 compatibility
from six.moves import range
from six import text_type as unicode, string_types as basestring

from calibre import prints
from calibre.constants import DEBUG

from calibre_plugins.find_duplicates.advanced.algorithms import _all_algorithms
from calibre_plugins.find_duplicates.advanced.common import (get_cols, truncate, STANDARD_FIELD_KEYS)
from calibre_plugins.find_duplicates.advanced.templates import (check_template, TEMPLATE_PREFIX, TEMPLATE_ERROR)

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/match_rules.py - exception when loading translations")
    pass


def check_match_rule(match_rule, possible_cols, db, target_db, all_algorithms, gui):
    '''
    check match rule for errors, and produce new match rule containing the remaining
    valid fields and algorithms.
    also produce dict detailing errors found
    '''
    book_id = list(db.all_ids())[0]
    mi = db.new_api.get_proxy_metadata(book_id)
    new_match_rule = {
        'algos': [],
        'multiply': match_rule.get('multiply', True),
        'composite_has_names': match_rule.get('composite_has_names', False)
    }
    errors = {
        'field': '',
        'missing_functions': set(),
        'error_functions': set(),
        'templates': set()
    }
    has_errors = False
    algo_dicts = match_rule['algos']
    field = match_rule['field']
    if field in possible_cols.keys():
        new_match_rule['field'] = field
    else:
        errors['field'] = field
        has_errors = True
        if DEBUG:
            if not field:
                prints('Find Duplicates: Match rule has no field')
            else:
                prints('Find Duplicates: cannot add column to match rule: {}, possible columns: {}'.format(field, possible_cols.keys()))
    for algo_dict in algo_dicts:
        name = algo_dict['name']
        settings = algo_dict.get('settings')
        # test it is function not a template
        if name in all_algorithms.keys():
            # match_rules is json serializable, does not contain function objects, so insert them now
            # and if any of the functions is a factory, run it to get the underlying algorithm function object
            function = all_algorithms[name]['function']
            if all_algorithms[name]['is_factory']:
                function = function(field if field in possible_cols else 'title', db)
            # test the function
            try:
               function('random_text', mi, **settings)
               new_match_rule['algos'].append({'name': name, 'settings': settings})
            except Exception as e:
               errors['error_functions'].add(name)
               has_errors = True
               if DEBUG:
                prints('Find Duplicates: error running function: {} with settings: {}, return this exception: {}'.format(function.__name__, settings, e))
        # could be a template.
        elif name.startswith(TEMPLATE_PREFIX):
            is_success, all_errors = check_template(name.lstrip(TEMPLATE_PREFIX), db, gui, target_db, print_error=False)
            if is_success:
                new_match_rule['algos'].append({'name': name, 'settings': settings})
            else:
                errors['templates'].add(name)
                has_errors = True
                if DEBUG:
                    prints('Find Duplicates: tepmlate: "{}" returned this error: {}'.format(name, all_errors))
        # must be a user function that is no longer there
        else:
            errors['missing_functions'].add(name)
            has_errors = True
            if DEBUG:
                prints('Find Duplicates: cannot find function: {}'.format(name))
    return new_match_rule, has_errors, errors

def parse_match_rule_errors(errors, idx):
    msg = _('Errors for match:') + '\n'
    sep = '\n   • '
    if idx:
        msg = _('Errors for match rule no. {}:').format(idx) + '\n'
    field = errors.get('field')
    if field:
        msg += ' ‣' + _('Column "{}" cannot be added to match rule').format(field) + '\n'
    missing_functions = errors['missing_functions']
    if missing_functions:
        msg += ' ‣' + _('The following functions are missing and cannot be restored:{}{}').format(sep, sep.join(list(missing_functions))) + '\n'
    error_functions = errors['error_functions']
    if error_functions:
        msg += ' ‣' + _('Encountered errors while running the following functions:{}{}').format(sep, sep.join(list(error_functions))) + '\n'
    error_templates = errors['templates']
    if error_templates:
        msg += ' ‣' + _('Encountered errors while running the following templates:{}{}').format(sep, sep.join(list(error_templates))) + '\n'
    return msg


def process_match_rules(match_rules, db, possible_cols):
    '''
    get the non serializable objects like functions.
    run the factories to get the real functions they encapsulate.
    determine the exemptions type.
    '''
    exemptions_type = 'book'
    flags = {}
    #fetch_mi flag will be set to True only if the match rules contain any templates, or
    #if one of the match functions as the attribute _all_algorithms[match_function]['uses_mi'] set to true
    #this is done to save performance in case we don't need mi object
    flags['fetch_mi'] = False
    fields_set = set()
    for match_rule in match_rules[:]:
        algo_dicts = match_rule['algos']
        field = match_rule['field']
        fields_set.add(field)
        if field not in STANDARD_FIELD_KEYS:
            flags['has_custom_fields'] = True
        for algo_dict in algo_dicts:
            name = algo_dict['name']
            # test it is function not a template
            if name in _all_algorithms.keys():
                if _all_algorithms[name].get('uses_mi'):
                    flags['fetch_mi'] = True
                function = _all_algorithms[name]['function']
                if _all_algorithms[name]['is_factory']:
                    # for composite cols with names, we pass authors to the factory to get the correct function {
                    if match_rule.get('composite_has_names'):
                        function = function('authors', db)
                    #}
                    else:
                        function = function(field, db)
                algo_dict['function'] = function
            else:
                # must be a template
                flags['fetch_mi'] = True
    if len(fields_set) == 1:
        field = list(fields_set)[0]
        if possible_cols[field].get('is_catetory'):
            # TODO: implement an author only like match algorithm
            pass
        if field == 'authors':
            exemptions_type = 'author'

    return match_rules, flags, exemptions_type

def add_reversed_rules(match_rules, db, possible_cols):
    '''
    match rules that contain algothims that should produce rev_ahash (similar_authors, soundex_authors)
    will be copied, replacing the algorithm with its reversed counter algorithm, leaving all other 
    algorithms/templates that does pre/post processing the same
    '''
    # detect match rules that needs copying
    cp = []
    for match_rule in match_rules:
        algo_dicts = match_rule['algos']
        field = match_rule['field']
        if possible_cols[field]['delegate'] != 'authors':
            # check no composite fields with names (we cannot know these in advance to set the delegate flag)
            if not match_rule.get('composite_has_names'):
                continue
        for algo_dict in algo_dicts:
            name = algo_dict['name']
            # test it is function not a template
            if name in _all_algorithms.keys():
                if _all_algorithms[name].get('reverse'):
                    cp.append(copy.deepcopy(match_rule))
                    break
    #
    for match_rule in cp:
        algo_dicts = match_rule['algos']
        field = match_rule['field']
        for algo_dict in algo_dicts:
            name = algo_dict['name']
            # test it is function not a template
            if name in _all_algorithms.keys():
                if _all_algorithms[name]['is_factory']:
                    function = _all_algorithms[name]['function']
                    # this time we call factories with reverse flag set to True to get reverse function
                    # for composite cols with names, we pass authors to the factory to get the correct function {
                    if match_rule.get('composite_has_names'):
                        function = function('authors', db, reverse=True)
                    #}
                    else:
                        function = function(field, db, reverse=True)
                algo_dict['function'] = function

    # add new reversed match rules to match rules
    match_rules += cp
    return match_rules
