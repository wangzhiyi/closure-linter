#!/usr/bin/env python
# Copyright 2007 The Closure Linter Authors. All Rights Reserved.
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

"""Checks JavaScript files for common style guide violations.

gjslint.py is designed to be used as a PRESUBMIT script to check for javascript
style guide violations.  As of now, it checks for the following violations:

  * Missing and extra spaces
  * Lines longer than 80 characters
  * Missing newline at end of file
  * Missing semicolon after function declaration
  * Valid JsDoc including parameter matching

Someday it will validate to the best of its ability against the entirety of the
JavaScript style guide.

This file is a front end that parses arguments and flags.  The core of the code
is in tokenizer.py and checker.py.
"""

from __future__ import division

__author__ = ('robbyw@google.com (Robert Walker)',
              'ajp@google.com (Andy Perelson)',
              'nnaze@google.com (Nathan Naze)',)

import errno
import itertools
import os
import platform
import re
import sys
import time
import mysql.connector

import gflags as flags

from closure_linter import errorrecord
from closure_linter import runner
from closure_linter.common import erroraccumulator
from closure_linter.common import simplefileflags as fileflags

# Attempt import of multiprocessing (should be available in Python 2.6 and up).
try:
  # pylint: disable=g-import-not-at-top
  import multiprocessing
except ImportError:
  multiprocessing = None

FLAGS = flags.FLAGS
flags.DEFINE_boolean('unix_mode', False,
                     'Whether to emit warnings in standard unix format.')
flags.DEFINE_boolean('beep', True, 'Whether to beep when errors are found.')
flags.DEFINE_boolean('time', True, 'Whether to emit timing statistics.')
flags.DEFINE_boolean('quiet', False, 'Whether to minimize logged messages. '
                     'Most useful for per-file linting, such as that performed '
                     'by the presubmit linter service.')
#@zhiyiadd - by default check html
flags.DEFINE_boolean('check_html', True,
                     'Whether to check javascript in html files.')
flags.DEFINE_boolean('summary', False,
                     'Whether to show an error count summary.')
flags.DEFINE_list('additional_extensions', None, 'List of additional file '
                  'extensions (not js) that should be treated as '
                  'JavaScript files.')
flags.DEFINE_boolean('multiprocess',
                     platform.system() is 'Linux' and bool(multiprocessing),
                     'Whether to attempt parallelized linting using the '
                     'multiprocessing module.  Enabled by default on Linux '
                     'if the multiprocessing module is present (Python 2.6+). '
                     'Otherwise disabled by default. '
                     'Disabling may make debugging easier.')
flags.ADOPT_module_key_flags(fileflags)
flags.ADOPT_module_key_flags(runner)


GJSLINT_ONLY_FLAGS = ['--unix_mode', '--beep', '--nobeep', '--time',
                      '--check_html', '--summary', '--quiet']



def _MultiprocessCheckPaths(paths):
  """Run _CheckPath over mutltiple processes.

  Tokenization, passes, and checks are expensive operations.  Running in a
  single process, they can only run on one CPU/core.  Instead,
  shard out linting over all CPUs with multiprocessing to parallelize.

  Args:
    paths: paths to check.

  Yields:
    errorrecord.ErrorRecords for any found errors.
  """

  pool = multiprocessing.Pool()

  path_results = pool.imap(_CheckPath, paths)
  for results in path_results:
    for result in results:
      yield result

  # Force destruct before returning, as this can sometimes raise spurious
  # "interrupted system call" (EINTR), which we can ignore.
  try:
    pool.close()
    pool.join()
    del pool
  except OSError as err:
    if err.errno is not errno.EINTR:
      raise err


def _CheckPaths(paths, project_argv):
  """Run _CheckPath on all paths in one thread.

  Args:
    paths: paths to check.

  Yields:
    errorrecord.ErrorRecords for any found errors.
  """

  style_metric_list = []
  file_num = 0

  for path in paths:
    file_num += 1
    if len(project_argv) == 2:
      project_argv.append(file_num)
    else:  
      project_argv[2] = file_num
    #print project_argv
    results, style_metric, min_file = _CheckPath(path, project_argv)
    if min_file == 0:
      style_metric_list.append(style_metric)
    #for record in results:
    #  yield record

  return style_metric_list


def _CheckPath(path, project_argv):
  """Check a path and return any errors.

  Args:
    path: paths to check.

  Returns:
    A list of errorrecord.ErrorRecords for any found errors.
  """

  #print path
  #min_file will try to cover both min.js and error code

  min_file = 0

  error_handler = erroraccumulator.ErrorAccumulator()
  file_stats, stats, error_stats = runner.Run(path, error_handler)

  if stats is None and error_stats is None:
    #if returned None
    min_file = 1
    style_metric = []
    make_error_record = lambda err: errorrecord.MakeErrorRecord(path, err)
    return map(make_error_record, error_handler.GetErrors()), style_metric, min_file
  
  '''
  print file_stats
  for v,s in vars(stats).items():
    print v
    print s
  
  for v,s in vars(error_stats).items():
    print v
    print s
  '''
  
  #now everything is collected here
  #do some analysis and create a record/vector

  style_metric = _SaveData(file_stats, stats, error_stats, project_argv)

  #print style_metric

  make_error_record = lambda err: errorrecord.MakeErrorRecord(path, err)
  return map(make_error_record, error_handler.GetErrors()), style_metric, min_file


def _SaveData(file_stats, stats, error_stats, project_argv):
  #process the collected data and save them
  #start the list of metrics
  #file info

  #indent - 4
  indent_count = 0
  indent_two = 0
  indent_four = 0
  indent_eight = 0
  indent_tab = 0
  indent_other = 0
  
  #use a new approach based on new stats
  for i in range(1,len(stats.indent_stats)):
    current_line = stats.indent_stats[i]
    last_line = stats.indent_stats[i-1]
    #get indent stats
    current_space_indent = current_line[1]
    current_tab_indent = current_line[2]   
    last_space_indent = last_line[1]
    last_tab_indent = last_line[2]
    #first consider tab indent
    if current_tab_indent != last_tab_indent:
      #if the number of tabs are not same
      #if same, either no indent or space indent
      indent_count += 1
      indent_tab += 1
    #then check space indent
    if current_space_indent != last_space_indent:
      #same space means no indent
      #only consider indent to avoid mistakes for outdent
      if current_space_indent - last_space_indent > 0:
        indent_count += 1
        indent_size = current_space_indent - last_space_indent
        if indent_size == 2:
          indent_two += 1
        elif indent_size == 4:
          indent_four += 1
        elif indent_size == 8:
          indent_eight += 1
        else:
          indent_other += 1

  '''
  for indent_line in stats.indent_stats:
    indent_width = indent_line[1]
    indent_depth = indent_line[2]
    indent_string = indent_line[3]
    num_tab = indent_string.count('\t')

    #if the current one is supposed to indent
    if indent_depth != 0:
      indent_count += 1
      if num_tab > 0:
        #if tab indent
        if num_tab == indent_depth:
          indent_tab += 1
        else:
          indent_other += 1
      else:
        #if not tab indent
        indent_size = indent_width / indent_depth
        if indent_size == 2:
          indent_two += 1
        elif indent_size == 4:
          indent_four += 1
        elif indent_size == 8:
          indent_eight += 1
        else:
          indent_other += 1
  '''

  #spacing
  #parentheses - 4
  count_start_paren = stats.start_paren_count
  count_start_paren_space_before = stats.start_paren_space_before
  count_start_paren_space_after = stats.start_paren_space_after
  
  count_end_paren = stats.end_paren_count
  count_end_paren_space_before = stats.end_paren_space_before
  count_end_paren_space_after = stats.end_paren_space_after

  #curly braces - 4
  count_start_brace = stats.start_block_count
  count_start_brace_space_before = stats.start_block_space_before
  count_start_brace_space_after = stats.start_block_space_after
  
  count_end_brace = stats.end_block_count
  count_end_brace_space_before = stats.end_block_space_before
  count_end_brace_space_after = stats.end_block_space_after

  #comma - 2
  count_comma = stats.comma_count
  count_comma_space_before = stats.comma_space_before
  count_comma_space_after = stats.comma_space_after

  #colon - 2
  count_colon = stats.colon_count
  count_colon_space_before = stats.colon_space_before
  count_colon_space_after = stats.colon_space_after

  #(other) operator - 2
  count_operator = stats.operator_count
  count_operator_space_before = stats.operator_space_before
  count_operator_space_after = stats.operator_space_after

  #comment space - 2
  count_block_comment_space = stats.block_comment_space
  #per_block_comment_space = stats.block_comment_space / stats.block_comment_count
  count_single_comment_space = stats.single_comment_space
  #per_single_comment_space = stats.single_comment_space / (stats.single_comment_count + stats.inline_comment_count) 

  #length - 2
  count_white_space_one = stats.white_space_list.count(1)
  count_white_space = stats.white_space_count
  if stats.white_space_count == 0:
    avg_length_white_space = 0
  else:
    avg_length_white_space = stats.white_space_total / stats.white_space_count

  end_line_blank = stats.end_new_line

  #naming
  #function names - 4
  #collect list of function names
  func_uppercase_char = 0
  func_lowercase_char = 0
  func_number_char = 0
  func_underscore_char = 0
  func_total_char = 0
  func_count = 0
  
  for function_name in stats.function_state_names:
    function_name = function_name.replace('$','')
    if function_name.find('.') > 0:
      #find the last element
      function_name = function_name.split('.')[-1]
    if function_name == '' or function_name == '_':
      continue
    if function_name in ('this','self','args','callback'):
      continue
    func_count += 1
    #check some indicators of function name
    func_uppercase_char += len(re.findall('([A-Z])', function_name))
    func_lowercase_char += len(re.findall('([a-z])', function_name))
    func_number_char += len(re.findall('([0-9])', function_name))
    func_underscore_char += len(re.findall('(_)', function_name))
  
  func_total_char = func_uppercase_char + func_lowercase_char + func_number_char + func_underscore_char
  
  #if func_total_char == 0:
  #  func_total_char = 1
  #per_func_uppercase_char = func_uppercase_char / func_total_char
  #per_func_lowercase_char = func_lowercase_char / func_total_char
  #per_func_number_char = func_number_char / func_total_char
  #per_func_underscore_char = func_underscore_char / func_total_char

  #variable names - 4
  #variable names = list of collected variable names - function names
  pure_variable_names = []
  for variable_name in stats.variable_names:
    variable_name = variable_name.replace('$','')
    if variable_name.find('.') > 0:
      #find the last element
      variable_name = variable_name.split('.')[-1]
    if variable_name == '' or variable_name == '_':
      continue
    if variable_name in ('this','self','args','callback'):
      continue
    if variable_name not in stats.function_state_names:
      #if the variable is not assigned with a function
      pure_variable_names.append(variable_name)

  var_uppercase_char = 0
  var_lowercase_char = 0
  var_number_char = 0
  var_underscore_char = 0
  var_total_char = 0
  var_count = 0
  
  for variable_name in pure_variable_names:
    var_count += 1
    #check some indicators of variable name
    var_uppercase_char += len(re.findall('([A-Z])', variable_name))
    var_lowercase_char += len(re.findall('([a-z])', variable_name))
    var_number_char += len(re.findall('([0-9])', variable_name))
    var_underscore_char += len(re.findall('(_)', variable_name))
  
  var_total_char = var_uppercase_char + var_lowercase_char + var_number_char + var_underscore_char
  
  #if var_total_char == 0:
  #  var_total_char = 1
  #per_var_uppercase_char = var_uppercase_char / var_total_char
  #per_var_lowercase_char = var_lowercase_char / var_total_char
  #per_var_number_char = var_number_char / var_total_char
  #per_var_underscore_char = var_underscore_char / var_total_char

  #length - 2
  if func_count == 0:
    func_length = 0
  else:
    func_length = func_total_char / func_count
  if var_count == 0:
    var_length = 0
  else:
    var_length = var_total_char / var_count

  #comment - 4
  count_single_comment = stats.single_comment_count
  count_multile_comment = stats.block_comment_count
  count_inline_comment = stats.inline_comment_count
  count_doc_comment = stats.doc_comment_count

  #comment line - 2
  count_blank_line = stats.blank_line_count
  count_multiple_comment_line = stats.block_comment_line
  count_doc_comment_line = stats.doc_comment_line

  #brace - 10
  count_start_brace_alone = stats.start_block_alone
  count_start_brace_begin = stats.start_block_begin
  count_start_brace_end = stats.start_block_end
  count_start_brace_mid = stats.start_block_mid

  count_end_brace_alone = stats.end_block_alone
  count_end_brace_begin = stats.end_block_begin
  count_end_brace_begin_nc = stats.end_block_begin_nocode
  count_end_brace_end = stats.end_block_end
  count_end_brace_end_nc = stats.end_block_end_nocode
  count_end_brace_mid = stats.end_block_mid

  #function
  #function declaration - 2
  count_function_expression = stats.num_function_declare 
  count_function_normal = stats.num_function_formal
  count_function_declare = stats.num_function_declare + stats.num_function_formal

  #function length - 2
  total_function_line = 0
  total_function_depth = 0
  function_count = 0
  for function_name, function_stats in stats.function_stats.items():
    if function_name == '':
      #something wrong?
      continue
    total_function_line += function_stats['pure_lines']
    total_function_depth += function_stats['block_depth']
    function_count += 1

  if function_count == 0:
    function_count = 1
  avg_function_line = total_function_line / function_count
  avg_function_depth = total_function_depth / function_count

  #block - 4
  #focus on block structure instead of simple block
  total_block_depth = 0
  total_block_count = 0
  block_stats_len = len(stats.block_stats)
  local_blocks = []
  for i in range(block_stats_len):
    block = stats.block_stats[i]
    block_index = i
    block_depth = block[1]

    #collect the stats into a list while the next one is larger than current one
    #the maximum one from one depth to another one depth

    #if encounter the last one:
    if block_index + 1 == block_stats_len:
      if block_depth == 1:
        #if depth is one, collect
        total_block_depth += block_depth
        total_block_count += 1
      else:
        #last one that is not depth one
        #append to a local list
        local_blocks.append(block_depth)
        #check the local peak if collect
        max_depth = max(local_blocks)
        total_block_depth += max_depth
        total_block_count += 1
        #clear local blocks after collecting
        local_blocks = []
    else:
      next_block = stats.block_stats[block_index+1]
      next_block_depth = next_block[1]    
      if block_depth == 1 and next_block_depth == 1:
        #if current one and next one are both one depth, collect current one
        total_block_depth += block_depth
        total_block_count += 1
      elif next_block_depth != 1:
        #if next one is not one depth
        local_blocks.append(block_depth)
      elif block_depth != 1 and next_block_depth == 1:
        #if next one is one depth, collect current one and check results
        local_blocks.append(block_depth)
        #check local peak
        max_depth = max(local_blocks)
        total_block_depth += max_depth
        total_block_count += 1
        #clear local blocks after collecting
        local_blocks = []

  if total_block_count == 0:
    avg_block_depth = 0
  else:
    avg_block_depth = total_block_depth / total_block_count

  line_count_all_total = stats.line_count_all_total
  line_count_total = stats.line_count_total
  line_count_pure = stats.line_count_pure

  if line_count_all_total == 0:
    avg_line_length_all = 0
  else:
    avg_line_length_all = stats.line_length_all_total / stats.line_count_all_total
  if line_count_total == 0:
    avg_line_length_code = 0
  else:
    avg_line_length_code = stats.line_length_total / stats.line_count_total
  if line_count_pure == 0:
    avg_line_length_pure = 0
  else:
    avg_line_length_pure = stats.line_length_pure / stats.line_count_pure

  #quote - 2
  count_quote = stats.single_quote_count + stats.double_quote_count
  count_single_quote = stats.single_quote_count
  count_double_quote = stats.double_quote_count

  #dot location - 3
  count_op_dot = stats.op_dot_count
  count_op_dot_begin = stats.op_dot_begin
  count_op_dot_end = stats.op_dot_end
  count_op_dot_mid = stats.op_dot_count - stats.op_dot_begin - stats.op_dot_end

  #operator location - 2
  count_op_split_begin = stats.op_split_begin
  count_op_split_end = stats.op_split_end
  count_op_split = stats.op_split_begin + stats.op_split_end

  #keyword loop - 3
  count_for = stats.keyword_for
  count_while = stats.keyword_while - stats.keyword_do
  count_dowhile = stats.keyword_do
  count_loop = stats.keyword_for + stats.keyword_while

  #keyword selection - 2
  count_if = stats.keyword_if
  count_switch = stats.keyword_switch
  count_selection =   stats.keyword_if + stats.keyword_switch

  #keyword count
  count_try = stats.keyword_try
  count_catch = stats.keyword_catch
  count_const = stats.keyword_const
  count_default = stats.keyword_default
  count_continue = stats.keyword_continue
  count_delete = stats.keyword_delete
  count_goto = stats.keyword_goto
  count_with = stats.keyword_with
  count_package = stats.keyword_package
  count_return = stats.keyword_return
  count_throw = stats.keyword_throw
  count_typeof = stats.keyword_typeof

  #if there are error indicators
  has_copyright = stats.has_copyright
  code_block_complete = stats.code_block_complete

  file_name = file_stats[0]
  html_file = file_stats[1]
  html_js = file_stats[2]
  html_js_line = file_stats[3]

  project_id = project_argv[0]
  sha = project_argv[1]
  file_num = project_argv[2]

  '''
  comma_error = error_stats.comma_error
  semicolon_error = error_stats.semicolon_error
  space_error = error_stats.space_error
  doc_error = error_stats.doc_error
  operator_error = error_stats.operator_error
  '''

  style_metric = [
      project_id, sha, file_num, file_name, html_file, html_js, html_js_line,
      indent_two, indent_four, indent_eight, indent_tab, indent_other, indent_count,
      count_start_paren_space_before, count_start_paren_space_after, count_start_paren,
      count_end_paren_space_before, count_end_paren_space_after, count_end_paren,
      count_start_brace_space_before, count_start_brace_space_after, count_start_brace,
      count_end_brace_space_before, count_end_brace_space_after, count_end_brace,
      count_comma_space_before, count_comma_space_after, count_comma,
      count_colon_space_before, count_colon_space_after, count_colon,
      count_operator_space_before, count_operator_space_after, count_operator,
      count_block_comment_space, count_single_comment_space,
      count_white_space_one, count_white_space, avg_length_white_space, end_line_blank,
      func_uppercase_char, func_lowercase_char, func_number_char, func_underscore_char, func_total_char, func_count,
      var_uppercase_char, var_lowercase_char, var_number_char, var_underscore_char, var_total_char, var_count,
      func_length, var_length,
      count_single_comment, count_multile_comment, count_inline_comment, count_doc_comment,
      count_blank_line, count_multiple_comment_line, count_doc_comment_line,
      count_start_brace_alone, count_start_brace_begin, count_start_brace_end, count_start_brace_mid,
      count_end_brace_alone, count_end_brace_begin, count_end_brace_begin_nc, 
      count_end_brace_end, count_end_brace_end_nc, count_end_brace_mid,
      count_function_normal, count_function_expression, count_function_declare,
      avg_function_line, avg_function_depth,
      avg_block_depth, line_count_all_total, line_count_total, line_count_pure,
      avg_line_length_all, avg_line_length_code, avg_line_length_pure,
      count_single_quote, count_double_quote, count_quote,
      count_op_dot_begin, count_op_dot_end, count_op_dot_mid, count_op_dot,
      count_op_split_begin, count_op_split_end, count_op_split,
      count_for, count_while, count_dowhile, count_loop,
      count_if, count_switch, count_selection,
      count_try, count_catch, count_const, count_default, count_continue, count_delete,
      count_goto, count_with, count_package, count_return, count_throw, count_typeof,
      has_copyright, code_block_complete
    ]
  
    #return the record to append and save to database
    #connect to database to save data - save data together

  return style_metric


def _SaveDatabase(style_metric_list):
  #connect database and save data
  # MYSQL SETTING
  HOST = "localhost"
  DATABASE = "ghtorrent" #database name
  USER = "root"
  PASSWORD = "root"
  LOCK_TIMEOUT = 120
  CREATE_TABLE = True

  create_style_metric = """
      CREATE TABLE IF NOT EXISTS style_metric (
        project_id int,
        sha varchar(100),
        file_num int,
        file_name varchar(1000),
        html_file int,
        html_js int,
        html_js_line int,
        indent_two int,
        indent_four int,
        indent_eight int,
        indent_tab int,
        indent_other int,
        indent_count int,
        count_start_paren_space_before int,
        count_start_paren_space_after int,
        count_start_paren int,
        count_end_paren_space_before int,
        count_end_paren_space_after int,
        count_end_paren int,
        count_start_brace_space_before int,
        count_start_brace_space_after int,
        count_start_brace int,
        count_end_brace_space_before int,
        count_end_brace_space_after int,
        count_end_brace int,
        count_comma_space_before int,
        count_comma_space_after int,
        count_comma int,
        count_colon_space_before int,
        count_colon_space_after int,
        count_colon int,
        count_operator_space_before int,
        count_operator_space_after int,
        count_operator int,
        count_block_comment_space int,
        count_single_comment_space int,
        count_white_space_one int,
        count_white_space int,
        avg_length_white_space float,
        end_line_blank int,
        func_uppercase_char int,
        func_lowercase_char int,
        func_number_char int,
        func_underscore_char int,
        func_total_char int,
        func_count int,
        var_uppercase_char int,
        var_lowercase_char int,
        var_number_char int,
        var_underscore_char int,
        var_total_char int,
        var_count int,
        func_length float,
        var_length float,
        count_single_comment int,
        count_multile_comment int,
        count_inline_comment int,
        count_doc_comment int,
        count_blank_line int,
        count_multiple_comment_line int,
        count_doc_comment_line int,
        count_start_brace_alone int,
        count_start_brace_begin int,
        count_start_brace_end int,
        count_start_brace_mid int,
        count_end_brace_alone int,
        count_end_brace_begin int,
        count_end_brace_begin_nc int,
        count_end_brace_end int,
        count_end_brace_end_nc int,
        count_end_brace_mid int,
        count_function_normal int,
        count_function_expression int,
        count_function_declare int,
        avg_function_line float,
        avg_function_depth float,
        avg_block_depth float,
        line_count_all_total int,
        line_count_total int,
        line_count_pure int,
        avg_line_length_all float,
        avg_line_length_code float,
        avg_line_length_pure float,
        count_single_quote int,
        count_double_quote int,
        count_quote int,
        count_op_dot_begin int,
        count_op_dot_end int,
        count_op_dot_mid int,
        count_op_dot int,
        count_op_split_begin int,
        count_op_split_end int,
        count_op_split int,
        count_for int,
        count_while int,
        count_dowhile int,
        count_loop int,
        count_if int,
        count_switch int,
        count_selection int,
        count_try int,
        count_catch int,
        count_const int,
        count_default int,
        count_continue int,
        count_delete int,
        count_goto int,
        count_with int,
        count_package int,
        count_return int,
        count_throw int,
        count_typeof int,
        has_copyright int,
        code_block_complete int,
        PRIMARY KEY (project_id,sha,file_num)
      )ENGINE = MyISAM CHARSET=utf8
      PARTITION BY KEY()
      PARTITIONS 10
  """

  #sql insert
  insert_style_metric = """
      INSERT IGNORE INTO style_metric (
        project_id, sha, file_num, file_name, html_file, html_js, html_js_line,
        indent_two, indent_four, indent_eight, indent_tab, indent_other, indent_count,
        count_start_paren_space_before, count_start_paren_space_after, count_start_paren,
        count_end_paren_space_before, count_end_paren_space_after, count_end_paren,
        count_start_brace_space_before, count_start_brace_space_after, count_start_brace,
        count_end_brace_space_before, count_end_brace_space_after, count_end_brace,
        count_comma_space_before, count_comma_space_after, count_comma,
        count_colon_space_before, count_colon_space_after, count_colon,
        count_operator_space_before, count_operator_space_after, count_operator,
        count_block_comment_space, count_single_comment_space,
        count_white_space_one, count_white_space, avg_length_white_space, end_line_blank,
        func_uppercase_char, func_lowercase_char, func_number_char, func_underscore_char, func_total_char, func_count,
        var_uppercase_char, var_lowercase_char, var_number_char, var_underscore_char, var_total_char, var_count,
        func_length, var_length,
        count_single_comment, count_multile_comment, count_inline_comment, count_doc_comment,
        count_blank_line, count_multiple_comment_line, count_doc_comment_line,
        count_start_brace_alone, count_start_brace_begin, count_start_brace_end, count_start_brace_mid,
        count_end_brace_alone, count_end_brace_begin, count_end_brace_begin_nc, 
        count_end_brace_end, count_end_brace_end_nc, count_end_brace_mid,
        count_function_normal, count_function_expression, count_function_declare,
        avg_function_line, avg_function_depth,
        avg_block_depth, line_count_all_total, line_count_total, line_count_pure,
        avg_line_length_all, avg_line_length_code, avg_line_length_pure,
        count_single_quote, count_double_quote, count_quote,
        count_op_dot_begin, count_op_dot_end, count_op_dot_mid, count_op_dot,
        count_op_split_begin, count_op_split_end, count_op_split,
        count_for, count_while, count_dowhile, count_loop,
        count_if, count_switch, count_selection,
        count_try, count_catch, count_const, count_default, count_continue, count_delete,
        count_goto, count_with, count_package, count_return, count_throw, count_typeof,
        has_copyright, code_block_complete) 
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
  """ 

  con = mysql.connector.connect(user=USER,
                                password=PASSWORD,
                                host=HOST,
                                database=DATABASE,
                                connection_timeout=LOCK_TIMEOUT)
  cur = con.cursor()
  cur.executemany(insert_style_metric, style_metric_list)
  con.commit()
  cur.close()
  con.close()


def _GetFilePaths(argv):
  suffixes = ['.js']
  if FLAGS.additional_extensions:
    suffixes += ['.%s' % ext for ext in FLAGS.additional_extensions]
  if FLAGS.check_html:
    suffixes += ['.html', '.htm']
  return fileflags.GetFileList(argv, 'JavaScript', suffixes)


# Error printing functions


def _PrintFileSummary(paths, records):
  """Print a detailed summary of the number of errors in each file."""

  paths = list(paths)
  paths.sort()

  for path in paths:
    path_errors = [e for e in records if e.path == path]
    print '%s: %d' % (path, len(path_errors))


def _PrintFileSeparator(path):
  print '----- FILE  :  %s -----' % path


def _PrintSummary(paths, error_records):
  """Print a summary of the number of errors and files."""

  error_count = len(error_records)
  all_paths = set(paths)
  all_paths_count = len(all_paths)

  if error_count is 0:
    print '%d files checked, no errors found.' % all_paths_count

  new_error_count = len([e for e in error_records if e.new_error])

  error_paths = set([e.path for e in error_records])
  error_paths_count = len(error_paths)
  no_error_paths_count = all_paths_count - error_paths_count

  if (error_count or new_error_count) and not FLAGS.quiet:
    error_noun = 'error' if error_count == 1 else 'errors'
    new_error_noun = 'error' if new_error_count == 1 else 'errors'
    error_file_noun = 'file' if error_paths_count == 1 else 'files'
    ok_file_noun = 'file' if no_error_paths_count == 1 else 'files'
    print ('Found %d %s, including %d new %s, in %d %s (%d %s OK).' %
           (error_count,
            error_noun,
            new_error_count,
            new_error_noun,
            error_paths_count,
            error_file_noun,
            no_error_paths_count,
            ok_file_noun))


def _PrintErrorRecords(error_records):
  """Print error records strings in the expected format."""

  current_path = None
  for record in error_records:

    if current_path != record.path:
      current_path = record.path
      if not FLAGS.unix_mode:
        _PrintFileSeparator(current_path)

    print record.error_string


def _FormatTime(t):
  """Formats a duration as a human-readable string.

  Args:
    t: A duration in seconds.

  Returns:
    A formatted duration string.
  """
  if t < 1:
    return '%dms' % round(t * 1000)
  else:
    return '%.2fs' % t




def main(argv=None):
  """Main function.

  Args:
    argv: Sequence of command line arguments.
  """
  if argv is None:
    argv = flags.FLAGS(sys.argv)

  if FLAGS.time:
    start_time = time.time()

  # Emacs sets the environment variable INSIDE_EMACS in the subshell.
  # Request Unix mode as emacs will expect output to be in Unix format
  # for integration.
  # See https://www.gnu.org/software/emacs/manual/html_node/emacs/
  # Interactive-Shell.html
  if 'INSIDE_EMACS' in os.environ:
    FLAGS.unix_mode = True

  suffixes = ['.js']
  if FLAGS.additional_extensions:
    suffixes += ['.%s' % ext for ext in FLAGS.additional_extensions]
  if FLAGS.check_html:
    suffixes += ['.html', '.htm']

  paths = fileflags.GetFileList(argv, 'JavaScript', suffixes)
  #@zhiyiadd
  #get project_id and sha
  project_argv = sys.argv[4:]

  #@zhiyiadd
  #paths will include the list of files 
  #get project_id and sha from file path

  #can simply pass project_id and sha to argv,
  #and compile path in this file
  #use --recurse to loop all files
  #argv_path = "/home/hdd/zhiyi/GHSC/"+project_id+"/"+repo_name+"-"+sha

  '''
  if FLAGS.multiprocess:
    records_iter = _MultiprocessCheckPaths(paths)
  else:
    records_iter = _CheckPaths(paths)

  records_iter, records_iter_copy = itertools.tee(records_iter, 2)
  _PrintErrorRecords(records_iter_copy)
  '''

  #error_records = list(records_iter)
  #_PrintSummary(paths, error_records)
  

  #@zhiyiadd
  #if not print errors, just get the returned style data
  style_metric_list = _CheckPaths(paths, project_argv)
  
  #records_iter = _CheckPaths(paths)
  
  #records_iter, records_iter_copy = itertools.tee(records_iter, 2)
  #_PrintErrorRecords(records_iter_copy)

  #for style_metric in style_metric_list:
  #  print style_metric

  _SaveDatabase(style_metric_list)

  exit_code = 0

  #@zhiyiadd
  #test argv
  #print argv
  #for path in paths:
    #path = path.replace("/home/hdd/zhiyi/GHSC/", "")
    #remove same path prefix
  #  print path

  # If there are any errors
  #if error_records:
  #  exit_code += 1

  # If there are any new errors
  #if [r for r in error_records if r.new_error]:
  #  exit_code += 2

  #if exit_code:
    #if FLAGS.summary:
    #  _PrintFileSummary(paths, error_records)

    #if FLAGS.beep:
      # Make a beep noise.
      #sys.stdout.write(chr(7))

    # Write out instructions for using fixjsstyle script to fix some of the
    # reported errors.
    #fix_args = []
    #for flag in sys.argv[1:]:
    #  for f in GJSLINT_ONLY_FLAGS:
    #    if flag.startswith(f):
    #      break
    #  else:
    #    fix_args.append(flag)

    #if not FLAGS.quiet:
    #  print """
#Some of the errors reported by GJsLint may be auto-fixable using the script
#fixjsstyle. Please double check any changes it makes and report any bugs. The
#script can be run by executing:

#fixjsstyle %s """ % ' '.join(fix_args)

  if FLAGS.time:
    print 'Done in %s.' % _FormatTime(time.time() - start_time)

  sys.exit(exit_code)


if __name__ == '__main__':
  main()
