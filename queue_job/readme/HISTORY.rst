.. [ The change log. The goal of this file is to help readers
    understand changes between version. The primary audience is
    end users and integrators. Purely technical changes such as
    code refactoring must not be mentioned here.
    
    This file may contain ONE level of section titles, underlined
    with the ~ (tilde) character. Other section markers are
    forbidden and will likely break the structure of the README.rst
    or other documents where this fragment is included. ]

11.0.1.1.0 (2018-05-25)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] New neat OCA readme file format
  (`#71 <https://github.com/OCA/queue/pull/71>`_)
* [ADD] The Jobrunner will keep the same Web Session and no longer generate a
  new session per job
  (`#54 <https://github.com/OCA/queue/pull/54>`_)
* [ADD] Configurable scheme, host and HTTP authentication
  (`#51 <https://github.com/OCA/queue/pull/51>`_)
* [ADD] ``base_sparse_field`` does not longer need to be set in ``--load``
  (`#47 <https://github.com/OCA/queue/pull/47>`_)
* [FIX] Correct automatic registration of channels and job functions
  (`#69 <https://github.com/OCA/queue/pull/69>`_)
* [FIX] Correct compatibility with ``@property`` methods
  (`#50 <https://github.com/OCA/queue/pull/50>`_) and (`#69 <https://github.com/OCA/queue/pull/69>`_)
