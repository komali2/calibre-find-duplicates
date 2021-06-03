#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2020, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict, defaultdict
import copy

# python3 compatibility
from six import text_type as unicode
from six import string_types as basestring

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.ebooks.metadata.book.base import Metadata

from calibre_plugins.find_duplicates.book_algorithms import AlgorithmBase
import calibre_plugins.find_duplicates.config as cfg
from calibre_plugins.find_duplicates.advanced.common import to_list, algorithm_caller, get_field_value, composite_to_list
from calibre_plugins.find_duplicates.advanced.templates import TEMPLATE_PREFIX, TEMPLATE_ERROR

try:
    load_translations()
except NameError:
    prints("FindDuplicates::advanced/hash_functions.py - exception when loading translations")
    pass

class HashFuncs(object):

    def book_metadata_hash(self, db, book_id, match_rules, mi):
        '''
        Take an iterable of match rules for duplicate processing.
        Each match rule specify one or more algorithms (or templates) to act on a certain field.
        All the algorithms/templates in a matching rule act on the same field successivley, handing
        the generated hash to the next algorithm/template to act on.
        For fields with multiple items, unless the multiply flag is turned off, each
        item is processed by the algorithms/templates separately, producing one hash for each item.
        In the end results of all the match rules are combined into one or more
        hashes depending on the muliply flag for multiple item fields.
        '''
        all_metadata = db.field_metadata.all_metadata()
        hash_string = ''
        hash_multipliers = OrderedDict()
        for match_rule in match_rules:
            field_name = match_rule['field']
            multiply = match_rule['multiply']
            algo_dicts = match_rule['algos']
            composite_has_names = match_rule.get('composite_has_names')
            # this flag is used for composite columns with multiple items to determine the separator
            field_value = self.get_field_value(book_id, db, field_name, mi)
            if composite_has_names:
                field_value = composite_to_list(field_name, field_value, db, composite_has_names)
            
            is_multiple = all_metadata[field_name]['is_multiple'] != {}
            if is_multiple:
                hashes_to_join = set()
                if multiply and not hash_multipliers.get(field_name):
                    hash_multipliers[field_name] = set()
                for item in field_value:
                    item_hash = item.strip()
                    for algo_dict in algo_dicts:
                        name = algo_dict['name']
                        func = algo_dict.get('function') or name
                        settings = algo_dict['settings']
                        item_hash = self.algorithm_caller(func, field_name, item_hash, all_metadata, mi, settings)
                    if item_hash:
                        if multiply:
                            if DEBUG:
                                item_hash = '|{}:{}|'.format(field_name, item_hash)
                            hash_multipliers[field_name].add(item_hash)
                        else:
                            hashes_to_join.add(item_hash)
                            
                # join hashes for field with multiple items (author, tag ... etc) if multiply was set to False
                if len(hashes_to_join) > 0:
                    hash_ = '|'.join(sorted(hashes_to_join))
                    if DEBUG:
                        hash_ = '|{}:{}|'.format(field_name, hash_)
                    hash_string += hash_
                    
            else:
                if field_value:
                    hash_ = unicode(field_value)
                    for algo_dict in algo_dicts:
                        name = algo_dict['name']
                        func = algo_dict.get('function') or name
                        settings = algo_dict['settings']
                        hash_ = self.algorithm_caller(func, field_name, hash_, all_metadata, mi, settings)
                    if DEBUG:
                        hash_ = '|{}:{}|'.format(field_name, hash_)
                    if hash_:
                        hash_string += hash_

            # templates change the field_vlaue inside mi, restore it for later match_rules that might
            # need to do conditional matching based on this field value
            setattr(mi, field_name, field_value)
                    
        # multiply the generated hash by hashes generated by fields with multiple items whose multiply flag is set to True
        all_hashes = set()
        all_hashes.add(hash_string)
        for mf_hashes in hash_multipliers.values():
            new_hashes = set()
            for mf_hash in mf_hashes:
                for hash_ in all_hashes:
                    new_hash = hash_ + mf_hash
                    new_hashes.add(new_hash)
            all_hashes = new_hashes
    #    if DEBUG:
    #        prints('Find Duplicates: Hashes for book_id ({}): {}'.format(book_id, all_hashes))
        return all_hashes

    def metadata_item_hash(self, match_rules, all_metadata, item_text):
        '''
        This functions operates on metadata item like author, tag, ... etc
        Each match rule specify one or more algorithms to act on a certain field.
        All the algorithms in a matching rule act on the same field successivley, handing
        the generated hash to the next algorithm to act on.
        '''
        # we have either one match rule, or two (the second being the rule to generate rev_hash)
        hashes = []
        for match_rule in match_rules:
            field_name = match_rule['field']
            algo_dicts = match_rule['algos']
            
            hash_ = unicode(item_text)
            
            # create a mi instance to persist the hash value for templates to read from
            # if no templates, set it to None to save performance
            mi = Metadata(_('Unknown'))
            setattr(mi, field_name, hash_)
            
            for algo_dict in algo_dicts:
                name = algo_dict['name']
                func = algo_dict.get('function') or name
                settings = algo_dict['settings']
                hash_ = self.algorithm_caller(func, field_name, hash_, all_metadata, mi, settings)

            hashes.append(hash_)

        if len(hashes) == 1:
            # no rule for rev_hash
            hashes.append(None)

        return hashes

    def algorithm_caller(self, func, field_name, hash_, all_metadata, mi, settings):
        return algorithm_caller(func, field_name, hash_, all_metadata, mi, settings)

    def get_field_value(self, book_id, db, field_name, mi):
        return get_field_value(book_id, db, field_name, mi)