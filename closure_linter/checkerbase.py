#!/usr/bin/env python
#
# Copyright 2008 The Closure Linter Authors. All Rights Reserved.
#
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

"""Base classes for writing checkers that operate on tokens."""

# Allow non-Google copyright
# pylint: disable=g-bad-file-header

__author__ = ('robbyw@google.com (Robert Walker)',
              'ajp@google.com (Andy Perelson)',
              'jacobr@google.com (Jacob Richman)')

import time

from closure_linter import errorrules
from closure_linter.common import error

from closure_linter import javascripttokens

Type = javascripttokens.JavaScriptTokenType

class LintRulesBase(object):
  """Base class for all classes defining the lint rules for a language."""

  def __init__(self):
    self.__checker = None
    
    self._stats = Stats()
    self._error_stats = errorCount()

  def Initialize(self, checker, limited_doc_checks, is_html):
    """Initializes to prepare to check a file.

    Args:
      checker: Class to report errors to.
      limited_doc_checks: Whether doc checking is relaxed for this file.
      is_html: Whether the file is an HTML file with extracted contents.
    """
    self.__checker = checker
    self._limited_doc_checks = limited_doc_checks
    self._is_html = is_html

  def _HandleError(self, code, message, token, position=None,
                   fix_data=None):
    """Call the HandleError function for the checker we are associated with."""
    if errorrules.ShouldReportError(code):
      self.__checker.HandleError(code, message, token, position, fix_data)

  def _SetLimitedDocChecks(self, limited_doc_checks):
    """Sets whether doc checking is relaxed for this file.

    Args:
      limited_doc_checks: Whether doc checking is relaxed for this file.
    """
    self._limited_doc_checks = limited_doc_checks

  def CheckToken(self, token, parser_state):
    """Checks a token, given the current parser_state, for warnings and errors.

    Args:
      token: The current token under consideration.
      parser_state: Object that indicates the parser state in the page.

    Raises:
      TypeError: If not overridden.
    """
    raise TypeError('Abstract method CheckToken not implemented')

  def Finalize(self, parser_state):
    """Perform all checks that need to occur after all lines are processed.

    Args:
      parser_state: State of the parser after parsing all tokens

    Raises:
      TypeError: If not overridden.
    """
    raise TypeError('Abstract method Finalize not implemented')


class Stats(object):
  #stats to collect code indicators
  def __init__(self):
    #initialize some variables
    self.num_function_declare = 0
    self.num_function_formal = 0
    self.function_no_name = 0
    self.function_token_names = []
    self.variable_names = []
    self.function_state_names = []
    self.function_stats = {}
    self.block_stats = []
    self.indent_stats = []

    self.comma_count = 0
    self.comma_space_before = 0
    self.comma_space_after = 0

    self.colon_count = 0
    self.colon_space_before = 0
    self.colon_space_after = 0

    self.operator_count = 0
    self.operator_space_before = 0
    self.operator_space_after = 0

    self.start_paren_count = 0
    self.start_paren_space_before = 0
    self.start_paren_space_after = 0
    self.end_paren_count = 0
    self.end_paren_space_before = 0
    self.end_paren_space_after = 0

    self.start_block_count = 0
    self.start_block_space_before = 0
    self.start_block_space_after = 0
    self.end_block_count = 0
    self.end_block_space_before = 0
    self.end_block_space_after = 0

    #block/brace style/position
    self.start_block_alone = 0
    self.start_block_begin = 0
    self.start_block_end = 0
    self.start_block_mid = 0

    self.end_block_alone = 0
    self.end_block_begin = 0
    self.end_block_begin_nocode = 0
    self.end_block_end = 0
    self.end_block_end_nocode = 0
    self.end_block_mid = 0

    self.block_comment_space = 0
    self.single_comment_space = 0

    #all include comments
    self.line_count_all_total = 0
    self.line_length_all_total = 0
    #not include comments
    self.line_count_total = 0
    self.line_length_total = 0
    #meaningful ones
    self.line_count_pure = 0
    self.line_length_pure = 0

    self.white_space_count = 0
    self.white_space_total = 0
    self.white_space_list = []

    self.single_quote_count = 0
    self.double_quote_count = 0

    self.block_comment_count = 0
    self.block_comment_line = 0
    self.single_comment_count = 0
    self.inline_comment_count = 0
    self.doc_comment_count = 0
    self.doc_comment_line = 0

    self.op_dot_count = 0
    self.op_dot_begin = 0
    self.op_dot_end = 0

    self.op_split_begin = 0
    self.op_split_end = 0

    self.blank_line_count = 0

    self.end_new_line = 1

    #keyword choice
    self.keyword_if = 0
    self.keyword_switch = 0
    self.keyword_for = 0
    self.keyword_while = 0
    self.keyword_do = 0

    #keyword count
    self.keyword_try = 0
    self.keyword_catch = 0
    self.keyword_const = 0
    self.keyword_default = 0
    self.keyword_continue = 0
    self.keyword_delete = 0
    self.keyword_goto = 0
    self.keyword_with = 0
    self.keyword_package = 0
    self.keyword_return = 0
    self.keyword_throw = 0
    self.keyword_typeof = 0

    self.has_copyright = 0

    self.code_block_complete = 1

class errorCount(object):
  #some errors can be counted for potential use
  def __init__(self):
    #initialize some variables
    self.comma_error = 0
    self.semicolon_error = 0
    self.space_error = 0
    self.doc_error = 0
    self.operator_error = 0


class CheckerBase(object):
  """This class handles checking a LintRules object against a file."""

  def __init__(self, error_handler, lint_rules, state_tracker):
    """Initialize a checker object.

    Args:
      error_handler: Object that handles errors.
      lint_rules: LintRules object defining lint errors given a token
        and state_tracker object.
      state_tracker: Object that tracks the current state in the token stream.

    """
    self._error_handler = error_handler
    self._lint_rules = lint_rules
    self._state_tracker = state_tracker 

    self._has_errors = False

  def HandleError(self, code, message, token, position=None,
                  fix_data=None):
    """Prints out the given error message including a line number.

    Args:
      code: The error code.
      message: The error to print.
      token: The token where the error occurred, or None if it was a file-wide
          issue.
      position: The position of the error, defaults to None.
      fix_data: Metadata used for fixing the error.
    """
    self._has_errors = True
    self._error_handler.HandleError(
        error.Error(code, message, token, position, fix_data))

  def HasErrors(self):
    """Returns true if the style checker has found any errors.

    Returns:
      True if the style checker has found any errors.
    """
    return self._has_errors

  def Check(self, start_token, limited_doc_checks=False, is_html=False,
            stop_token=None):
    """Checks a token stream, reporting errors to the error reporter.

    Args:
      start_token: First token in token stream.
      limited_doc_checks: Whether doc checking is relaxed for this file.
      is_html: Whether the file being checked is an HTML file with extracted
          contents.
      stop_token: If given, check should stop at this token.
    """

    self._lint_rules.Initialize(self, limited_doc_checks, is_html)
    self._ExecutePass(start_token, self._LintPass, stop_token=stop_token)
    self._lint_rules.Finalize(self._state_tracker)

  def _LintPass(self, token):
    """Checks an individual token for lint warnings/errors.

    Used to encapsulate the logic needed to check an individual token so that it
    can be passed to _ExecutePass.

    Args:
      token: The token to check.
    """
    self._lint_rules.CheckToken(token, self._state_tracker)

  def _ExecutePass(self, token, pass_function, stop_token=None):
    """Calls the given function for every token in the given token stream.

    As each token is passed to the given function, state is kept up to date and,
    depending on the error_trace flag, errors are either caught and reported, or
    allowed to bubble up so developers can see the full stack trace. If a parse
    error is specified, the pass will proceed as normal until the token causing
    the parse error is reached.

    Args:
      token: The first token in the token stream.
      pass_function: The function to call for each token in the token stream.
      stop_token: The last token to check (if given).

    Raises:
      Exception: If any error occurred while calling the given function.
    """

    self._state_tracker.Reset()
    while token:
      # When we are looking at a token and decided to delete the whole line, we
      # will delete all of them in the "HandleToken()" below.  So the current
      # token and subsequent ones may already be deleted here.  The way we
      # delete a token does not wipe out the previous and next pointers of the
      # deleted token.  So we need to check the token itself to make sure it is
      # not deleted.
      if not token.is_deleted:
        # End the pass at the stop token
        if stop_token and token is stop_token:
          return
        #state_time = time.time()
        
        #if there is something wrong in block token state - usually pop issue
        #if cannot pop, just ignore - only wrong depth and length stats
        #disable the metrics on function length/depth and block depth
        #the error indicator, default 1
        code_block_complete = 1
        try:
          self._state_tracker.HandleToken(
              token, self._state_tracker.GetLastNonSpaceToken())
        except:
          code_block_complete = 0  
        #check_time = time.time()
        #print (check_time - state_time)
        pass_function(token)
        #print (time.time() - check_time)
        try:
          self._state_tracker.HandleAfterToken(token)
        except:
          code_block_complete = 0

        if code_block_complete == 0:
          #this will suggest a block error in the code
          self._lint_rules._stats.code_block_complete = 0

      token = token.next
    
    #get function stats here for better calculation
      
    for function_obj in self._state_tracker._function_close:
      #collect function name
      function_name = function_obj.name
      if function_name not in list(self._lint_rules._stats.function_stats.keys()):
        #at this time, can only collect function names, full tokens haven't been parsed
        function_start_token = function_obj.start_token
        function_end_token = function_obj.end_token
        #do this only when tokens are collected
        if function_start_token is not None and function_end_token is not None:
          #get number of lines in function
          total_lines = function_end_token.line_number - function_start_token.line_number + 1
          blank_lines = 0
          comment_lines = 0
          loop_token = function_start_token
          #search for lines that should not be counted
          while loop_token != function_end_token:
            if loop_token.type == Type.BLANK_LINE:
              blank_lines += 1
            if loop_token.type == Type.START_SINGLE_LINE_COMMENT:
              if loop_token.IsFirstInLine() or (loop_token.previous.type == Type.WHITESPACE and loop_token.previous.IsFirstInLine()):
                comment_lines += 1
            loop_token = loop_token.next
          self._lint_rules._stats.function_stats[function_name] = {}

          self._lint_rules._stats.function_stats[function_name]['total_lines'] = total_lines
          self._lint_rules._stats.function_stats[function_name]['pure_lines'] = total_lines - blank_lines - comment_lines
          #function_depth
          self._lint_rules._stats.function_stats[function_name]['block_depth'] = function_obj.block_depth    

    #print some stats to check
    #for v,s in vars(self._lint_rules._stats).items():
    #  print v
    #  print s
    #for v,s in vars(self._lint_rules._error_stats).items():
    #  print v
    #  print s
    #print len(self._state_tracker._function_close)
    #print len(self._lint_rules._stats.function_state_names)
    #print len(self._lint_rules._stats.function_stats.keys())
    #for f in self._state_tracker._function_close:
    #  print f