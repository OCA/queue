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

* [ADD] Run jobrunner as a worker process instead of a thread in the main
  process (when running with --workers > 0)
* [REF] ``@job`` and ``@related_action`` deprecated, any method can be delayed,
  and configured using ``queue.job.function`` records

12.0.1.1.0 (2019-11-01)
~~~~~~~~~~~~~~~~~~~~~~~

Important: the license has been changed from AGPL3 to LGPL3.

* [IMP] Dont' start the Jobrunner if root channel's capacity
  is explicitly set to 0
* [ADD] Ability to set several jobs to done using an multi-action
  (port of `#59 <https://github.com/OCA/queue/pull/59>`_)
* [REF] Extract a method handling the post of a message when a job is failed,
  allowing to modify this behavior from addons
* [ADD] Allow Jobrunner configuration from server_environment
  (details on `#124 <https://github.com/OCA/queue/pull/124>`_)
* [ADD] Environment variable ``TEST_QUEUE_JOB_NO_DELAY=1`` for test and debug
  (details on `#114 <https://github.com/OCA/queue/pull/114>`_)
* [FIX] race condition under pressure, when starting a job takes more than 1 second
  (details on `#131 <https://github.com/OCA/queue/pull/131>`_)
* [FIX] ``retry_postone`` on a job could be rollbacked on errors
  (details on `#130 <https://github.com/OCA/queue/pull/130>`_)
* [FIX] Autovacuum cron job misconfiguration
  (details on `#163 <https://github.com/OCA/queue/pull/163>`_)

12.0.1.0.0 (2018-10-02)
~~~~~~~~~~~~~~~~~~~~~~~

* [MIGRATION] from 11.0 branched at rev. b0945be
