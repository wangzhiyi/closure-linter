"""Tiny subset of the mox API used by this repository's tests."""


class _Matcher(object):
  def matches(self, value):
    raise NotImplementedError


class _IsA(_Matcher):
  def __init__(self, expected_type):
    self._expected_type = expected_type

  def matches(self, value):
    return isinstance(value, self._expected_type)


class _Func(_Matcher):
  def __init__(self, func):
    self._func = func

  def matches(self, value):
    return bool(self._func(value))


def IsA(expected_type):
  return _IsA(expected_type)


def Func(func):
  return _Func(func)


class _MockObject(object):
  def __init__(self):
    self._expectations = []
    self._replay = False
    self._cursor = 0

  def _set_replay(self):
    self._replay = True

  def _verify(self):
    if self._cursor != len(self._expectations):
      raise AssertionError('Not all expected calls were made.')

  def __getattr__(self, name):
    def _method(*args, **kwargs):
      if kwargs:
        raise AssertionError('Keyword arguments are not supported in this mock.')
      if not self._replay:
        self._expectations.append((name, args))
        return None
      if self._cursor >= len(self._expectations):
        raise AssertionError('Unexpected call to %s.' % name)
      expected_name, expected_args = self._expectations[self._cursor]
      if expected_name != name:
        raise AssertionError('Expected %s but got %s.' % (expected_name, name))
      if len(expected_args) != len(args):
        raise AssertionError('Argument count mismatch for %s.' % name)
      for expected, actual in zip(expected_args, args):
        if isinstance(expected, _Matcher):
          if not expected.matches(actual):
            raise AssertionError('Matcher failed for %s.' % name)
        elif expected != actual:
          raise AssertionError('Expected %r but got %r.' % (expected, actual))
      self._cursor += 1
      return None

    return _method


class Mox(object):
  def __init__(self):
    self._mocks = []

  def CreateMock(self, cls):
    del cls
    mock = _MockObject()
    self._mocks.append(mock)
    return mock

  def ReplayAll(self):
    for mock in self._mocks:
      mock._set_replay()

  def VerifyAll(self):
    for mock in self._mocks:
      mock._verify()
