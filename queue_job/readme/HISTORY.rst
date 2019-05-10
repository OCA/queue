.. [ The change log. The goal of this file is to help readers
    understand changes between version. The primary audience is
    end users and integrators. Purely technical changes such as
    code refactoring must not be mentioned here.
    
    This file may contain ONE level of section titles, underlined
    with the ~ (tilde) character. Other section markers are
    forbidden and will likely break the structure of the README.rst
    or other documents where this fragment is included. ]

Next
~~~~

* [IMP] Dont' start the Jobrunner if root channel's capacity
  is explicitly set to 0
* [ADD] Ability to set several jobs to done using an multi-action
  (port of `#59 <https://github.com/OCA/queue/pull/59>`_)
* [REF] Extract a method handling the post of a message when a job is failed,
  allowing to modify this behavior from addons
* [ADD] Default "related action" for jobs, opening a form or list view (when
  the job is linked to respectively one record on several).
  (`#46 <https://github.com/OCA/queue/pull/46>`_)
* [FIX] Error when creating a job channel manually
  (`#96 <https://github.com/OCA/queue/pull/96>`_)

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
  (`#50 <https://github.com/OCA/queue/pull/50>`_ and `#69 <https://github.com/OCA/queue/pull/69>`__)
