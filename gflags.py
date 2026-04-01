"""Minimal gflags compatibility shim for local Python 3 execution."""


class _FlagValues(object):
  def __init__(self):
    self._flags = {}

  def __call__(self, argv):
    return argv

  def __getattr__(self, name):
    try:
      return self._flags[name]
    except KeyError:
      raise AttributeError(name)

  def __setattr__(self, name, value):
    if name == '_flags':
      object.__setattr__(self, name, value)
    else:
      self._flags[name] = value

  def FlagDict(self):
    return dict(self._flags)


FLAGS = _FlagValues()


def _DefineFlag(name, default):
  setattr(FLAGS, name, default)


def DEFINE_boolean(name, default, help_text, **kwargs):
  del help_text, kwargs
  _DefineFlag(name, default)


def DEFINE_integer(name, default, help_text, **kwargs):
  del help_text, kwargs
  _DefineFlag(name, default)


def DEFINE_list(name, default, help_text, **kwargs):
  del help_text, kwargs
  _DefineFlag(name, list(default) if default is not None else None)


def DEFINE_multistring(name, default, help_text, **kwargs):
  del help_text, kwargs
  _DefineFlag(name, list(default) if default is not None else [])


def ADOPT_module_key_flags(module):
  del module
