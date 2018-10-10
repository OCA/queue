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

* [IMP] Dont' start the Jobrunner if root channel's capacity is explicitly set
  to 0 (backport from `#148 <https://github.com/OCA/queue/pull/148>`_)
* [ADD] Default "related action" for jobs, opening a form or list view (when
  the job is linked to respectively one record on several).
  (`#79 <https://github.com/OCA/queue/pull/79>`_, backport from `#46 <https://github.com/OCA/queue/pull/46>`_)

10.0.1.1.3
~~~~~~~~~~

* [REF] Extract a method handling the post of a message when a job is failed,
  allowing to modify this behavior from addons (Backport of `#108 <https://github.com/OCA/queue/pull/108>`)

10.0.1.0.0
~~~~~~~~~~

* Starting the changelog from there
