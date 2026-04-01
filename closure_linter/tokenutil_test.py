#!/usr/bin/env python
#
# Copyright 2012 The Closure Linter Authors. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the scopeutil module."""

# Allow non-Google copyright
# pylint: disable=g-bad-file-header

__author__ = ('nnaze@google.com (Nathan Naze)')

import unittest as googletest

from closure_linter import ecmametadatapass
from closure_linter import javascripttokens
from closure_linter import testutil
from closure_linter import tokenutil


class FakeToken(object):
  pass


class TokenUtilTest(googletest.TestCase):

  def testGetTokenRange(self):

    a = FakeToken()
    b = FakeToken()
    c = FakeToken()
    d = FakeToken()
    e = FakeToken()

    a.next = b
    b.next = c
    c.next = d

    self.assertEqual([a, b, c, d], tokenutil.GetTokenRange(a, d))

    # This is an error as e does not come after a in the token chain.
    self.assertRaises(Exception, lambda: tokenutil.GetTokenRange(a, e))

  def testTokensToString(self):

    a = FakeToken()
    b = FakeToken()
    c = FakeToken()
    d = FakeToken()
    e = FakeToken()

    a.string = 'aaa'
    b.string = 'bbb'
    c.string = 'ccc'
    d.string = 'ddd'
    e.string = 'eee'

    a.line_number = 5
    b.line_number = 6
    c.line_number = 6
    d.line_number = 10
    e.line_number = 11

    self.assertEqual(
        'aaa\nbbbccc\n\n\n\nddd\neee',
        tokenutil.TokensToString([a, b, c, d, e]))

    self.assertEqual(
        'ddd\neee\naaa\nbbbccc',
        tokenutil.TokensToString([d, e, a, b, c]),
        'Neighboring tokens not in line_number order should have a newline '
        'between them.')

  def testGetPreviousCodeToken(self):

    tokens = testutil.TokenizeSource("""
start1. // comment
    /* another comment */
    end1
""")

    def _GetTokenStartingWith(token_starts_with):
      for t in tokens:
        if t.string.startswith(token_starts_with):
          return t

    self.assertEqual(
        None,
        tokenutil.GetPreviousCodeToken(_GetTokenStartingWith('start1')))

    self.assertEqual(
        '.',
        tokenutil.GetPreviousCodeToken(_GetTokenStartingWith('end1')).string)

    self.assertEqual(
        'start1',
        tokenutil.GetPreviousCodeToken(_GetTokenStartingWith('.')).string)

  def testGetNextCodeToken(self):

    tokens = testutil.TokenizeSource("""
start1. // comment
    /* another comment */
    end1
""")

    def _GetTokenStartingWith(token_starts_with):
      for t in tokens:
        if t.string.startswith(token_starts_with):
          return t

    self.assertEqual(
        '.',
        tokenutil.GetNextCodeToken(_GetTokenStartingWith('start1')).string)

    self.assertEqual(
        'end1',
        tokenutil.GetNextCodeToken(_GetTokenStartingWith('.')).string)

    self.assertEqual(
        None,
        tokenutil.GetNextCodeToken(_GetTokenStartingWith('end1')))

  def testGetIdentifierStart(self):

    tokens = testutil.TokenizeSource("""
start1 . // comment
    prototype. /* another comment */
    end1

['edge'][case].prototype.
    end2 = function() {}
""")

    def _GetTokenStartingWith(token_starts_with):
      for t in tokens:
        if t.string.startswith(token_starts_with):
          return t

    self.assertEqual(
        'start1',
        tokenutil.GetIdentifierStart(_GetTokenStartingWith('end1')).string)

    self.assertEqual(
        'start1',
        tokenutil.GetIdentifierStart(_GetTokenStartingWith('start1')).string)

    self.assertEqual(
        None,
        tokenutil.GetIdentifierStart(_GetTokenStartingWith('end2')))

  def testInsertTokenBefore(self):

    self.AssertInsertTokenAfterBefore(False)

  def testInsertTokenAfter(self):

    self.AssertInsertTokenAfterBefore(True)

  def AssertInsertTokenAfterBefore(self, after):

    new_token = javascripttokens.JavaScriptToken(
        'a', javascripttokens.JavaScriptTokenType.IDENTIFIER, 1, 1)

    existing_token1 = javascripttokens.JavaScriptToken(
        'var', javascripttokens.JavaScriptTokenType.KEYWORD, 1, 1)
    existing_token1.start_index = 0
    existing_token1.metadata = ecmametadatapass.EcmaMetaData()

    existing_token2 = javascripttokens.JavaScriptToken(
        ' ', javascripttokens.JavaScriptTokenType.WHITESPACE, 1, 1)
    existing_token2.start_index = 3
    existing_token2.metadata = ecmametadatapass.EcmaMetaData()
    existing_token2.metadata.last_code = existing_token1

    existing_token1.next = existing_token2
    existing_token2.previous = existing_token1

    if after:
      tokenutil.InsertTokenAfter(new_token, existing_token1)
    else:
      tokenutil.InsertTokenBefore(new_token, existing_token2)

    self.assertEqual(existing_token1, new_token.previous)
    self.assertEqual(existing_token2, new_token.next)

    self.assertEqual(new_token, existing_token1.next)
    self.assertEqual(new_token, existing_token2.previous)

    self.assertEqual(existing_token1, new_token.metadata.last_code)
    self.assertEqual(new_token, existing_token2.metadata.last_code)

    self.assertEqual(0, existing_token1.start_index)
    self.assertEqual(3, new_token.start_index)
    self.assertEqual(4, existing_token2.start_index)

  def testGetIdentifierForToken(self):

    tokens = testutil.TokenizeSource("""
start1.abc.def.prototype.
  onContinuedLine

(start2.abc.def
  .hij.klm
  .nop)

start3.abc.def
   .hij = function() {};

// An absurd multi-liner.
start4.abc.def.
   hij.
   klm = function() {};

start5 . aaa . bbb . ccc
  shouldntBePartOfThePreviousSymbol

start6.abc.def ghi.shouldntBePartOfThePreviousSymbol

var start7 = 42;

function start8() {

}

start9.abc. // why is there a comment here?
  def /* another comment */
  shouldntBePart

start10.abc // why is there a comment here?
  .def /* another comment */
  shouldntBePart

start11.abc. middle1.shouldNotBeIdentifier
""")

    def _GetTokenStartingWith(token_starts_with):
      for t in tokens:
        if t.string.startswith(token_starts_with):
          return t

    self.assertEqual(
        'start1.abc.def.prototype.onContinuedLine',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start1')))

    self.assertEqual(
        'start2.abc.def.hij.klm.nop',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start2')))

    self.assertEqual(
        'start3.abc.def.hij',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start3')))

    self.assertEqual(
        'start4.abc.def.hij.klm',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start4')))

    self.assertEqual(
        'start5.aaa.bbb.ccc',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start5')))

    self.assertEqual(
        'start6.abc.def',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start6')))

    self.assertEqual(
        'start7',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start7')))

    self.assertEqual(
        'start8',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start8')))

    self.assertEqual(
        'start9.abc.def',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start9')))

    self.assertEqual(
        'start10.abc.def',
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('start10')))

    self.assertIsNone(
        tokenutil.GetIdentifierForToken(_GetTokenStartingWith('middle1')))


if __name__ == '__main__':
  googletest.main()
