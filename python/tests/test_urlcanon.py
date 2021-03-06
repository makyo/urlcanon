# -*- coding: utf-8 -*-
'''
test_urlcanon.py - unit tests for the urlcanon package

Copyright (C) 2016-2018 Internet Archive

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import urlcanon
import os
import json
import pytest
try:
    unicode
except NameError:  # py3
    unicode = str

def load_json_bytes(json_bytes):
    '''
    The python json parser only operates on strings, not bytes. :( This
    hacky workaround is based on the observation that every possible byte
    sequence can be represented as a str by "decoding" it as ISO-8859-1. It's
    not very efficient, but oh well.
    '''
    def rebytify_data_structure(obj):
        if isinstance(obj, dict):
            bd = {}
            for orig_key in obj:
                new_key = rebytify_data_structure(orig_key)
                new_value = rebytify_data_structure(obj[orig_key])
                bd[new_key] = new_value
            return bd
        elif isinstance(obj, list):
            for i in range(len(obj)):
                obj[i] = rebytify_data_structure(obj[i])
            return obj
        elif isinstance(obj, unicode):
            try:
                return obj.encode('latin1')
            except Exception as e:
                raise Exception('%s: %s' % (repr(obj), e))
        else: # a number or None
            return obj
    obj = json.loads(json_bytes.decode('latin1'))
    return rebytify_data_structure(obj)

def test_parser_idempotence():
    path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'testdata',
            'idempotence.json')
    with open(path, 'rb') as f:
        inputs = load_json_bytes(f.read())
    for s in inputs:
        assert urlcanon.parse_url(s).__bytes__() == s

def load_funky_ipv4_data():
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata', 'funky_ipv4.json')
    with open(path, 'rb') as f:
        inputs = load_json_bytes(f.read())
        return [(unresolved, inputs[unresolved]) for unresolved in inputs]

@pytest.mark.parametrize('unresolved,expected', load_funky_ipv4_data())
def test_funky_ipv4(unresolved, expected):
    ip4 = urlcanon.parse.parse_ipv4or6(unresolved)[0]
    assert urlcanon.canon.dotted_decimal(ip4) == expected

def load_path_dots_data():
    # Most of path_dots.json was generated in the browser using this html/js.
    #
    # <html>
    # <head>
    # <title>browser url canonicalization test</title>
    # </head>
    # <body>
    # <a id='url' href='http://example.com/'>i am your link</a>
    # <script>
    # var e = document.getElementById('url');
    #
    # var SEPARATORS = ['/'];  // , '\\']
    # var SEGMENTS = ['', '.', '..', 'foo'];
    #
    # function all_the_paths(len, path) {
    #     if (path.length >= len) {
    #         var p = path.join('')
    #         e.setAttribute('href', 'http://example.com' + p);
    #         // console.log(p + ' => ' + e.pathname);
    #         console.log("assert urlcanon.canon.resolve_path_dots(b'" + p + "') == b'" + e.pathname + "'");
    #         return
    #     }
    #     path.push('');
    #     if (path.length % 2 == 1) {
    #         for (var i = 0; i < SEPARATORS.length; i++) {
    #             path[path.length-1] = SEPARATORS[i]
    #             all_the_paths(len, path)
    #         }
    #     } else {
    #         for (var i = 0; i < SEGMENTS.length; i++) {
    #             path[path.length-1] = SEGMENTS[i]
    #             all_the_paths(len, path)
    #         }
    #     }
    #     path.pop()
    # }
    #
    # for (var i = 1; i < 9; i++) {
    #     all_the_paths(i, []);
    # }
    #
    # </script>
    # </body>
    # </html>
    #
    path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'testdata',
            'path_dots.json')
    with open(path, 'rb') as f:
        inputs = load_json_bytes(f.read())
    testdata = []
    for (unresolved, expected) in inputs[b'special'].items():
        testdata.append((unresolved, True, expected))
    for (unresolved, expected) in inputs[b'nonspecial'].items():
        testdata.append((unresolved, False, expected))
    return testdata

@pytest.mark.parametrize(
        'unresolved,is_special,expected', load_path_dots_data())
def test_resolve_path_dots(unresolved, is_special, expected):
    assert urlcanon.canon.resolve_path_dots(
            unresolved, special=is_special) == expected

def load_w3c_test_data():
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata', 'urltestdata.json')
    with open(path, 'rb') as f:
        # load_json_bytes doesn't work for urltestdata.json because it contains
        # unicode character escapes beyond \u00ff such as \u0300
        tests = json.loads(f.read().decode('utf-8'))
        return sorted([(test['input'], test['href'], test) for test in tests
                       if is_absolute_url_test(test)])

def is_absolute_url_test(test):
    return (isinstance(test, dict) and test.get('base') == 'about:blank'
            and 'href' in test and test['input'][0] != '#')

@pytest.mark.parametrize("input,href,test", load_w3c_test_data())
def test_w3c_test_data(input, href, test):
    url = urlcanon.parse_url(input)
    urlcanon.whatwg(url)
    assert test['protocol'].encode('utf-8') == (
            url.scheme + url.colon_after_scheme)
    assert test['username'].encode('utf-8') == url.username
    assert test['password'].encode('utf-8') == url.password
    assert test['host'].encode('utf-8') == url.host_port
    assert test['hostname'].encode('utf-8') == url.host
    assert test['pathname'].encode('utf-8') == url.path
    assert test['search'].encode('utf-8') == (
            url.query and (url.question_mark + url.query) or b'')
    assert test['hash'].encode('utf-8') == (
            url.fragment and (url.hash_sign + url.fragment) or b'')
    assert test['href'] == unicode(url)

def load_parsing():
    path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'testdata',
            'parsing.json')
    with open(path, 'rb') as f:
        inputs = load_json_bytes(f.read())
        return sorted(inputs.items())

@pytest.mark.parametrize("input,parsed_fields", load_parsing())
def test_parsing(input, parsed_fields):
    parsed_url = urlcanon.parse_url(input)
    assert parsed_url.leading_junk == parsed_fields[b'leading_junk']
    assert parsed_url.scheme == parsed_fields[b'scheme']
    assert parsed_url.colon_after_scheme == parsed_fields[b'colon_after_scheme']
    assert parsed_url.slashes == parsed_fields[b'slashes']
    assert parsed_url.username == parsed_fields[b'username']
    assert parsed_url.colon_before_password == parsed_fields[b'colon_before_password']
    assert parsed_url.password == parsed_fields[b'password']
    assert parsed_url.at_sign == parsed_fields[b'at_sign']
    assert parsed_url.ip6 == parsed_fields[b'ip6']
    assert parsed_url.ip4 == parsed_fields[b'ip4']
    assert parsed_url.host == parsed_fields[b'host']
    assert parsed_url.colon_before_port == parsed_fields[b'colon_before_port']
    assert parsed_url.port == parsed_fields[b'port']
    assert parsed_url.path == parsed_fields[b'path']
    assert parsed_url.question_mark == parsed_fields[b'question_mark']
    assert parsed_url.query == parsed_fields[b'query']
    assert parsed_url.hash_sign == parsed_fields[b'hash_sign']
    assert parsed_url.fragment == parsed_fields[b'fragment']
    assert parsed_url.trailing_junk == parsed_fields[b'trailing_junk']
    assert parsed_url.surt_ancestry() == parsed_fields[b'surt_ancestry']


def load_supplemental_whatwg_test_data():
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata',
        'supplemental_whatwg.json')
    with open(path, 'rb') as f:
        jb = load_json_bytes(f.read())
    return sorted(jb.items())

@pytest.mark.parametrize(
        'uncanonicalized,canonicalized', load_supplemental_whatwg_test_data())
def test_supplemental_whatwg(uncanonicalized, canonicalized):
    url = urlcanon.parse_url(uncanonicalized)
    urlcanon.whatwg(url)
    assert url.__bytes__() == canonicalized

def load_ssurt_test_data(section):
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata', 'ssurt.json')
    with open(path, 'rb') as f:
        jb = load_json_bytes(f.read())
    return sorted(jb[section].items())

@pytest.mark.parametrize(
        'host,host_reversed', load_ssurt_test_data(b'reverseHost'))
def test_reverse_host(host, host_reversed):
    assert urlcanon.reverse_host(host) == host_reversed

@pytest.mark.parametrize(
        'host,ssurt_host', load_ssurt_test_data(b'ssurtHost'))
def test_ssurt_host(host, ssurt_host):
    assert urlcanon.ssurt_host(host) == ssurt_host

@pytest.mark.parametrize(
        'url,ssurt', load_ssurt_test_data(b'ssurt'))
def test_ssurt(url, ssurt):
    assert urlcanon.parse_url(url).ssurt() == ssurt

@pytest.mark.parametrize(
        'url,surt', load_ssurt_test_data(b'surt'))
def test_surt(url, surt):
    assert urlcanon.parse_url(url).surt() == surt

@pytest.mark.parametrize(
        'url,surt', load_ssurt_test_data(b'surtWithoutScheme'))
def test_surt_without_scheme(url, surt):
    assert urlcanon.parse_url(url).surt(with_scheme=False) == surt

@pytest.mark.parametrize(
        'url,surt', load_ssurt_test_data(b'surtWithoutTrailingComma'))
def test_surt_without_trailing_comma(url, surt):
    assert urlcanon.parse_url(url).surt(trailing_comma=False) == surt

def load_surt_test_data(section):
    '''
    Tests copied from
    https://github.com/internetarchive/surt/blob/master/tests/test_surt.py
    '''
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata', 'surt.json')
    with open(path, 'rb') as f:
        jb = load_json_bytes(f.read())
    return sorted(jb[section].items())

@pytest.mark.parametrize(
        'uncanonicalized,canonicalized',
        load_surt_test_data(b'google'))
def test_google_canonicalizer(uncanonicalized, canonicalized):
    url = urlcanon.parse_url(uncanonicalized)
    urlcanon.google(url)
    assert url.__bytes__() == canonicalized

def load_aggressive_test_data():
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata', 'aggressive.json')
    with open(path, 'rb') as f:
        jb = load_json_bytes(f.read())
    return sorted(jb.items())

@pytest.mark.parametrize(
        'uncanonicalized,canonicalized', load_aggressive_test_data())
def test_aggressive(uncanonicalized, canonicalized):
    url = urlcanon.parse_url(uncanonicalized)
    # if uncanonicalized == b'  https://www.google.com/  ':
    #     import pdb; pdb.set_trace()
    urlcanon.aggressive(url)
    assert url.__bytes__() == canonicalized

def load_semantic_precise_test_data():
    path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'testdata',
        'semantic_precise.json')
    with open(path, 'rb') as f:
        jb = load_json_bytes(f.read())
    return sorted(jb.items())

@pytest.mark.parametrize(
        'uncanonicalized,canonicalized', load_semantic_precise_test_data())
def test_semantic_precise(uncanonicalized, canonicalized):
    url = urlcanon.parse_url(uncanonicalized)
    urlcanon.semantic_precise(url)
    assert url.__bytes__() == canonicalized

def test_normalize_host():
    assert urlcanon.normalize_host('EXAMPLE.Com') == b'example.com'
    assert urlcanon.normalize_host('₹.com') == b'xn--yzg.com'
    assert urlcanon.normalize_host('XN--fa-Hia.de..') == b'xn--fa-hia.de'
    assert urlcanon.normalize_host('☕.de') == b'xn--53h.de'
    assert urlcanon.normalize_host(
            '日本⒈co．jp') == b'%E6%97%A5%E6%9C%AC%E2%92%88co%EF%BC%8Ejp'
    assert urlcanon.normalize_host('☃.net') == b'xn--n3h.net'
    assert urlcanon.normalize_host('%e2%98%83.n%45t') == b'xn--n3h.net'
    assert urlcanon.normalize_host('%25e2%98%%383.N%45t') == b'xn--n3h.net'
    # XXX some test cases from http://unicode.org/cldr/utility/idna.jsp
    # don't work. python needs an implementation of uts46
    # assert urlcanon.normalize_host('Faß.de') == b'fass.de'
    # assert urlcanon.normalize_host('σόλος.gr') == b'xn--wxaikc6b.gr'
    # assert urlcanon.normalize_host('Σόλος.gr') == b'xn--wxaikc6b.gr'
    # assert urlcanon.normalize_host(
    #         'ΣΌΛΟΣ.grﻋﺮﺑﻲ.de') == b'xn--wxaikc6b.xn--gr-gtd9a1b0g.de'

## # XXX these are "parsing" tests from the surt library, change to
## # canonicalization tests, which canonicalizer?
## assert handyurl.parse("http:////////////////www.vikings.com").geturl() == 'http://www.vikings.com/'
## assert handyurl.parse("http://https://order.1and1.com").geturl() == 'https://order.1and1.com'
## assert handyurl.parse("http://mineral.galleries.com:/minerals/silicate/chabazit/chabazit.htm").geturl() == 'http://mineral.galleries.com/minerals/silicate/chabazit/chabazit.htm'
